"""Settings: defaults < `.pr-brief.yml` < environment (`PR_BRIEF_*`) < explicit overrides."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    model_validator,
)

from pr_brief.errors import ConfigError

ENV_PREFIX = "PR_BRIEF_"
DEFAULT_CONFIG_PATH = ".pr-brief.yml"
MAX_CONFIG_BYTES = 64 * 1024

ProviderName = Literal["mock", "ollama", "openai-compatible", "anthropic", "gemini"]
PresetName = Literal["balanced", "cheap", "strict"]

# Ready-made token budgets. Only budgets: a preset can never loosen a security setting. Single
# settings (file, environment, inputs) still override whatever the preset sets.
PRESETS: dict[str, dict[str, Any]] = {
    "balanced": {},  # the plain defaults
    "cheap": {"max_input_tokens": 3000, "max_output_tokens": 500},
    "strict": {"max_input_tokens": 12000, "max_output_tokens": 1500},
}


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderName
    model: str | None = None
    api_key: SecretStr | None = None
    base_url: str | None = None
    preset: PresetName = "balanced"
    language: Literal["en", "tr"] = "en"
    max_input_tokens: int = Field(6000, ge=500, le=200_000)
    max_output_tokens: int = Field(900, ge=100, le=16_000)
    ignore: list[str] = Field(default_factory=list)
    include_drafts: bool = False
    skip_bots: bool = True
    dry_run: bool = False
    fail_on_error: bool = False
    config_path: str = DEFAULT_CONFIG_PATH
    cache: bool = True
    timeout_seconds: float = Field(60, gt=0, le=600)
    # Your provider's price in USD per million tokens; only used for the cost line of the summary.
    price_input_per_million: float | None = Field(None, ge=0, le=1_000_000, allow_inf_nan=False)
    price_output_per_million: float | None = Field(None, ge=0, le=1_000_000, allow_inf_nan=False)

    @model_validator(mode="after")
    def _prices_come_in_pairs(self) -> Settings:
        if (self.price_input_per_million is None) != (self.price_output_per_million is None):
            raise ValueError(
                "price-input-per-million and price-output-per-million must be set together"
            )
        return self


_FIELDS = frozenset(Settings.model_fields)


def load_settings(
    env: Mapping[str, str],
    *,
    base_dir: Path,
    overrides: Mapping[str, object] | None = None,
    config_loader: Callable[[str], str | None] | None = None,
) -> Settings:
    """`config_loader(path)` returns the config file's text (None if absent) instead of reading
    `base_dir`; the GitHub mode uses it to read the file from the base commit, never the PR head.
    """
    env_values: dict[str, Any] = {}
    for name in _FIELDS:
        raw = env.get(ENV_PREFIX + name.upper())
        if raw is not None and raw.strip():
            env_values[name] = raw.strip() if name != "ignore" else raw
    config_path = str(env_values.get("config_path") or (overrides or {}).get("config_path") or "")
    explicit = bool(config_path)
    config_path = config_path or DEFAULT_CONFIG_PATH
    file_values = _read_file(base_dir, config_path, explicit=explicit, loader=config_loader)
    chosen = {**file_values, **env_values, **(overrides or {})}.get("preset")
    preset_values = PRESETS.get(chosen, {}) if isinstance(chosen, str) else {}
    merged: dict[str, Any] = {**preset_values, **file_values, **env_values, **(overrides or {})}
    if isinstance(merged.get("ignore"), str):
        merged["ignore"] = [ln.strip() for ln in merged["ignore"].splitlines() if ln.strip()]
    # The API key is read from the environment only (never from the repository file).
    key = env.get(ENV_PREFIX + "API_KEY", "").strip()
    if key:
        merged["api_key"] = key
    try:
        return Settings.model_validate(merged)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'settings'}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(
            f"Invalid configuration ({problems}).",
            hint="see docs/configuration.md for the allowed values.",
        ) from None


def _read_file(
    base_dir: Path,
    config_path: str,
    *,
    explicit: bool,
    loader: Callable[[str], str | None] | None,
) -> dict[str, Any]:
    if (
        PurePosixPath(config_path).is_absolute()
        or PureWindowsPath(config_path).is_absolute()
        or ".." in PurePosixPath(config_path.replace("\\", "/")).parts
    ):
        raise ConfigError(
            "config-path must be a relative path inside the repository.",
            hint="use a path like .pr-brief.yml.",
        )
    text = loader(config_path) if loader else _read_local(base_dir / config_path)
    if text is None:
        if explicit:
            raise ConfigError(
                f"Config file {config_path} was not found.",
                hint="check the config-path input or remove it to use the default.",
            )
        return {}
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigError(f"Config file {config_path} is too large (limit 64 KiB).")
    try:
        data = yaml.safe_load(text)
    except (yaml.YAMLError, RecursionError):
        raise ConfigError(
            f"Config file {config_path} is not valid YAML.",
            hint="validate it with a YAML linter.",
        ) from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {config_path} must be a mapping of settings.")
    out = {str(k).replace("-", "_"): v for k, v in data.items()}
    if "api_key" in out:
        raise ConfigError(
            "api-key must not be set in the config file (api-key).",
            hint="pass it via the action's api-key input from a repository secret.",
        )
    return out


def _read_local(path: Path) -> str | None:
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise ConfigError(f"Config file {path.name} is too large (limit 64 KiB).")
    return path.read_text(encoding="utf-8")
