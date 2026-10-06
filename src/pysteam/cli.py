"""The installed ``pysteam`` command. Protocol logging stays redacted."""

from __future__ import annotations

import asyncio
import csv
import fnmatch
import json
import time
import uuid
from collections.abc import Coroutine
from pathlib import Path
from typing import Annotated, Any, NoReturn
from urllib.parse import urlsplit

import msgspec
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text

from pysteam._terminal import enable_debug_logging
from pysteam.archive import ArchiveRegistry, ArchiveStore, ContentArchiver
from pysteam.auth import GuardChallenge, LoginResult
from pysteam.cdn import DepotFile, DepotManifest
from pysteam.client import SteamClient
from pysteam.clientpackages import ClientPackageArchiver
from pysteam.credentials import EncryptedFileCredentialStore, LoginCredentials
from pysteam.errors import (
    CDNError,
    CDNHTTPError,
    CredentialStoreError,
    MaFileError,
    ProfileError,
    ProtocolError,
    SteamError,
    SteamResultError,
    TransportError,
)
from pysteam.guard import guard_code
from pysteam.guard_enrollment import GuardEnrollmentClient
from pysteam.ids import SteamID
from pysteam.mafile import load_mafile
from pysteam.migration import migrate_legacy_data
from pysteam.pics import KVValue, extract_manifest_ids
from pysteam.profiles import (
    ProfileRegistry,
    SavedProfile,
    default_profile_dir,
    ensure_private_directory,
    legacy_profile_dir,
)
from pysteam.sis import export_sis, import_sis, inspect_csm, inspect_sis, repack_sis
from pysteam.vault import Vault, vault_passphrase

_CONSOLE = Console(highlight=False)
main = typer.Typer(
    help="Steam authentication, app metadata, and content preservation.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
steamid = typer.Typer(help="Parse SteamID representations.", no_args_is_help=True)
guard = typer.Typer(help="Steam Guard utilities.", no_args_is_help=True)
account_group = typer.Typer(help="Register and manage saved Steam accounts.", no_args_is_help=True)
depot = typer.Typer(help="Inspect and download Steam depot files.", no_args_is_help=True)
vault_group = typer.Typer(help="Manage the protected local vault.", no_args_is_help=True)
archive_group = typer.Typer(help="Preserve and restore Steam content.", no_args_is_help=True)
appinfo_group = typer.Typer(help="Archive Steam app metadata.", no_args_is_help=True)
workshop_group = typer.Typer(help="Inspect and archive Workshop content.", no_args_is_help=True)
client_group = typer.Typer(help="Archive Steam client packages.", no_args_is_help=True)
sis_group = typer.Typer(help="Import and export Steam backup containers.", no_args_is_help=True)
main.add_typer(steamid, name="steamid")
main.add_typer(guard, name="guard")
main.add_typer(account_group, name="account")
main.add_typer(depot, name="depot")
main.add_typer(vault_group, name="vault")
main.add_typer(archive_group, name="archive")
main.add_typer(appinfo_group, name="appinfo")
main.add_typer(workshop_group, name="workshop")
main.add_typer(client_group, name="client")
main.add_typer(sis_group, name="sis")

_ACTIVE_VAULT: Vault | None = None
_ACTIVE_PASSWORD: str | None = None


def _command_error(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _pause(message: str) -> None:
    _CONSOLE.input(f"{message}. Press Enter to continue.")


def _field(parent: dict[str, KVValue], key: str) -> str:
    value = parent.get(key)
    return value if isinstance(value, str) else "unknown"


def _show_summary(app_id: int, app_info: dict[str, KVValue]) -> None:
    common = app_info.get("common")
    details = common if isinstance(common, dict) else {}
    depots = app_info.get("depots")
    manifests = extract_manifest_ids(app_info) if isinstance(depots, dict) else {}

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim", no_wrap=True)
    summary.add_column(overflow="fold")
    summary.add_row("App ID", str(app_id))
    summary.add_row("Name", Text(_field(details, "name")))
    summary.add_row("Type", Text(_field(details, "type")))
    summary.add_row("PICS fields", str(len(app_info)))
    summary.add_row("Public manifests", str(len(manifests)))
    _CONSOLE.print(Panel(summary, title="PICS app info", border_style="cyan", expand=False))

    if manifests:
        table = Table(title="Public depot manifests", box=None)
        table.add_column("Depot ID", justify="right")
        table.add_column("Manifest ID", justify="right")
        for depot_id, manifest_id in sorted(manifests.items()):
            table.add_row(str(depot_id), str(manifest_id))
        _CONSOLE.print(table)


async def _inspect_app(app_id: int, *, as_json: bool) -> None:
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        await client.login_anonymous()
        app_info = await client.get_app_info(app_id)
    if as_json:
        typer.echo(json.dumps(app_info, indent=2))
    else:
        _show_summary(app_id, app_info)


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


def _run(task: Coroutine[Any, Any, None], *, debug: bool) -> None:
    if debug:
        enable_debug_logging(Console(stderr=True))
    try:
        asyncio.run(task)
    except KeyError as exc:
        _command_error(f"Steam returned no data for ID {exc.args[0]}")
    except (SteamError, ValueError, OSError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


def _default_store_path(steam_id: int | None = None) -> Path:
    name = f"{steam_id}.bin" if steam_id is not None else "credentials.bin"
    return default_profile_dir() / "credentials" / name


def _prompt_secret(label: str, *, confirmation: bool = False) -> str:
    return str(typer.prompt(label, hide_input=True, confirmation_prompt=confirmation))


def _vault_password(*, new: bool = False) -> str:
    secret = vault_passphrase()
    if secret is None:
        secret = _prompt_secret("New vault password" if new else "Vault password", confirmation=new)
    if not secret:
        raise typer.BadParameter("vault password must not be empty")
    return secret


def _store_passphrase(*, new: bool = False) -> bytes:
    global _ACTIVE_VAULT
    directory = default_profile_dir().resolve()
    if _ACTIVE_VAULT is None or _ACTIVE_VAULT.directory.resolve() != directory:
        if not Vault.exists(directory):
            raise CredentialStoreError("vault is not initialized; run 'pysteam init'")
        _ACTIVE_VAULT = Vault.open(_vault_password(), directory)
    return _ACTIVE_VAULT.credential_passphrase


async def _initialize_vault() -> Vault:
    """Create the vault and switch existing account stores after verification."""
    global _ACTIVE_VAULT, _ACTIVE_PASSWORD
    registry = ProfileRegistry()
    directory = registry.directory.resolve()
    if _ACTIVE_VAULT is not None and _ACTIVE_VAULT.directory.resolve() == directory:
        vault = _ACTIVE_VAULT
    else:
        password = _vault_password(new=not Vault.exists(directory))
        vault = (
            Vault.open(password, directory)
            if Vault.exists(directory)
            else Vault.create(password, directory)
        )
        _ACTIVE_VAULT = vault
        _ACTIVE_PASSWORD = password
    profiles = registry.list()
    if not profiles or all(item.store_path.parent.name == "accounts" for item in profiles):
        return vault
    replacements: dict[int, Path] = {}
    for profile in profiles:
        target = directory / "vault" / "accounts" / f"{profile.steam_id}.bin"
        if profile.store_path != target:
            old_password = _prompt_secret(f"Existing store password for {profile.account_name}")
            saved = await EncryptedFileCredentialStore(profile.store_path, old_password).load(
                profile.account_name
            )
            if saved is None or saved.steam_id != profile.steam_id:
                raise ProfileError("existing account store is missing or mismatched")
            new_store = EncryptedFileCredentialStore(target, vault.credential_passphrase)
            if not target.exists():
                await new_store.save(profile.account_name, saved)
            if await new_store.load(profile.account_name) != saved:
                raise ProfileError("vault account migration verification failed")
        replacements[profile.steam_id] = target
    registry.migrate_stores(replacements)
    return vault


@main.command(help="Create or unlock the protected vault and migrate saved accounts.")
def init() -> None:
    _run(_init_command(), debug=False)


async def _init_command() -> None:
    vault = await _initialize_vault()
    _CONSOLE.print(f"[green]Vault ready[/green]: {vault.path}")


@vault_group.command("status", help="Show whether the local vault is initialized.")
def vault_status() -> None:
    directory = default_profile_dir()
    state = "ready" if Vault.exists(directory) else "not initialized"
    _CONSOLE.print(f"Vault: {state} ({directory / 'vault.bin'})")
    if Vault.exists(directory):
        _CONSOLE.print(f"Registered archives: {len(ArchiveRegistry(directory).list())}")


@vault_group.command("change-password", help="Change the vault unlock password.")
def vault_change_password() -> None:
    try:
        old = _vault_password()
        new = _prompt_secret("New vault password", confirmation=True)
        vault = Vault.open(old)
        original_capsules: list[tuple[Path, bytes]] = []
        missing_archives = 0
        try:
            for root in ArchiveRegistry(vault.directory).list():
                path = root / "keys.bin"
                if not path.is_file():
                    missing_archives += 1
                    continue
                original_capsules.append((path, path.read_bytes()))
                ArchiveStore(root, old).rekey(new)
            vault.change_password(old, new)
        except Exception:
            for path, raw in reversed(original_capsules):
                from pysteam.archive import _atomic_write

                _atomic_write(path, raw)
            raise
        global _ACTIVE_VAULT, _ACTIVE_PASSWORD
        _ACTIVE_VAULT = Vault.open(new)
        _ACTIVE_PASSWORD = new
        _CONSOLE.print("[green]Vault password changed[/green]")
        if missing_archives:
            _CONSOLE.print(
                f"[yellow]{missing_archives} moved or missing archive(s) were skipped; "
                "use 'pysteam archive rekey --archive PATH' on each moved copy.[/yellow]"
            )
    except (SteamError, ValueError, OSError) as exc:
        _command_error(f"{type(exc).__name__}: {exc}")


def _load_authenticator(path: Path) -> tuple[str, LoginCredentials, str | None]:
    try:
        imported = load_mafile(path)
        return imported.account_name, imported.credentials, None
    except MaFileError as exc:
        if str(exc) != "a passphrase is required for this encrypted maFile":
            raise
    passphrase = _prompt_secret("maFile backup passphrase")
    imported = load_mafile(path, passphrase=passphrase)
    return imported.account_name, imported.credentials, passphrase


async def _challenge(challenge: GuardChallenge) -> str | None:
    kind = challenge.confirmation_type
    if kind in (2, 3):
        label = "Email Steam Guard code" if kind == 2 else "Steam Guard device code"
        _CONSOLE.print(f"Steam requires a {label.lower()}.")
        return _prompt_secret(label)
    if kind in (4, 5):
        _CONSOLE.print("Approve the pending sign-in in your Steam mobile app.")
        return None
    raise typer.BadParameter(f"Unsupported Steam Guard confirmation type {kind}")


async def _legacy_credentials(
    account_name: str, steam_id: int, mafile_passphrase: str | None
) -> LoginCredentials | None:
    path = _default_store_path(steam_id)
    if not path.is_file():
        return None
    if mafile_passphrase:
        try:
            return await EncryptedFileCredentialStore(path, mafile_passphrase).load(account_name)
        except CredentialStoreError:
            pass
    old_passphrase = _prompt_secret("Existing credential store passphrase")
    return await EncryptedFileCredentialStore(path, old_passphrase).load(account_name)


async def _register_account(
    account_name: str,
    *,
    mafile: Path | None,
    enroll: bool,
    resume_enrollment: Path | None,
    backup_dir: Path | None,
    fresh: bool,
) -> None:
    registry = ProfileRegistry()
    if registry.get(account_name) is not None:
        raise ProfileError("account profile already exists")
    ensure_private_directory(registry.directory)
    if mafile is not None and (enroll or resume_enrollment is not None):
        raise typer.BadParameter("--mafile cannot be combined with enrollment")
    if backup_dir is not None and not enroll:
        raise typer.BadParameter("--backup-dir requires --enroll")
    if resume_enrollment is not None and not enroll:
        raise typer.BadParameter("--resume-enrollment requires --enroll")
    if backup_dir is not None and resume_enrollment is not None:
        raise typer.BadParameter("--backup-dir cannot be combined with --resume-enrollment")

    imported = LoginCredentials()
    backup_passphrase: str | None = None
    if mafile is not None:
        imported_name, imported, backup_passphrase = _load_authenticator(mafile)
        if account_name.casefold() != imported_name.casefold():
            raise ProfileError("maFile account does not match the requested account")
    await _initialize_vault()
    legacy = None
    if imported.steam_id is not None and not fresh:
        legacy = await _legacy_credentials(account_name, imported.steam_id, backup_passphrase)
        if legacy is not None and legacy.steam_id not in (None, imported.steam_id):
            raise ProfileError("existing credential store SteamID does not match the maFile")
    material = imported.with_fallback(legacy)
    password = material.password or _prompt_secret("Steam password")
    if not password:
        raise typer.BadParameter("a Steam password is required")
    material = LoginCredentials(password=password).with_fallback(material)

    if enroll:
        backup_passphrase = _prompt_secret(
            "New maFile backup passphrase", confirmation=resume_enrollment is None
        )
        if not backup_passphrase:
            raise typer.BadParameter("a maFile backup passphrase is required")
        async with SteamClient(timeout=20, auto_reconnect=False) as client:
            service = GuardEnrollmentClient(client)
            if resume_enrollment is None:
                directory = backup_dir or default_profile_dir() / "maFiles" / uuid.uuid4().hex
                pending = await service.login_and_begin(
                    account_name,
                    password,
                    directory=directory,
                    passphrase=backup_passphrase,
                    on_challenge=_challenge,
                )
                _CONSOLE.print(f"Encrypted maFile backup: {pending.mafile_path}")
                _CONSOLE.print(f"Recovery code: {pending.recovery_code}")
                await asyncio.to_thread(_pause, "Back up the maFile folder and recovery code")
            else:
                pending = await service.login_and_resume(
                    account_name,
                    password,
                    mafile_path=resume_enrollment,
                    passphrase=backup_passphrase,
                    on_challenge=_challenge,
                )
            label = {1: "SMS", 3: "email"}.get(pending.confirmation_type, "Steam")
            activation_code = _prompt_secret(f"{label} activation code")
            try:
                mafile = await pending.finalize(activation_code)
            except SteamError:
                _CONSOLE.print(
                    f"Activation incomplete. Keep the backup and retry with "
                    f"--enroll --resume-enrollment {pending.mafile_path}"
                )
                raise
        imported_auth = load_mafile(mafile, passphrase=backup_passphrase)
        if imported_auth.account_name.casefold() != account_name.casefold():
            raise ProfileError("new maFile account does not match the requested account")
        imported = imported_auth.credentials
        material = LoginCredentials(password=password).with_fallback(imported)

    store_passphrase = _store_passphrase(new=True)
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        result = await client.login_auto(
            account_name, credentials=material, on_challenge=_challenge
        )
    steam_id = result.tokens.steam_id
    if imported.steam_id is not None and imported.steam_id != steam_id:
        raise ProfileError("signed-in SteamID does not match the maFile")
    profile = SavedProfile(
        account_name,
        steam_id,
        registry.store_path(steam_id),
        mafile.resolve() if mafile is not None else None,
    )
    store = EncryptedFileCredentialStore(profile.store_path, store_passphrase)
    if profile.store_path.exists():
        previous = await store.load(account_name)
        if previous is None or previous.steam_id != steam_id:
            raise ProfileError("managed credential store already exists for another account")
    await store.save(
        account_name,
        LoginCredentials(
            password=password,
            shared_secret=material.shared_secret,
            refresh_token=result.tokens.refresh_token,
            steam_id=steam_id,
            guard_data=result.tokens.guard_data or material.guard_data,
        ),
    )
    registry.add(profile)
    _CONSOLE.print(
        f"[green]Account added[/green]: {account_name} ({steam_id})"
        + (" [default]" if registry.default() == profile else "")
    )


async def _authenticate(
    client: SteamClient,
    *,
    account: str | None,
    mafile: Path | None,
    store_path: Path | None,
    remember: bool,
    anonymous: bool = False,
) -> LoginResult | None:
    if anonymous:
        if account is not None or mafile is not None or store_path is not None or remember:
            raise typer.BadParameter("--anonymous cannot be combined with account options")
        await client.login_anonymous()
        return None
    registry = ProfileRegistry()
    profile = None
    if mafile is None and store_path is None:
        profile = registry.get(account) if account is not None else registry.default()
    if profile is not None:
        await _initialize_vault()
        profile = registry.select(profile.account_name)
        profile_store = EncryptedFileCredentialStore(profile.store_path, _store_passphrase())
        saved = await profile_store.load(profile.account_name)
        if saved is None:
            raise ProfileError("saved account has no encrypted credentials")
        if saved.steam_id is not None and saved.steam_id != profile.steam_id:
            raise ProfileError("saved account SteamID does not match its profile")
        if not saved.refresh_token and not saved.password:
            saved = LoginCredentials(password=_prompt_secret("Steam password")).with_fallback(saved)
        result = await client.login_auto(
            profile.account_name, credentials=saved, store=profile_store, on_challenge=_challenge
        )
        if result.tokens.steam_id != profile.steam_id:
            raise ProfileError("signed-in SteamID does not match its profile")
        return result
    if mafile is None and account is None and store_path is None and not remember:
        await client.login_anonymous()
        return None
    if mafile is None and account is None:
        raise typer.BadParameter("--account is required when no maFile is supplied")
    supplied = LoginCredentials()
    mafile_passphrase: str | None = None
    if mafile is not None:
        imported_name, supplied, mafile_passphrase = _load_authenticator(mafile)
        if account is not None and account.casefold() != imported_name.casefold():
            raise typer.BadParameter("--account does not match the maFile account")
        account = imported_name
    assert account is not None

    store: EncryptedFileCredentialStore | None = None
    default_path = _default_store_path(supplied.steam_id)
    existing_mafile_store = mafile is not None and default_path.is_file()
    if remember or store_path is not None or existing_mafile_store:
        path = store_path or default_path
        if store_path is None:
            ensure_private_directory(default_profile_dir())
        passphrase = (
            mafile_passphrase
            if store_path is None and mafile_passphrase is not None
            else _prompt_secret("Credential store passphrase", confirmation=not path.exists())
        )
        store = EncryptedFileCredentialStore(path, passphrase)
    saved = await store.load(account) if store is not None else None
    material = supplied.with_fallback(saved)
    if not material.refresh_token and not material.password:
        material = LoginCredentials(password=_prompt_secret("Steam password")).with_fallback(
            material
        )
    try:
        return await client.login_auto(
            account, credentials=material, store=store, on_challenge=_challenge
        )
    except SteamResultError as exc:
        if exc.eresult not in {5, 26, 27} or not material.refresh_token or material.password:
            raise
        _CONSOLE.print("Saved login expired. Enter your Steam password to sign in again.")
        material = LoginCredentials(password=_prompt_secret("Steam password")).with_fallback(
            material
        )
        return await client.login_auto(
            account, credentials=material, store=store, on_challenge=_challenge
        )


async def _login(
    account: str | None, *, mafile: Path | None, store: Path | None, remember: bool
) -> None:
    if account is None and mafile is None and ProfileRegistry().default() is None:
        raise typer.BadParameter("no default account; run 'pysteam account add' or pass an account")
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        result = await _authenticate(
            client, account=account, mafile=mafile, store_path=store, remember=remember
        )
        assert result is not None
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="dim")
        summary.add_column()
        summary.add_row("Account", Text(result.tokens.account_name))
        summary.add_row("SteamID", str(result.tokens.steam_id))
        summary.add_row("Method", result.method)
        saved_profile = ProfileRegistry().get(result.tokens.account_name)
        if saved_profile is not None and mafile is None and store is None:
            summary.add_row("Encrypted store", str(saved_profile.store_path))
        elif (
            remember
            or store is not None
            or (mafile is not None and _default_store_path(result.tokens.steam_id).is_file())
        ):
            default_id = result.tokens.steam_id if mafile is not None else None
            summary.add_row("Encrypted store", str(store or _default_store_path(default_id)))
        _CONSOLE.print(Panel(summary, title="Login succeeded", border_style="green", expand=False))


async def _manifest(
    client: SteamClient,
    app_id: int,
    depot_id: int,
    manifest_id: int | None,
    branch: str,
) -> tuple[DepotManifest, bytes, str, str]:
    if manifest_id is None:
        manifest_id = (await client.get_app_manifest_ids(app_id, branch=branch)).get(depot_id)
        if manifest_id is None:
            raise ProtocolError("PICS has no manifest for this depot and branch")
    try:
        key = await client.cdn.get_depot_key(app_id, depot_id)
    except SteamResultError as exc:
        if exc.eresult == 15:
            raise ProtocolError(
                "Steam denied the depot key. Sign in with an account that owns this depot "
                "using a saved account profile or --mafile."
            ) from None
        raise
    servers = await client.cdn.servers()
    if not servers:
        raise ProtocolError("Steam returned no CDN servers")
    last_error: SteamError | None = None
    for server in servers[:3]:
        token = ""
        try:
            manifest = await client.cdn.get_manifest(
                server=server,
                app_id=app_id,
                depot_id=depot_id,
                manifest_id=manifest_id,
                depot_key=key,
                branch=branch,
            )
            return manifest, key, server, token
        except TransportError as exc:
            last_error = exc
            continue
        except CDNHTTPError as exc:
            if exc.status_code not in (401, 403):
                last_error = exc
                continue
            hostname = urlsplit(server).hostname
            if hostname is None:
                raise ProtocolError("CDN server has no hostname") from None
            token = await client.cdn.get_auth_token(app_id, depot_id, hostname)
            try:
                manifest = await client.cdn.get_manifest(
                    server=server,
                    app_id=app_id,
                    depot_id=depot_id,
                    manifest_id=manifest_id,
                    depot_key=key,
                    auth_token=token,
                    branch=branch,
                )
                return manifest, key, server, token
            except CDNHTTPError as retry_exc:
                last_error = retry_exc
    if last_error is not None:
        raise last_error
    raise ProtocolError("CDN manifest could not be fetched")


async def _depot_list(
    app_id: int,
    depot_id: int,
    manifest_id: int | None,
    branch: str,
    account: str | None,
    mafile: Path | None,
    store: Path | None,
    as_json: bool,
    anonymous: bool = False,
) -> None:
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        await _authenticate(
            client,
            account=account,
            mafile=mafile,
            store_path=store,
            remember=False,
            anonymous=anonymous,
        )
        manifest, _, _, _ = await _manifest(client, app_id, depot_id, manifest_id, branch)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "app_id": app_id,
                    "depot_id": manifest.depot_id,
                    "manifest_id": manifest.manifest_id,
                    "files": [
                        {"name": file.name, "size": file.size, "flags": file.flags}
                        for file in manifest.files
                    ],
                },
                indent=2,
            )
        )
        return
    table = Table(title=f"Depot {depot_id} · manifest {manifest.manifest_id}", box=None)
    table.add_column("Path", overflow="fold")
    table.add_column("Bytes", justify="right")
    table.add_column("Kind")
    for file in manifest.files:
        kind = "link" if file.link_target else "directory" if file.flags & 64 else "file"
        table.add_row(Text(file.name), str(file.size), kind)
    _CONSOLE.print(table)


def _destination(root: Path, file: DepotFile) -> Path:
    if file.link_target or file.flags & (64 | 512):
        raise ProtocolError("directory and symlink entries cannot be downloaded as files")
    destination = root.joinpath(*file.name.split("/"))
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ProtocolError("manifest path escapes the output directory")
    return destination


async def _depot_download(
    app_id: int,
    depot_id: int,
    manifest_id: int | None,
    branch: str,
    account: str | None,
    mafile: Path | None,
    store: Path | None,
    files: tuple[str, ...],
    output: Path,
    overwrite: bool,
    anonymous: bool = False,
    *,
    all_files: bool = False,
    includes: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
    max_downloads: int = 8,
) -> None:
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        await _authenticate(
            client,
            account=account,
            mafile=mafile,
            store_path=store,
            remember=False,
            anonymous=anonymous,
        )
        manifest, key, server, token = await _manifest(
            client, app_id, depot_id, manifest_id, branch
        )
        root = output.resolve()
        if not files and not all_files:
            raise ValueError("select --file or --all")
        chosen = {manifest.file(name).name for name in files}
        if all_files:
            chosen.update(
                item.name
                for item in manifest.files
                if not item.link_target and not item.flags & (64 | 512)
            )
        if includes:
            chosen = {
                name
                for name in chosen
                if any(fnmatch.fnmatchcase(name, pattern) for pattern in includes)
            }
        if excludes:
            chosen = {
                name
                for name in chosen
                if not any(fnmatch.fnmatchcase(name, pattern) for pattern in excludes)
            }
        selected = [manifest.file(name) for name in sorted(chosen)]
        targets = [(_destination(root, file), file) for file in selected]
        if not overwrite and any(path.exists() for path, _ in targets):
            raise ValueError("destination exists; use --overwrite to replace files")
        semaphore = asyncio.Semaphore(max_downloads)

        async def download(destination: Path, file: DepotFile) -> None:
            nonlocal token
            async with semaphore:
                try:
                    await client.cdn.download_file(
                        server=server,
                        manifest=manifest,
                        file=file,
                        depot_key=key,
                        destination=destination,
                        auth_token=token,
                    )
                except CDNHTTPError as exc:
                    if token or exc.status_code not in (401, 403):
                        raise
                    hostname = urlsplit(server).hostname
                    if hostname is None:
                        raise ProtocolError("CDN server has no hostname") from None
                    token = await client.cdn.get_auth_token(app_id, depot_id, hostname)
                    await client.cdn.download_file(
                        server=server,
                        manifest=manifest,
                        file=file,
                        depot_key=key,
                        destination=destination,
                        auth_token=token,
                    )
                _CONSOLE.print(
                    Text.assemble(("Downloaded", "green"), " ", file.name, f" ({file.size} bytes)")
                )

        try:
            async with asyncio.TaskGroup() as group:
                for destination, file in targets:
                    group.create_task(download(destination, file))
        except* (SteamError, OSError, ValueError) as group:
            raise group.exceptions[0] from None


async def _doctor(app_id: int) -> None:
    started = time.monotonic()
    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        _CONSOLE.print("[green]OK[/green]  CM discovery and WebSocket connection")
        await client.login_anonymous()
        _CONSOLE.print("[green]OK[/green]  Anonymous CM logon")
        info = await client.get_app_info(app_id)
        common = info.get("common")
        name = _field(common, "name") if isinstance(common, dict) else "unknown"
        _CONSOLE.print(Text.assemble(("OK", "green"), f"  PICS app {app_id}: ", name))
    _CONSOLE.print(f"Completed in {time.monotonic() - started:.2f}s")


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


@main.command(help="Check CM discovery, anonymous logon, and PICS.")
def doctor(
    app_id: Annotated[int, typer.Option(min=1, max=0xFFFFFFFF)] = 220,
    debug: Annotated[bool, typer.Option("--debug", help="Show redacted protocol logs.")] = False,
) -> None:
    _run(_doctor(app_id), debug=debug)


async def _archive_store(root: Path) -> ArchiveStore:
    await _initialize_vault()
    assert _ACTIVE_PASSWORD is not None
    return ArchiveStore(root, _ACTIVE_PASSWORD)


def _register_archive(root: Path) -> None:
    if _ACTIVE_VAULT is not None and (root / "keys.bin").is_file():
        ArchiveRegistry(_ACTIVE_VAULT.directory).add(root)


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
            from pysteam.cdn import parse_manifest

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
