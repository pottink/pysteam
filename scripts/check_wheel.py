"""Install the built wheel in an isolated uv environment and import its public API."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]


main = typer.Typer(help="Install the built wheel and check imports.", add_completion=False)


@main.command()
def check(
    python_version: Annotated[
        str, typer.Option("--python", help="Python version or interpreter path.")
    ],
) -> None:
    wheels = list((ROOT / "dist").glob("pysteam_sdk-*.whl"))
    if len(wheels) != 1:
        typer.echo("Error: expected exactly one built pysteam-sdk wheel", err=True)
        raise typer.Exit(code=1)
    uv_run = [
        "uv",
        "run",
        "--no-project",
        "--isolated",
        "--python",
        python_version,
        "--with",
        str(wheels[0]),
    ]
    subprocess.run(
        [
            *uv_run,
            "python",
            "-c",
            "import pysteam as p; "
            "assert p.GuardEnrollmentClient and p.load_mafile and p.ProfileRegistry; "
            "assert p.Vault and p.ArchiveStore and p.ContentArchiver; "
            "assert p.WorkshopClient and p.ClientPackageArchiver",
        ],
        check=True,
        cwd=ROOT,
    )
    subprocess.run([*uv_run, "pysteam", "app", "--help"], check=True, cwd=ROOT)
    subprocess.run([*uv_run, "pysteam", "account", "add", "--help"], check=True, cwd=ROOT)
    subprocess.run([*uv_run, "pysteam", "login", "--help"], check=True, cwd=ROOT)
    subprocess.run([*uv_run, "pysteam", "depot", "download", "--help"], check=True, cwd=ROOT)
    for group in ("vault", "archive", "appinfo", "workshop", "client", "sis"):
        subprocess.run(
            [*uv_run, "pysteam", group, "--help"],
            check=True,
            cwd=ROOT,
            capture_output=True,
        )
    for group, commands in {
        "vault": ("status", "change-password"),
        "archive": (
            "app",
            "depot",
            "batch",
            "list",
            "inspect",
            "verify",
            "repair",
            "extract",
            "diff",
            "import",
            "rekey",
        ),
        "appinfo": ("snapshot", "update"),
        "workshop": ("query", "archive"),
        "client": ("archive",),
        "sis": ("inspect", "import", "export", "repack"),
    }.items():
        for command in commands:
            subprocess.run(
                [*uv_run, "pysteam", group, command, "--help"],
                check=True,
                cwd=ROOT,
                capture_output=True,
            )
    subprocess.run([*uv_run, "pysteam", "steamid", "parse", "STEAM_0:1:4"], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
