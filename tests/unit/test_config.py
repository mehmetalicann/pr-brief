from pathlib import Path

import pytest

from pr_brief.config import Settings, load_settings
from pr_brief.errors import ConfigError


def write(tmp_path: Path, text: str, name: str = ".pr-brief.yml") -> None:
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_defaults_match_the_spec(tmp_path: Path) -> None:
    s = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    assert s.provider == "mock"
    assert s.language == "en"
    assert (s.max_input_tokens, s.max_output_tokens) == (6000, 900)
    assert s.ignore == []
    assert (s.include_drafts, s.dry_run, s.fail_on_error, s.cache) == (False, False, False, True)
    assert s.config_path == ".pr-brief.yml"
    assert s.timeout_seconds == 60
    assert s.api_key is None


def test_provider_is_required(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="provider"):
        load_settings({}, base_dir=tmp_path)


def test_file_is_read_and_kebab_case_keys_are_accepted(tmp_path: Path) -> None:
    write(tmp_path, "provider: mock\nlanguage: tr\nmax-input-tokens: 3000\nignore:\n  - gen/**\n")
    s = load_settings({}, base_dir=tmp_path)
    assert (s.language, s.max_input_tokens, s.ignore) == ("tr", 3000, ["gen/**"])


def test_precedence_overrides_beat_env_beat_file_beat_defaults(tmp_path: Path) -> None:
    write(tmp_path, "provider: mock\nlanguage: tr\nmax-input-tokens: 3000\nmodel: from-file\n")
    env = {"PR_BRIEF_LANGUAGE": "en", "PR_BRIEF_MODEL": "from-env"}
    s = load_settings(env, base_dir=tmp_path, overrides={"model": "from-cli"})
    assert s.model == "from-cli"
    assert s.language == "en"  # env beats file
    assert s.max_input_tokens == 3000  # file beats default


def test_empty_env_values_count_as_unset(tmp_path: Path) -> None:
    write(tmp_path, "provider: mock\nlanguage: tr\n")
    s = load_settings({"PR_BRIEF_LANGUAGE": "  ", "PR_BRIEF_MODEL": ""}, base_dir=tmp_path)
    assert s.language == "tr"
    assert s.model is None


def test_env_strings_are_coerced(tmp_path: Path) -> None:
    env = {
        "PR_BRIEF_PROVIDER": "mock",
        "PR_BRIEF_DRY_RUN": "true",
        "PR_BRIEF_CACHE": "false",
        "PR_BRIEF_MAX_INPUT_TOKENS": "4000",
        "PR_BRIEF_TIMEOUT_SECONDS": "12.5",
        "PR_BRIEF_IGNORE": "docs/**\n\n  *.snap  \n",
    }
    s = load_settings(env, base_dir=tmp_path)
    assert s.dry_run is True
    assert s.cache is False
    assert s.max_input_tokens == 4000
    assert s.timeout_seconds == 12.5
    assert s.ignore == ["docs/**", "*.snap"]


def test_api_key_comes_only_from_env_and_is_masked(tmp_path: Path) -> None:
    secret = "sk-test-" + "SECRET-1234567890abcdef"  # fake, built at runtime
    s = load_settings({"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_API_KEY": secret}, base_dir=tmp_path)
    assert s.api_key is not None
    assert s.api_key.get_secret_value() == secret
    assert secret not in repr(s)
    assert secret not in str(s)


def test_api_key_in_config_file_is_rejected_without_echoing_it(tmp_path: Path) -> None:
    secret = "sk-test-" + "SECRET-1234567890abcdef"  # fake, built at runtime
    write(tmp_path, f"provider: mock\napi-key: {secret}\n")
    with pytest.raises(ConfigError, match="api-key") as exc:
        load_settings({}, base_dir=tmp_path)
    assert secret not in exc.value.user_message()


def test_unknown_key_in_file_is_an_error(tmp_path: Path) -> None:
    write(tmp_path, "provider: mock\nlangauge: tr\n")
    with pytest.raises(ConfigError, match="langauge"):
        load_settings({}, base_dir=tmp_path)


def test_invalid_values_name_the_field_not_the_value(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="max_input_tokens"):
        load_settings(
            {"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_MAX_INPUT_TOKENS": "5"}, base_dir=tmp_path
        )
    with pytest.raises(ConfigError, match="provider"):
        load_settings({"PR_BRIEF_PROVIDER": "nope"}, base_dir=tmp_path)


def test_malformed_yaml_and_non_mapping_are_errors(tmp_path: Path) -> None:
    write(tmp_path, "provider: [unclosed\n")
    with pytest.raises(ConfigError, match="YAML"):
        load_settings({}, base_dir=tmp_path)
    write(tmp_path, "- just\n- a list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_settings({}, base_dir=tmp_path)


def test_empty_file_is_fine(tmp_path: Path) -> None:
    write(tmp_path, "")
    assert load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path).provider == "mock"


def test_missing_default_file_is_fine_but_missing_explicit_file_is_not(tmp_path: Path) -> None:
    assert load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path).provider == "mock"
    env = {"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_CONFIG_PATH": "custom.yml"}
    with pytest.raises(ConfigError, match=r"custom\.yml"):
        load_settings(env, base_dir=tmp_path)


@pytest.mark.parametrize("bad", ["../outside.yml", "/etc/passwd", "C:/Windows/x.yml"])
def test_config_path_must_stay_inside_the_repo(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ConfigError, match="config-path"):
        load_settings({"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_CONFIG_PATH": bad}, base_dir=tmp_path)


def test_oversized_file_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "provider: mock\n# " + "x" * 70_000 + "\n")
    with pytest.raises(ConfigError, match="too large"):
        load_settings({}, base_dir=tmp_path)


def test_settings_is_immutable(tmp_path: Path) -> None:
    s: Settings = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path)
    with pytest.raises(ValueError, match="frozen"):
        s.language = "tr"  # type: ignore[misc]


def test_config_loader_replaces_the_working_directory_file(tmp_path: Path) -> None:
    write(tmp_path, "language: tr\n")  # must be ignored when a loader is given
    seen: list[str] = []

    def loader(path: str) -> str | None:
        seen.append(path)
        return "model: from-base\n"

    s = load_settings({"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path, config_loader=loader)
    assert (s.model, s.language, seen) == ("from-base", "en", [".pr-brief.yml"])


def test_config_loader_missing_default_file_is_fine(tmp_path: Path) -> None:
    s = load_settings(
        {"PR_BRIEF_PROVIDER": "mock"}, base_dir=tmp_path, config_loader=lambda _p: None
    )
    assert s.model is None


def test_config_loader_missing_explicit_file_is_an_error(tmp_path: Path) -> None:
    env = {"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_CONFIG_PATH": "x.yml"}
    with pytest.raises(ConfigError, match="not found"):
        load_settings(env, base_dir=tmp_path, config_loader=lambda _p: None)


def test_config_loader_is_never_asked_for_unsafe_paths(tmp_path: Path) -> None:
    def boom(_p: str) -> str:
        raise AssertionError("loader must not be called")

    for bad in ("/etc/passwd", "../secret.yml"):
        env = {"PR_BRIEF_PROVIDER": "mock", "PR_BRIEF_CONFIG_PATH": bad}
        with pytest.raises(ConfigError):
            load_settings(env, base_dir=tmp_path, config_loader=boom)


def test_config_loader_text_is_size_limited_and_rejects_api_key(tmp_path: Path) -> None:
    env = {"PR_BRIEF_PROVIDER": "mock"}
    with pytest.raises(ConfigError, match="too large"):
        load_settings(env, base_dir=tmp_path, config_loader=lambda _p: "a: " + "x" * 70_000)
    with pytest.raises(ConfigError, match="api-key"):
        load_settings(env, base_dir=tmp_path, config_loader=lambda _p: "api-key: abc\n")
