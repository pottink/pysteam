"""Steam client update package archiving command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from pysteam.cli import _CONSOLE, _authenticate, _run, client_group
from pysteam.client import SteamClient
from pysteam.content.client_packages import ClientPackageArchiver


async def _client_archive(
    name: str,
    root: Path,
    account: str | None,
    anonymous: bool,
    package_format: str,
    max_downloads: int,
    as_json: bool,
) -> None:
    async with SteamClient(timeout=20, auto_reconnect=True) as steam:
        await _authenticate(
            steam,
            account=account,
            mafile=None,
            store_path=None,
            remember=False,
            anonymous=anonymous,
        )
        result = await ClientPackageArchiver(steam, root, max_downloads=max_downloads).archive(
            name, package_format=package_format
        )
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "channel": result.name,
                    "version": result.version,
                    "packages": result.packages,
                    "downloaded": result.downloaded,
                },
                indent=2,
            )
        )
    else:
        _CONSOLE.print(
            f"[green]Archived[/green] {result.name} version {result.version}: "
            f"{result.packages} packages ({result.downloaded} downloaded)"
        )


@client_group.command("archive", help="Preserve current Steam client update packages.")
def client_archive_command(
    name: Annotated[str, typer.Argument()] = "steam_client_win32",
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    package_format: Annotated[str, typer.Option("--format")] = "zip",
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(
        _client_archive(name, archive, account, anonymous, package_format, max_downloads, as_json),
        debug=False,
    )
