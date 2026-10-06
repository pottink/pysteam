"""Advance the SteamTracking schema pin and regenerate Python protobufs.

Run with ``uv run python scripts/update_protos.py``. The script leaves changes
uncommitted so a schema upgrade can be reviewed alongside generated code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = ROOT / "vendor" / "steam-protobufs"
GENERATOR = ROOT / "scripts" / "generate_protos.py"


def git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    if not SUBMODULE.is_dir():
        raise RuntimeError("SteamTracking submodule is absent; run git submodule update --init")
    affected = git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "vendor/steam-protobufs",
        "src/pysteam/proto",
    )
    if affected or git("status", "--porcelain", "--untracked-files=all", cwd=SUBMODULE):
        raise RuntimeError(
            "schema pin or generated protobufs have local changes; review them first"
        )

    previous = git("rev-parse", "HEAD", cwd=SUBMODULE)
    git("fetch", "--no-tags", "origin", "master", cwd=SUBMODULE)
    latest = git("rev-parse", "FETCH_HEAD", cwd=SUBMODULE)
    if latest != previous:
        git("checkout", "--detach", latest, cwd=SUBMODULE)
        subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(GENERATOR), "--check"], cwd=ROOT, check=True)
    print(f"SteamTracking/Protobufs: {previous} -> {latest}")
    if latest != previous:
        print("Review the submodule and generated code changes, then run the project checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
