"""PICS app metadata snapshot commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.table import Table

from pysteam.cli import _CONSOLE, _authenticate, _run, appinfo_group
from pysteam.client import SteamClient
from pysteam.content.archive import ArchiveStore


async def _appinfo_snapshot(
    app_ids: tuple[int, ...],
    *,
    root: Path,
    update: bool,
    as_json: bool,
    account: str | None,
    anonymous: bool,
) -> None:
    store = ArchiveStore(root, "metadata-only")
    selected = app_ids or (store.appinfo_ids() if update else ())
    if not selected:
        raise ValueError("provide AppIDs or take an initial snapshot first")
    rows: list[dict[str, object]] = []
    async with SteamClient(timeout=20, auto_reconnect=True) as steam:
        await _authenticate(
            steam,
            account=account,
            mafile=None,
            store_path=None,
            remember=False,
            anonymous=anonymous,
        )
        for offset in range(0, len(selected), 100):
            batch = selected[offset : offset + 100]
            access = await steam.get_access_tokens(app_ids=batch)
            info = await steam.get_product_info(app_ids=batch, app_tokens=access.apps)
            for app_id in batch:
                raw = info.apps.get(app_id)
                if raw is None:
                    rows.append({"app_id": app_id, "status": "unavailable"})
                    continue
                digest, changed = store.save_appinfo(app_id, raw)
                rows.append(
                    {
                        "app_id": app_id,
                        "sha256": digest,
                        "status": "saved" if changed else "unchanged",
                    }
                )
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
    else:
        table = Table(title="App metadata snapshots", box=box.ROUNDED)
        for heading in ("AppID", "Status", "SHA-256"):
            table.add_column(heading)
        for row in rows:
            table.add_row(str(row["app_id"]), str(row["status"]), str(row.get("sha256", "")))
        _CONSOLE.print(table)


@appinfo_group.command("snapshot", help="Save original PICS app metadata bytes.")
def appinfo_snapshot_command(
    app_ids: Annotated[list[int], typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(
        _appinfo_snapshot(
            tuple(app_ids),
            root=archive,
            update=False,
            as_json=as_json,
            account=account,
            anonymous=anonymous,
        ),
        debug=False,
    )


@appinfo_group.command("update", help="Refresh all saved app metadata or selected AppIDs.")
def appinfo_update_command(
    app_ids: Annotated[list[int] | None, typer.Argument()] = None,
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(
        _appinfo_snapshot(
            tuple(app_ids or ()),
            root=archive,
            update=True,
            as_json=as_json,
            account=account,
            anonymous=anonymous,
        ),
        debug=False,
    )
