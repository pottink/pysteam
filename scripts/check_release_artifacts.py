"""Ensure release archives contain only the distributable SDK and metadata."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDIST_ROOT_FILES = {
    "LICENSE",
    "PKG-INFO",
    "README.md",
    "pyproject.toml",
    "pyproject.toml.orig",
}


def _one_artifact(pattern: str) -> Path:
    matches = list((ROOT / "dist").glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {pattern} artifact")
    return matches[0]


def check() -> None:
    sdist = _one_artifact("pysteam_sdk-*.tar.gz")
    wheel = _one_artifact("pysteam_sdk-*.whl")

    with tarfile.open(sdist, "r:gz") as archive:
        names = [
            Path(*Path(member.name).parts[1:]).as_posix()
            for member in archive.getmembers()
            if member.isfile()
        ]
    unexpected_sdist = sorted(
        name
        for name in names
        if name not in SDIST_ROOT_FILES and not name.startswith("src/pysteam/")
    )
    if unexpected_sdist:
        raise RuntimeError(f"unexpected source archive files: {unexpected_sdist}")

    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
    unexpected_wheel = sorted(
        name
        for name in names
        if not name.startswith("pysteam/")
        and not (name.startswith("pysteam_sdk-") and ".dist-info/" in name)
    )
    if unexpected_wheel:
        raise RuntimeError(f"unexpected wheel files: {unexpected_wheel}")

    print(f"Release archives contain only SDK files and metadata ({len(names)} wheel files).")


if __name__ == "__main__":
    check()
