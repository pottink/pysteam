"""Install the built wheel in an isolated uv environment and import its public API."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    options = parser.parse_args()
    wheels = list((ROOT / "dist").glob("pysteam_sdk-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("expected exactly one built pysteam-sdk wheel")
    subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--isolated",
            "--python",
            options.python,
            "--with",
            str(wheels[0]),
            "python",
            "-c",
            "import pysteam; assert pysteam.SteamClient and pysteam.CDNClient",
        ],
        check=True,
        cwd=ROOT,
    )


if __name__ == "__main__":
    main()
