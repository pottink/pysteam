"""Direct depot listing and file download commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pysteam.cli import _depot_download, _depot_list, _run, depot


@depot.command("list", help="List files in a depot manifest.")
def depot_list(
    app_id: Annotated[int, typer.Argument(min=1, max=0xFFFFFFFF)],
    depot_id: Annotated[int, typer.Argument(min=1, max=0xFFFFFFFF)],
    manifest_id: Annotated[
        int | None,
        typer.Option(
            "--manifest", min=1, max=0xFFFFFFFFFFFFFFFF, help="Manifest ID; default: PICS branch."
        ),
    ] = None,
    branch: Annotated[str, typer.Option()] = "public",
    account: Annotated[
        str | None, typer.Option(help="Steam account for authenticated access.")
    ] = None,
    mafile: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="Existing Steam Guard maFile.")
    ] = None,
    store: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Encrypted credential store.")
    ] = None,
    anonymous: Annotated[
        bool,
        typer.Option("--anonymous", help="Use anonymous access instead of the default account."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print file metadata as JSON.")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show redacted protocol logs.")] = False,
) -> None:
    _run(
        _depot_list(
            app_id, depot_id, manifest_id, branch, account, mafile, store, as_json, anonymous
        ),
        debug=debug,
    )


@depot.command("download", help="Download selected files with CDN integrity checks.")
def depot_download(
    app_id: Annotated[int, typer.Argument(min=1, max=0xFFFFFFFF)],
    depot_id: Annotated[int, typer.Argument(min=1, max=0xFFFFFFFF)],
    files: Annotated[
        list[str] | None, typer.Option("--file", help="Manifest path; repeat.")
    ] = None,
    all_files: Annotated[bool, typer.Option("--all", help="Download the whole depot.")] = False,
    include: Annotated[list[str] | None, typer.Option("--include", help="Glob filter.")] = None,
    exclude: Annotated[list[str] | None, typer.Option("--exclude", help="Glob filter.")] = None,
    max_downloads: Annotated[int, typer.Option("--max-downloads", min=1, max=64)] = 8,
    output: Annotated[Path, typer.Option(file_okay=False)] = Path("downloads"),
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace existing destination files.")
    ] = False,
    manifest_id: Annotated[
        int | None,
        typer.Option(
            "--manifest", min=1, max=0xFFFFFFFFFFFFFFFF, help="Manifest ID; default: PICS branch."
        ),
    ] = None,
    branch: Annotated[str, typer.Option()] = "public",
    account: Annotated[
        str | None, typer.Option(help="Steam account for authenticated access.")
    ] = None,
    mafile: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="Existing Steam Guard maFile.")
    ] = None,
    store: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Encrypted credential store.")
    ] = None,
    anonymous: Annotated[
        bool,
        typer.Option("--anonymous", help="Use anonymous access instead of the default account."),
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show redacted protocol logs.")] = False,
) -> None:
    _run(
        _depot_download(
            app_id,
            depot_id,
            manifest_id,
            branch,
            account,
            mafile,
            store,
            tuple(files or ()),
            output,
            overwrite,
            anonymous,
            all_files=all_files,
            includes=tuple(include or ()),
            excludes=tuple(exclude or ()),
            max_downloads=max_downloads,
        ),
        debug=debug,
    )
