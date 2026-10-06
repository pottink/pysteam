"""Saved account, Steam Guard, and login commands."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pysteam.accounts.credentials import EncryptedFileCredentialStore
from pysteam.accounts.guard import guard_code
from pysteam.accounts.migration import migrate_legacy_data
from pysteam.accounts.profiles import ProfileRegistry, default_profile_dir, legacy_profile_dir
from pysteam.cli import (
    _CONSOLE,
    _command_error,
    _initialize_vault,
    _load_authenticator,
    _login,
    _register_account,
    _run,
    _store_passphrase,
    account_group,
    guard,
    main,
)
from pysteam.errors import MaFileError, ProfileError, SteamError


@account_group.command("add", help="Save an account from a maFile or enroll a new authenticator.")
def account_add(
    name: Annotated[str, typer.Argument()],
    mafile: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="Import an active maFile.")
    ] = None,
    enroll: Annotated[
        bool, typer.Option("--enroll", help="Create and activate a new Steam Guard maFile.")
    ] = False,
    resume_enrollment: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Resume an incomplete enrollment."),
    ] = None,
    backup_dir: Annotated[Path | None, typer.Option(file_okay=False)] = None,
    fresh: Annotated[
        bool, typer.Option("--fresh", help="Skip an existing legacy credential store.")
    ] = False,
    debug: Annotated[
        bool, typer.Option("--debug", help="Show redacted authentication logs.")
    ] = False,
) -> None:
    _run(
        _register_account(
            name,
            mafile=mafile,
            enroll=enroll,
            resume_enrollment=resume_enrollment,
            backup_dir=backup_dir,
            fresh=fresh,
        ),
        debug=debug,
    )


@account_group.command("list", help="Show saved accounts and the selected default.")
def account_list() -> None:
    try:
        registry = ProfileRegistry()
        profiles = registry.list()
        selected = registry.default()
        if not profiles:
            _CONSOLE.print(
                Panel(
                    "No accounts saved yet.\nAdd one with [bold]pysteam account add NAME[/bold].",
                    title="Steam accounts",
                    border_style="cyan",
                    expand=False,
                )
            )
            return
        table = Table(
            title=f"Steam accounts ({len(profiles)})",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
            caption="Use 'pysteam account use NAME' to change the default.",
            caption_style="dim",
            expand=False,
        )
        table.add_column("Account", overflow="fold", min_width=12)
        table.add_column("SteamID", style="dim", no_wrap=True)
        table.add_column("maFile backup", justify="center", no_wrap=True)
        table.add_column("Selection", no_wrap=True)
        for profile in profiles:
            is_default = selected == profile
            table.add_row(
                Text(profile.account_name, style="bold green" if is_default else "bold"),
                str(profile.steam_id),
                Text("Yes", style="green") if profile.mafile_path else Text("No", style="dim"),
                Text("* Default", style="bold green") if is_default else Text("-", style="dim"),
            )
        _CONSOLE.print(table)
    except ProfileError as exc:
        _command_error(str(exc))


@account_group.command("show", help="Show one account's non-secret profile paths.")
def account_show(name: Annotated[str, typer.Argument()]) -> None:
    try:
        registry = ProfileRegistry()
        profile = registry.select(name)
        _CONSOLE.print(f"Account: {profile.account_name}")
        _CONSOLE.print(f"SteamID: {profile.steam_id}")
        _CONSOLE.print(f"Encrypted store: {profile.store_path}")
        _CONSOLE.print(f"maFile backup: {profile.mafile_path or 'none'}")
        _CONSOLE.print(f"Default: {'yes' if registry.default() == profile else 'no'}")
    except ProfileError as exc:
        _command_error(str(exc))


@account_group.command("use", help="Select the default account for login and depot commands.")
def account_use(name: Annotated[str, typer.Argument()]) -> None:
    try:
        profile = ProfileRegistry().use(name)
        _CONSOLE.print(f"Default account: {profile.account_name}")
    except ProfileError as exc:
        _command_error(str(exc))


@account_group.command("remove", help="Remove a saved account and its encrypted credential store.")
def account_remove(
    name: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation.")] = False,
) -> None:
    try:
        registry = ProfileRegistry()
        profile = registry.select(name)
        typer.echo(f"Account: {profile.account_name}")
        typer.echo(f"Encrypted credential store to remove: {profile.store_path}")
        if profile.mafile_path is not None:
            typer.echo(f"maFile backup to keep: {profile.mafile_path}")
        if not yes and not typer.confirm("Remove this saved account?", default=False):
            typer.echo("Account removal cancelled.")
            return
        registry.remove(name)
        typer.echo(f"Removed account: {profile.account_name}")
        selected = registry.default()
        if selected is not None:
            typer.echo(f"Default account: {selected.account_name}")
    except ProfileError as exc:
        _command_error(str(exc))


@account_group.command("migrate", help="Move old user-config account data into this directory.")
def account_migrate(
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation.")] = False,
) -> None:
    typer.echo(f"From: {legacy_profile_dir()}")
    typer.echo(f"To:   {default_profile_dir()}")
    if not yes and not typer.confirm("Move saved account data?", default=False):
        typer.echo("Account migration cancelled.")
        return
    try:
        target, old_removed = migrate_legacy_data()
    except ProfileError as exc:
        _command_error(str(exc))
    typer.echo(f"Account data ready: {target}")
    if not old_removed:
        typer.echo("The old directory remains; check the new data before removing it.")


@guard.command("code", help="Generate the current code from a saved account or maFile.")
def guard_code_command(
    account: Annotated[
        str | None, typer.Option(help="Saved account; default: selected account.")
    ] = None,
    mafile: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Explicit existing maFile."),
    ] = None,
) -> None:
    try:
        if mafile is not None:
            name, credentials, _ = _load_authenticator(mafile)
            if account is not None and account.casefold() != name.casefold():
                raise ProfileError("maFile account does not match the requested account")
        else:
            asyncio.run(_initialize_vault())
            profile = ProfileRegistry().select(account)
            store = EncryptedFileCredentialStore(profile.store_path, _store_passphrase())
            saved = asyncio.run(store.load(profile.account_name))
            if saved is None or saved.steam_id != profile.steam_id:
                raise ProfileError("saved account credentials are missing or mismatched")
            credentials = saved
        if credentials.shared_secret is None:
            raise MaFileError("account has no shared secret")
        now = int(time.time())
        typer.echo(guard_code(credentials.shared_secret, timestamp=now))
        _CONSOLE.print(f"[dim]Expires in {30 - now % 30}s[/dim]")
    except (SteamError, ValueError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


@main.command(help="Sign in with a saved account or explicit credentials.")
def login(
    account: Annotated[str | None, typer.Argument()] = None,
    mafile: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="Existing Steam Guard maFile.")
    ] = None,
    remember: Annotated[
        bool, typer.Option("--remember", help="Save renewed login data in an encrypted store.")
    ] = False,
    store: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Use this encrypted credential store.")
    ] = None,
    debug: Annotated[bool, typer.Option("--debug", help="Show redacted protocol logs.")] = False,
) -> None:
    _run(_login(account, mafile=mafile, store=store, remember=remember), debug=debug)
