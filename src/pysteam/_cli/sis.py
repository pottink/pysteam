"""Steam SIS backup inspection, import, export, and repacking commands."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from pysteam._cli.archive import _depot_key_for_import
from pysteam.cli import _CONSOLE, _archive_store, _command_error, _register_archive, _run, sis_group
from pysteam.content.sis import export_sis, import_sis, inspect_csm, inspect_sis, repack_sis
from pysteam.errors import CDNError, SteamError


@sis_group.command("inspect", help="Inspect a sku.sis backup or standalone CSM index.")
def sis_inspect_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        if path.suffix.lower() == ".csm":
            container = inspect_csm(path)
            data: object = {
                "depot_id": container.depot_id,
                "encrypted": container.encrypted,
                "chunks": len(container.entries),
            }
        else:
            backup = inspect_sis(path)
            data = {
                "app_id": backup.app_id,
                "manifests": backup.manifests,
                "containers": [
                    {
                        "depot_id": item.depot_id,
                        "chunks": len(item.entries),
                        "encrypted": item.encrypted,
                    }
                    for item in backup.containers
                ],
            }
        if as_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            _CONSOLE.print(data)
    except (SteamError, OSError, ValueError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


async def _sis_import(path: Path, root: Path) -> None:
    if root.resolve().is_relative_to(path.parent.resolve()):
        raise CDNError("archive destination must be outside the SIS source directory")
    store = await _archive_store(root)
    backup = inspect_sis(path)
    for depot_id, manifest_id in backup.manifests.items():
        key = _depot_key_for_import(store, depot_id)
        try:
            store.manifest(depot_id, manifest_id)
        except CDNError:
            sidecar = path.parent / "manifests" / str(depot_id) / f"{manifest_id}.manifest"
            if not sidecar.is_file() or sidecar.stat().st_size > 64 * 1024 * 1024:
                raise CDNError("SIS import needs the original depot manifest") from None
            from pysteam.content.cdn import parse_manifest

            manifest = parse_manifest(sidecar.read_bytes(), depot_key=key)
            if (manifest.depot_id, manifest.manifest_id) != (depot_id, manifest_id):
                raise CDNError("SIS manifest sidecar identity mismatch") from None
            store.save_manifest(manifest, app_id=backup.app_id, branch="public")
    result = await asyncio.to_thread(import_sis, store, backup)
    _register_archive(root)
    _CONSOLE.print(result)


@sis_group.command("import", help="Import CSD/CSM chunks using original manifests and depot keys.")
def sis_import_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
) -> None:
    _run(_sis_import(path, archive), debug=False)


async def _sis_export(root: Path, app_id: int, output: Path, overwrite: bool) -> None:
    store = await _archive_store(root)
    backup = await asyncio.to_thread(export_sis, store, app_id, output, overwrite=overwrite)
    _CONSOLE.print(f"[green]Exported[/green] {len(backup.manifests)} depots to {backup.path}")


@sis_group.command("export", help="Export complete archived depots to a Steam SIS backup.")
def sis_export_command(
    app_id: Annotated[int, typer.Argument(min=1)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)] = Path("sis-export"),
    archive: Annotated[Path, typer.Option("--archive", file_okay=False)] = Path("steam-archive"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    _run(_sis_export(archive, app_id, output, overwrite), debug=False)


@sis_group.command("repack", help="Normalize an encrypted SIS backup without changing its source.")
def sis_repack_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)] = Path("sis-repacked"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    try:
        backup = repack_sis(inspect_sis(path), output, overwrite=overwrite)
        _CONSOLE.print(f"[green]Repacked[/green] {len(backup.containers)} containers")
    except (SteamError, OSError, ValueError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")
