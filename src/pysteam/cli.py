"""The installed ``pysteam`` command. Protocol logging stays redacted."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import time
import uuid
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pysteam._terminal import enable_debug_logging
from pysteam.accounts.auth import GuardChallenge, LoginResult
from pysteam.accounts.credentials import EncryptedFileCredentialStore, LoginCredentials
from pysteam.accounts.enrollment import GuardEnrollmentClient
from pysteam.accounts.mafile import load_mafile
from pysteam.accounts.profiles import (
    ProfileRegistry,
    SavedProfile,
    default_profile_dir,
    ensure_private_directory,
)
from pysteam.accounts.vault import Vault, vault_passphrase
from pysteam.client import SteamClient
from pysteam.content.archive import ArchiveRegistry, ArchiveStore
from pysteam.content.cdn import DepotFile, DepotManifest
from pysteam.content.pics import KVValue, extract_manifest_ids
from pysteam.errors import (
    CDNHTTPError,
    CredentialStoreError,
    MaFileError,
    ProfileError,
    ProtocolError,
    SteamError,
    SteamResultError,
    TransportError,
)

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
                from pysteam.content.archive import _atomic_write

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


async def _archive_store(root: Path) -> ArchiveStore:
    await _initialize_vault()
    assert _ACTIVE_PASSWORD is not None
    return ArchiveStore(root, _ACTIVE_PASSWORD)


def _register_archive(root: Path) -> None:
    if _ACTIVE_VAULT is not None and (root / "keys.bin").is_file():
        ArchiveRegistry(_ACTIVE_VAULT.directory).add(root)


from pysteam._cli import (  # noqa: E402,F401
    accounts,
    appinfo,
    archive,
    client_packages,
    misc,
    sis,
    workshop,
)
from pysteam._cli import depot as depot_commands  # noqa: E402,F401
from pysteam._cli.misc import app  # noqa: E402,F401
