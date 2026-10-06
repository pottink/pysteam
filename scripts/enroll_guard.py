"""Standalone enrollment check; use `pysteam account add --enroll` for profiles."""

from __future__ import annotations

import asyncio
import uuid
from getpass import getpass
from pathlib import Path
from typing import Annotated

import typer

from pysteam import (
    GuardChallenge,
    GuardEnrollmentClient,
    SteamClient,
    SteamError,
    default_profile_dir,
)
from pysteam.profiles import ensure_private_directory


async def _challenge(challenge: GuardChallenge) -> str | None:
    if challenge.confirmation_type == 2:
        return await asyncio.to_thread(getpass, "Steam Guard code from your account's email: ")
    if challenge.confirmation_type == 3:
        return await asyncio.to_thread(
            getpass, "Code from your existing Steam mobile authenticator: "
        )
    if challenge.confirmation_type == 4:
        print("Approve this sign-in in your Steam mobile app.")
        return None
    if challenge.confirmation_type == 5:
        print("Approve this sign-in through Steam's email link.")
        return None
    raise RuntimeError("Steam requested an unsupported login confirmation")


def _default_output() -> Path:
    ensure_private_directory(default_profile_dir())
    return default_profile_dir() / "maFiles" / uuid.uuid4().hex


async def _run(account: str | None, output: Path | None, resume: Path | None) -> None:
    account_name = account or input("Steam account name: ").strip()
    if not account_name:
        raise ValueError("a Steam account name is required")
    password = getpass("Steam password: ")
    passphrase = getpass("maFile backup passphrase: ")
    if not passphrase:
        raise ValueError("a nonempty backup passphrase is required")
    if resume is None and passphrase != getpass("Repeat backup passphrase: "):
        raise ValueError("backup passphrases do not match")

    async with SteamClient(timeout=20, auto_reconnect=False) as client:
        enroll = GuardEnrollmentClient(client)
        if resume is None:
            pending = await enroll.login_and_begin(
                account_name,
                password,
                directory=output or _default_output(),
                passphrase=passphrase,
                on_challenge=_challenge,
            )
            print(f"Encrypted authenticator backup: {pending.mafile_path}")
            print(f"Recovery code: {pending.recovery_code}")
            await asyncio.to_thread(
                input,
                "Write down the recovery code and back up the maFile folder, then press Enter.",
            )
        else:
            pending = await enroll.login_and_resume(
                account_name,
                password,
                mafile_path=resume,
                passphrase=passphrase,
                on_challenge=_challenge,
            )
            print(f"Resuming activation from: {pending.mafile_path}")
        channel = {1: "SMS", 3: "email"}.get(pending.confirmation_type, "Steam")
        activation_code = getpass(f"{channel} activation code: ")
        try:
            saved = await pending.finalize(activation_code)
        except SteamError:
            print(
                "Activation is incomplete. Keep the backup and retry with "
                f"--resume {pending.mafile_path}"
            )
            raise
        print(f"Steam Guard activation verified. Encrypted maFile: {saved}")


main = typer.Typer(help="Enroll a new Steam Guard authenticator.", add_completion=False)


@main.command()
def enroll(
    account: Annotated[
        str | None, typer.Option(help="Steam account name (otherwise prompted).")
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(file_okay=False, help="New directory for the encrypted maFile and manifest."),
    ] = None,
    resume: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, help="Existing maFile with incomplete activation."
        ),
    ] = None,
) -> None:
    if output is not None and resume is not None:
        raise typer.BadParameter("--output and --resume cannot be combined")
    try:
        asyncio.run(_run(account, output, resume))
    except (SteamError, ValueError) as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    main()
