"""Workshop discovery and preservation commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.table import Table

from pysteam.cli import (
    _CONSOLE,
    _archive_store,
    _authenticate,
    _register_archive,
    _run,
    workshop_group,
)
from pysteam.client import SteamClient
from pysteam.content.archive import ContentArchiver


async def _workshop_query(
    app_id: int,
    search: str,
    page: int,
    per_page: int,
    account: str | None,
    anonymous: bool,
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
        result = await steam.workshop.query(app_id, search=search, page=page, per_page=per_page)
    rows = [
        {
            "published_file_id": item.published_file_id,
            "app_id": item.app_id,
            "title": item.title,
            "file_size": item.file_size,
            "steampipe": bool(item.manifest_id and not item.file_url),
        }
        for item in result.items
    ]
    if as_json:
        typer.echo(json.dumps({"total": result.total, "items": rows}, indent=2))
    else:
        table = Table(title=f"Workshop · {result.total} results", box=box.ROUNDED)
        for title in ("ID", "Title", "Bytes", "SteamPipe"):
            table.add_column(title)
        for row in rows:
            table.add_row(
                str(row["published_file_id"]),
                str(row["title"]),
                str(row["file_size"]),
                str(row["steampipe"]),
            )
        _CONSOLE.print(table)


@workshop_group.command("query", help="Search published Workshop files for an app.")
def workshop_query_command(
    app_id: Annotated[int, typer.Argument(min=1)],
    search: Annotated[str, typer.Option("--search")] = "",
    page: Annotated[int, typer.Option(min=1)] = 1,
    per_page: Annotated[int, typer.Option("--per-page", min=1, max=100)] = 20,
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(
        _workshop_query(app_id, search, page, per_page, account, anonymous, as_json),
        debug=False,
    )


async def _workshop_archive(
    published_file_id: int,
    root: Path,
    account: str | None,
    anonymous: bool,
    max_downloads: int,
    cpu_workers: int,
) -> None:
    store = await _archive_store(root)
    async with SteamClient(timeout=20, auto_reconnect=True) as steam:
        await _authenticate(
            steam,
            account=account,
            mafile=None,
            store_path=None,
            remember=False,
            anonymous=anonymous,
        )
        result = await ContentArchiver(
            steam, store, max_downloads=max_downloads, cpu_workers=cpu_workers
        ).archive_workshop(published_file_id)
        _register_archive(root)
    _CONSOLE.print(
        f"[green]Archived[/green] Workshop item {published_file_id} "
        f"({result.source}, {result.bytes_downloaded} bytes downloaded)"
    )


@workshop_group.command("archive", help="Preserve a Workshop item and its content.")
def workshop_archive_command(
    published_file_id: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    cpu_workers: Annotated[int, typer.Option("--cpu-workers", min=0, max=32)] = 0,
) -> None:
    _run(
        _workshop_archive(
            published_file_id, archive, account, anonymous, max_downloads, cpu_workers
        ),
        debug=False,
    )
