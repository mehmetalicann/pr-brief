"""The SBOM is derived from the hash-locked requirements: it lists what the action runs."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sbom_script", ROOT / "scripts" / "sbom.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sbom_script"] = module
    spec.loader.exec_module(module)
    return module


sbom = _load()

LOCK = """\
# comment line
Anyio==4.16.0 \
    --hash=sha256:aaaa \
    --hash=sha256:bbbb
httpx==0.28.1 \
    --hash=sha256:cccc
"""


def test_the_lock_file_is_parsed_into_names_versions_and_hashes() -> None:
    packages = sbom.parse_lock(LOCK)
    assert [(p.name, p.version, p.hashes) for p in packages] == [
        ("anyio", "4.16.0", ("aaaa", "bbbb")),
        ("httpx", "0.28.1", ("cccc",)),
    ]


def test_the_document_is_a_cyclonedx_bom_with_purls_and_hashes() -> None:
    doc = sbom.build_sbom(sbom.parse_lock(LOCK), version="1.2.3", timestamp="2026-12-01T00:00:00Z")
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.5"
    assert doc["metadata"]["component"]["name"] == "pr-brief"
    assert doc["metadata"]["component"]["version"] == "1.2.3"
    assert doc["metadata"]["timestamp"] == "2026-12-01T00:00:00Z"
    first = doc["components"][0]
    assert first["purl"] == "pkg:pypi/anyio@4.16.0"
    assert first["hashes"] == [
        {"alg": "SHA-256", "content": "aaaa"},
        {"alg": "SHA-256", "content": "bbbb"},
    ]
    assert re.fullmatch(r"urn:uuid:[0-9a-f-]{36}", doc["serialNumber"])
    json.dumps(doc)  # serialisable


def test_the_real_lock_file_yields_every_runtime_dependency_with_hashes() -> None:
    packages = sbom.parse_lock((ROOT / "requirements.lock").read_text(encoding="utf-8"))
    names = {p.name for p in packages}
    assert {"httpx", "pydantic", "pyyaml"} <= names
    assert all(p.hashes and re.fullmatch(r"[0-9a-f]{64}", p.hashes[0]) for p in packages)


def test_the_cli_writes_the_file(tmp_path: Path) -> None:
    out = tmp_path / "sbom.cdx.json"
    code = sbom.main(
        ["--version", "1.2.3", "--lock", str(ROOT / "requirements.lock"), "--out", str(out)]
    )
    assert code == 0
    assert (
        json.loads(out.read_text(encoding="utf-8"))["metadata"]["component"]["version"] == "1.2.3"
    )
