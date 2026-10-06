"""Public app inspection, SteamID, and connectivity commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pysteam.cli import _CONSOLE, _command_error, _doctor, _inspect_app, _run, main, steamid
from pysteam.ids import SteamID


@main.command(help="Show the public PICS response for one Steam app ID.")
def app(
    app_id: Annotated[int, typer.Argument(min=1, max=0xFFFFFFFF)],
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the complete parsed PICS response.")
    ] = False,
    debug: Annotated[
        bool, typer.Option("--debug", help="Show redacted CM and PICS protocol logs.")
    ] = False,
) -> None:
    _run(_inspect_app(app_id, as_json=as_json), debug=debug)


@steamid.command("parse", help="Show the components of a SteamID64, Steam2, or Steam3 ID.")
def steamid_parse(value: Annotated[str, typer.Argument()]) -> None:
    try:
        parsed = SteamID.parse(value)
    except ValueError as exc:
        _command_error(str(exc))
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    for label, part in (
        ("SteamID64", int(parsed)),
        ("Account ID", parsed.account_id),
        ("Universe", parsed.universe),
        ("Account type", parsed.account_type),
        ("Instance", parsed.instance),
    ):
        table.add_row(label, str(part))
    _CONSOLE.print(Panel(table, title="SteamID", border_style="cyan", expand=False))


@main.command(help="Check CM discovery, anonymous logon, and PICS.")
def doctor(
    app_id: Annotated[int, typer.Option(min=1, max=0xFFFFFFFF)] = 220,
    debug: Annotated[bool, typer.Option("--debug", help="Show redacted protocol logs.")] = False,
) -> None:
    _run(_doctor(app_id), debug=debug)
