"""Writes a CycloneDX 1.5 SBOM from the hash-locked requirements (standard library only).

    python scripts/sbom.py --version 1.0.0 --out sbom.cdx.json

`requirements.lock` is exactly what the action installs (`pip install --require-hashes`), so the
SBOM lists the real runtime dependencies with their versions and SHA-256 hashes. The release
workflow attaches the file to the GitHub release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.!+_-]+)", re.M)
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]+)")


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    hashes: tuple[str, ...]


def parse_lock(text: str) -> list[Package]:
    """Packages of a pip-compile `--generate-hashes` file, names normalised to lower case."""
    packages: list[Package] = []
    matches = list(REQUIREMENT_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        packages.append(
            Package(
                name=re.sub(r"[-_.]+", "-", match.group(1)).lower(),
                version=match.group(2),
                hashes=tuple(HASH_RE.findall(text[match.end() : end])),
            )
        )
    return packages


def build_sbom(packages: list[Package], *, version: str, timestamp: str) -> dict[str, object]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "name": "pr-brief",
                "version": version,
                "purl": f"pkg:github/mehmetalicann/pr-brief@v{version}",
            },
        },
        "components": [
            {
                "type": "library",
                "name": p.name,
                "version": p.version,
                "purl": f"pkg:pypi/{p.name}@{p.version}",
                "hashes": [{"alg": "SHA-256", "content": h} for h in p.hashes],
            }
            for p in packages
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--lock", type=Path, default=ROOT / "requirements.lock")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    packages = parse_lock(args.lock.read_text(encoding="utf-8"))
    if not packages:
        print("sbom: no packages found in the lock file", file=sys.stderr)
        return 1
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_sbom(packages, version=args.version, timestamp=stamp)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
