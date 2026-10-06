"""Archive commands: online capture, offline inspection, and repair."""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Annotated

import msgspec
import typer
from rich import box
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TaskProgressColumn, TextColumn
from rich.table import Table

from pysteam.accounts.profiles import default_profile_dir
from pysteam.cli import (
    _CONSOLE,
    _archive_store,
    _authenticate,
    _command_error,
    _prompt_secret,
    _register_archive,
    _run,
    archive_group,
)
from pysteam.client import SteamClient
from pysteam.content.archive import ArchiveRegistry, ArchiveStore, ContentArchiver
from pysteam.errors import CDNError, CredentialStoreError, ProtocolError, SteamError


async def _archive_job(
    app_id: int,
    depot_ids: tuple[int, ...] | None,
    *,
    manifest_id: int | None,
    branch: str,
    root: Path,
    account: str | None,
    anonymous: bool,
    max_downloads: int,
    cpu_workers: int,
    as_json: bool = False,
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
        chosen = depot_ids
        if chosen is None:
            chosen = tuple(sorted(await steam.get_app_manifest_ids(app_id, branch=branch)))
        if not chosen:
            raise ProtocolError("PICS returned no depots for this app and branch")
        rows: list[dict[str, int]] = []
        for depot_id in chosen:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Depot " + str(depot_id)),
                BarColumn(),
                TaskProgressColumn(),
                console=_CONSOLE,
                transient=True,
                disable=as_json or not _CONSOLE.is_terminal,
            ) as progress:
                task = progress.add_task("download", total=1)

                def update_progress(done: int, total: int, task_id: TaskID = task) -> None:
                    progress.update(task_id, completed=done, total=max(total, 1))

                archiver = ContentArchiver(
                    steam,
                    store,
                    max_downloads=max_downloads,
                    cpu_workers=cpu_workers,
                    progress=update_progress,
                )
                try:
                    result = await archiver.archive_depot(
                        app_id, depot_id, manifest_id=manifest_id, branch=branch
                    )
                finally:
                    _register_archive(root)
            rows.append(
                {
                    "app_id": result.app_id,
                    "depot_id": result.depot_id,
                    "manifest_id": result.manifest_id,
                    "new_chunks": result.chunks_downloaded,
                    "reused_chunks": result.chunks_reused,
                    "bytes_downloaded": result.bytes_downloaded,
                }
            )
            if not as_json:
                _CONSOLE.print(
                    f"[green]Archived[/green] depot {result.depot_id} "
                    f"manifest {result.manifest_id}: {result.chunks_downloaded} new, "
                    f"{result.chunks_reused} reused chunks"
                )
        if as_json:
            typer.echo(json.dumps(rows, indent=2))


@archive_group.command("depot", help="Preserve one depot's raw manifest and encrypted chunks.")
def archive_depot_command(
    app_id: Annotated[int, typer.Argument(min=1)],
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest: Annotated[int | None, typer.Option("--manifest", min=1)] = None,
    branch: Annotated[str, typer.Option()] = "public",
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    cpu_workers: Annotated[int, typer.Option("--cpu-workers", min=0, max=32)] = 0,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    _run(
        _archive_job(
            app_id,
            (depot_id,),
            manifest_id=manifest,
            branch=branch,
            root=archive,
            account=account,
            anonymous=anonymous,
            max_downloads=max_downloads,
            cpu_workers=cpu_workers,
            as_json=as_json,
        ),
        debug=debug,
    )


@archive_group.command("app", help="Preserve every depot listed for an app branch.")
def archive_app_command(
    app_id: Annotated[int, typer.Argument(min=1)],
    branch: Annotated[str, typer.Option()] = "public",
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    cpu_workers: Annotated[int, typer.Option("--cpu-workers", min=0, max=32)] = 0,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    _run(
        _archive_job(
            app_id,
            None,
            manifest_id=None,
            branch=branch,
            root=archive,
            account=account,
            anonymous=anonymous,
            max_downloads=max_downloads,
            cpu_workers=cpu_workers,
            as_json=as_json,
        ),
        debug=debug,
    )


@archive_group.command("batch", help="Archive AppID,DepotID,ManifestID,Branch CSV rows.")
def archive_batch_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    cpu_workers: Annotated[int, typer.Option("--cpu-workers", min=0, max=32)] = 0,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            raw_rows = list(csv.DictReader(source))
        if not raw_rows or len(raw_rows) > 10000:
            raise ValueError("batch must contain between 1 and 10000 rows")
        rows: list[tuple[int, int, int | None, str]] = []
        for row in raw_rows:
            app_id = int(row["AppID"])
            depot_id = int(row["DepotID"])
            manifest = int(row["ManifestID"]) if row.get("ManifestID") else None
            branch = row.get("Branch") or "public"
            if app_id <= 0 or depot_id <= 0 or (manifest is not None and manifest <= 0):
                raise ValueError("batch contains a non-positive ID")
            rows.append((app_id, depot_id, manifest, branch))
        _run(
            _archive_batch(rows, archive, account, anonymous, max_downloads, cpu_workers, as_json),
            debug=debug,
        )
    except (OSError, KeyError, ValueError) as exc:
        _command_error(f"invalid batch file: {type(exc).__name__}")


async def _archive_batch(
    rows: list[tuple[int, int, int | None, str]],
    root: Path,
    account: str | None,
    anonymous: bool,
    max_downloads: int,
    cpu_workers: int,
    as_json: bool,
) -> None:
    store = await _archive_store(root)
    output: list[dict[str, int]] = []
    async with SteamClient(timeout=20, auto_reconnect=True) as steam:
        await _authenticate(
            steam,
            account=account,
            mafile=None,
            store_path=None,
            remember=False,
            anonymous=anonymous,
        )
        archiver = ContentArchiver(
            steam, store, max_downloads=max_downloads, cpu_workers=cpu_workers
        )
        for app_id, depot_id, manifest_id, branch in rows:
            try:
                result = await archiver.archive_depot(
                    app_id, depot_id, manifest_id=manifest_id, branch=branch
                )
            finally:
                _register_archive(root)
            output.append(
                {
                    "app_id": result.app_id,
                    "depot_id": result.depot_id,
                    "manifest_id": result.manifest_id,
                    "new_chunks": result.chunks_downloaded,
                    "reused_chunks": result.chunks_reused,
                }
            )
            if not as_json:
                _CONSOLE.print(
                    f"[green]Archived[/green] {result.app_id}/{result.depot_id}/"
                    f"{result.manifest_id}"
                )
    if as_json:
        typer.echo(json.dumps(output, indent=2))


@archive_group.command("list", help="List locally archived manifests.")
def archive_list_command(
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        records = ArchiveStore(archive, "unused").list()
        if as_json:
            typer.echo(json.dumps([msgspec.to_builtins(item) for item in records], indent=2))
            return
        table = Table(title="Steam archive", box=box.ROUNDED)
        for name in ("App", "Depot", "Manifest", "Branch", "State", "Chunks"):
            table.add_column(name)
        for item in records:
            table.add_row(
                str(item.app_id),
                str(item.depot_id),
                str(item.manifest_id),
                item.branch,
                "complete" if item.complete else "incomplete",
                str(item.chunks),
            )
        _CONSOLE.print(table)
    except (SteamError, OSError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


async def _archive_offline(
    operation: str,
    archive: Path,
    depot_id: int,
    manifest_id: int,
    *,
    old: int | None = None,
    destination: Path | None = None,
    files: tuple[str, ...] = (),
    overwrite: bool = False,
    as_json: bool = False,
) -> None:
    store = await _archive_store(archive)
    if operation == "inspect":
        manifest = store.manifest(depot_id, manifest_id)
        data: object = {
            "depot_id": manifest.depot_id,
            "manifest_id": manifest.manifest_id,
            "files": [{"name": item.name, "size": item.size} for item in manifest.files],
        }
    elif operation == "verify":
        checked, missing = await asyncio.to_thread(store.verify, depot_id, manifest_id)
        data = {"chunks_checked": checked, "missing_or_invalid": missing}
        if missing:
            raise CDNError(f"archive has {missing} missing or invalid chunks")
    elif operation == "extract":
        assert destination is not None
        paths = await asyncio.to_thread(
            store.extract,
            depot_id,
            manifest_id,
            destination,
            files=files or None,
            overwrite=overwrite,
        )
        data = {"files_extracted": len(paths), "output": str(destination)}
    else:
        assert old is not None
        diff = store.diff(depot_id, old, manifest_id)
        data = {"added": diff.added, "removed": diff.removed, "changed": diff.changed}
    if as_json:
        typer.echo(json.dumps(data, indent=2))
    else:
        _CONSOLE.print(data)


@archive_group.command("inspect", help="Inspect an archived manifest and its files.")
def archive_inspect_command(
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest_id: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(_archive_offline("inspect", archive, depot_id, manifest_id, as_json=as_json), debug=False)


@archive_group.command("verify", help="Verify every archived chunk against its manifest.")
def archive_verify_command(
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest_id: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(_archive_offline("verify", archive, depot_id, manifest_id, as_json=as_json), debug=False)


@archive_group.command("extract", help="Extract verified files from a local archive.")
def archive_extract_command(
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest_id: Annotated[int, typer.Argument(min=1)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)] = Path("extract"),
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    files: Annotated[list[str] | None, typer.Option("--file")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    _run(
        _archive_offline(
            "extract",
            archive,
            depot_id,
            manifest_id,
            destination=output,
            files=tuple(files or ()),
            overwrite=overwrite,
        ),
        debug=False,
    )


@archive_group.command("diff", help="Compare two archived depot manifests.")
def archive_diff_command(
    depot_id: Annotated[int, typer.Argument(min=1)],
    old: Annotated[int, typer.Argument(min=1)],
    new: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _run(_archive_offline("diff", archive, depot_id, new, old=old, as_json=as_json), debug=False)


@archive_group.command("repair", help="Refetch missing or corrupt chunks from Steam.")
def archive_repair_command(
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest_id: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    account: Annotated[str | None, typer.Option()] = None,
    anonymous: Annotated[bool, typer.Option("--anonymous")] = False,
) -> None:
    records = ArchiveStore(archive, "unused").list()
    record = next(
        (item for item in records if (item.depot_id, item.manifest_id) == (depot_id, manifest_id)),
        None,
    )
    if record is None:
        _command_error("archive manifest is not recorded")
    _run(
        _archive_job(
            record.app_id,
            (depot_id,),
            manifest_id=manifest_id,
            branch=record.branch,
            root=archive,
            account=account,
            anonymous=anonymous,
            max_downloads=8,
            cpu_workers=0,
        ),
        debug=False,
    )


@archive_group.command("rekey", help="Change the password for a portable archive key capsule.")
def archive_rekey_command(
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
) -> None:
    try:
        if archive.resolve() in ArchiveRegistry(default_profile_dir()).list():
            raise CredentialStoreError(
                "this archive is registered with the local vault; use vault change-password"
            )
        old = _prompt_secret("Current archive password")
        new = _prompt_secret("New archive password", confirmation=True)
        ArchiveStore(archive, old).rekey(new)
        _CONSOLE.print("[green]Archive key capsule rekeyed[/green]")
    except (SteamError, ValueError, OSError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


def _depot_key_for_import(store: ArchiveStore, depot_id: int) -> bytes:
    try:
        return store.get_key(depot_id)
    except CredentialStoreError as exc:
        if str(exc) != "archive has no key for this depot":
            raise
    value = _prompt_secret(f"Depot {depot_id} key (64 hex characters)")
    try:
        key = bytes.fromhex(value)
    except ValueError:
        raise CDNError("depot key must be 64 hex characters") from None
    if len(key) != 32:
        raise CDNError("depot key must be 64 hex characters")
    store.save_key(depot_id, key)
    return key


async def _import_legacy(
    source: Path, root: Path, app_id: int, depot_id: int, manifest_id: int
) -> None:
    store = await _archive_store(root)
    key = _depot_key_for_import(store, depot_id)
    record = await asyncio.to_thread(
        store.import_legacy,
        source,
        app_id=app_id,
        depot_id=depot_id,
        manifest_id=manifest_id,
        key=key,
    )
    _register_archive(root)
    _CONSOLE.print(
        f"Imported depot {depot_id}: "
        + ("[green]complete[/green]" if record.complete else "[yellow]incomplete[/yellow]")
    )


@archive_group.command("import", help="Import legacy SHA chunk folders and a manifest ZIP.")
def archive_import_command(
    source: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    app_id: Annotated[int, typer.Argument(min=1)],
    depot_id: Annotated[int, typer.Argument(min=1)],
    manifest_id: Annotated[int, typer.Argument(min=1)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
) -> None:
    _run(_import_legacy(source, archive, app_id, depot_id, manifest_id), debug=False)
