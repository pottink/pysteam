"""Standalone maFile login check; saved profiles use `pysteam login`."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pysteam import (
    EncryptedFileCredentialStore,
    LoginCredentials,
    SteamClient,
    SteamError,
    default_profile_dir,
    load_mafile,
)
from pysteam._terminal import enable_debug_logging
from pysteam.accounts.profiles import ensure_private_directory

_CONSOLE = Console(highlight=False)


def _status(label: str, message: str, *, style: str) -> None:
    line = Text()
    line.append(f" {label:<4} ", style=style)
    line.append("  ")
    line.append(message)
    _CONSOLE.print(line)


def _ask_secret(label: str) -> str:
    return _CONSOLE.input(Text(f"{label}: ", style="bold cyan"), password=True)


class _DiagnosticSteamClient(SteamClient):
    async def _logon_refresh_token(
        self, refresh_token: str, steam_id: int, account_name: str
    ) -> None:
        _status("STEP", "Guard authentication completed; submitting CM logon", style="cyan")
        await super()._logon_refresh_token(refresh_token, steam_id, account_name)


def _enable_debug_logging() -> logging.Handler:
    return enable_debug_logging(_CONSOLE)


def _default_store_path(steam_id: int) -> Path:
    ensure_private_directory(default_profile_dir())
    return default_profile_dir() / "credentials" / f"{steam_id}.bin"


async def _run(mafile_path: Path, *, remember: bool, store_path: Path | None) -> None:
    _CONSOLE.print(Panel.fit("Steam Guard login check", border_style="cyan"))
    _status("STEP", "Unlocking maFile", style="cyan")
    passphrase = _ask_secret("maFile backup passphrase")
    imported = load_mafile(mafile_path, passphrase=passphrase)
    _status("OK", "maFile validated", style="green")
    store = None
    if remember:
        steam_id = imported.credentials.steam_id
        if steam_id is None:
            raise ValueError("maFile is missing its SteamID")
        store = EncryptedFileCredentialStore(
            store_path or _default_store_path(steam_id), passphrase
        )
    saved = await store.load(imported.account_name) if store is not None else None
    credentials = imported.credentials.with_fallback(saved)
    if not credentials.refresh_token and not credentials.password:
        password = _ask_secret("Steam password (first login)" if remember else "Steam password")
        if not password:
            raise ValueError("a Steam password is required")
        credentials = credentials.with_fallback(LoginCredentials(password=password))
    else:
        _status("OK", "Encrypted login credentials available", style="green")
    _status("STEP", "Connecting to Steam", style="cyan")
    async with _DiagnosticSteamClient(timeout=20, auto_reconnect=False) as client:
        _status("OK", "CM WebSocket connected", style="green")
        _status("STEP", "Authenticating with Steam Guard", style="cyan")
        result = await client.login_auto(
            imported.account_name,
            credentials=credentials,
            store=store,
        )
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="dim", no_wrap=True)
        summary.add_column(overflow="fold")
        summary.add_row("SteamID", str(result.tokens.steam_id))
        summary.add_row("Method", result.method)
        if store is not None:
            summary.add_row("Encrypted store", Text(str(store.path)))
        _CONSOLE.print(Panel(summary, title="Login succeeded", border_style="green", expand=False))


main = typer.Typer(help="Test login with an existing Steam Guard maFile.", add_completion=False)


@main.command()
def login(
    mafile: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    remember: Annotated[
        bool, typer.Option("--remember", help="Encrypt credentials for later logins.")
    ] = False,
    store: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Credential store path.")
    ] = None,
    debug: Annotated[
        bool, typer.Option("--debug", help="Show redacted CM and authentication progress.")
    ] = False,
) -> None:
    if store is not None and not remember:
        raise typer.BadParameter("--store requires --remember")
    if debug:
        _enable_debug_logging()
    try:
        asyncio.run(_run(mafile, remember=remember, store_path=store))
    except (SteamError, ValueError) as exc:
        _status("FAIL", f"{type(exc).__name__}: {exc}", style="bold red")
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    main()
