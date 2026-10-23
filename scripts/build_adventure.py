#!/usr/bin/env python3
"""Build the audited Open Adventure release for the signed ARM64 app."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from build_bsd_adventure import build as build_bsd

URL = "https://gitlab.com/esr/open-adventure/-/archive/1.22/open-adventure-1.22.tar.gz"
SOURCE_SHA256 = "a40127c8296a5872ff69b53ecf4028797999f87cbc0735b9c379cecd1cb446f7"
COMMIT = "e6160529e70a8c7a06b9a5f190d69aa35c4c62f5"
YAML_WHEEL_URL = "https://files.pythonhosted.org/packages/89/a0/6cf41a19a1f2f3feab0e9c0b74134aa2ce6849093d5517a0c550fe37a648/pyyaml-6.0.3-cp312-cp312-macosx_11_0_arm64.whl"
YAML_WHEEL_SHA256 = "fc09d0aa354569bc501d4e787133afc08552722d3ab34836a80547331bb5d4a0"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(cache: Path, temporary: Path, resources: Path, builder: Path, fetch) -> dict:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Adventure bundle requires an ARM64 macOS build host")
    archive = fetch(URL, cache / "open-adventure-1.22.tar.gz", SOURCE_SHA256)
    source = temporary / "open-adventure"
    source.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as bundle:
        if sum(member.size for member in bundle.getmembers()) > 32 * 1024 * 1024:
            raise ValueError("Open Adventure archive exceeds source size limit")
        bundle.extractall(source, filter="data")
    checkout = source / "open-adventure-1.22"
    copying = (checkout / "COPYING").read_text()
    yaml = checkout / "adventure.yaml"
    if "BSD 2-Clause LICENSE" not in copying or "SPDX-License-Identifier: BSD-2-Clause" not in yaml.read_text().splitlines()[:3]:
        raise ValueError("Open Adventure source or game-data license changed")
    wheel = fetch(YAML_WHEEL_URL, cache / "pyyaml-6.0.3-cp312-cp312-macosx_11_0_arm64.whl", YAML_WHEEL_SHA256)
    subprocess.run([str(builder), "-I", "-m", "pip", "install", "--no-deps", "--no-index", str(wheel)],
                   check=True, shell=False)
    subprocess.run([str(builder), "-I", "make_dungeon.py"], cwd=checkout, check=True, shell=False)
    subprocess.run(["make", "advent", "CC=/usr/bin/clang", "CFLAGS=-DADVENT_AUTOSAVE -arch arm64 -mmacosx-version-min=13.0"],
                   cwd=checkout, check=True, shell=False)
    target = resources / "adventure"
    target.mkdir()
    executable = target / "advent-430"
    shutil.copy2(checkout / "advent", executable)
    shutil.copy2(checkout / "COPYING", target / "COPYING-430")
    provenance = {
        "schema_version": 1,
        "editions": {
            "1995": {
                "name": "Open Adventure 2.5, 430 points",
                "executable": executable.name,
                "sha256": digest(executable),
                "game_data": "Compiled from adventure.yaml",
                "game_data_sha256": digest(yaml),
                "license": "BSD-2-Clause",
                "source_url": URL,
                "source_sha256": SOURCE_SHA256,
                "source_commit": COMMIT,
                "source_tag": "1.22",
                "build_dependency": {"name": "PyYAML", "version": "6.0.3", "wheel_sha256": YAML_WHEEL_SHA256},
            }
        },
    }
    provenance["editions"]["1977"] = build_bsd(cache / "bsd-350", temporary / "bsd-350", resources, fetch)
    (target / "manifest.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return provenance


def fetch(url: str, path: Path, expected: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and digest(path) == expected:
        return path
    with urllib.request.urlopen(url, timeout=60) as response, path.open("wb") as destination:
        shutil.copyfileobj(response, destination)
    if digest(path) != expected:
        path.unlink(missing_ok=True)
        raise ValueError("Pinned Adventure source or build dependency hash mismatch")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="adventure-build-") as temporary:
        root = Path(temporary)
        receipt = build(root / "cache", root / "source", arguments.output,
                        arguments.python, fetch)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
