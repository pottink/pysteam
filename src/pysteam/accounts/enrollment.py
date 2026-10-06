"""Steam Guard enrollment with a saved authenticator backup before activation."""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import httpx
import msgspec
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from google.protobuf.message import DecodeError, Message

from pysteam.accounts.auth import (
    AuthenticationInteractionRequired,
    AuthTokens,
    GuardChallenge,
    GuardChallengeHandler,
)
from pysteam.accounts.guard import guard_code
from pysteam.accounts.mafile import load_mafile
from pysteam.errors import (
    EnrollmentError,
    ProtocolError,
    RequestTimeout,
    SteamResultError,
    TransportError,
)
from pysteam.proto import steammessages_twofactor_steamclient_pb2 as twofactor

if TYPE_CHECKING:
    from pysteam.client import SteamClient

_T = TypeVar("_T", bound=Message)
_MAX_RESPONSE = 1024 * 1024
_MAX_FINALIZE_ATTEMPTS = 10


class _TwoFactorService:
    def __init__(self, client: SteamClient) -> None:
        self._http = client._http
        self._timeout = client.timeout

    async def call(self, method: str, request: Message, response_type: type[_T], token: str) -> _T:
        encoded = base64.b64encode(request.SerializeToString()).decode("ascii")
        url = f"https://api.steampowered.com/ITwoFactorService/{method}/v1/"
        try:
            async with self._http.stream(
                "POST",
                url,
                params={"access_token": token},
                data={"input_protobuf_encoded": encoded},
                timeout=self._timeout,
            ) as response:
                content = bytearray()
                async for part in response.aiter_bytes():
                    if len(content) + len(part) > _MAX_RESPONSE:
                        raise ProtocolError("two-factor response exceeds size limit")
                    content.extend(part)
                status_code = response.status_code
                result_header = response.headers.get("x-eresult")
        except httpx.HTTPError:
            raise TransportError(f"two-factor {method} request failed") from None
        try:
            eresult = int(result_header) if result_header is not None else None
        except ValueError:
            raise ProtocolError("two-factor result header is invalid") from None
        if eresult is not None and eresult != 1:
            raise SteamResultError(f"two-factor {method}", eresult)
        if status_code >= 300:
            raise TransportError(f"two-factor {method} returned HTTP {status_code}")
        if eresult is None:
            raise ProtocolError("two-factor result header is missing")
        try:
            parsed = response_type()
            parsed.ParseFromString(bytes(content))
        except DecodeError:
            raise ProtocolError("two-factor response is invalid protobuf") from None
        return parsed


def _atomic_new_file(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        if path.exists():
            raise EnrollmentError("authenticator backup path already exists")
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _prepare_backup_directory(directory: Path) -> None:
    try:
        directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        descriptor, temporary = tempfile.mkstemp(prefix=".pysteam-check-", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(b"check")
                target.flush()
                os.fsync(target.fileno())
        finally:
            os.unlink(temporary)
    except OSError:
        raise EnrollmentError("authenticator backup directory must be new and writable") from None


def _save_backup(
    directory: Path,
    *,
    steam_id: int,
    account_name: str,
    device_id: str,
    response: twofactor.CTwoFactor_AddAuthenticator_Response,
    passphrase: str,
    prepared: bool = False,
) -> Path:
    if not passphrase:
        raise ValueError("an authenticator backup passphrase is required")
    if not prepared:
        _prepare_backup_directory(directory)
    elif not directory.is_dir() or any(directory.iterdir()):
        raise EnrollmentError("authenticator backup directory is no longer empty")
    salt, iv = os.urandom(16), os.urandom(16)
    key = Argon2id(salt=salt, length=32, iterations=3, lanes=12, memory_cost=12 * 1024).derive(
        passphrase.encode("utf-8")
    )
    filename = f"{steam_id}.maFile"
    record = {
        "account_name": account_name,
        "steam_id": steam_id,
        "serial_number": str(response.serial_number),
        "revocation_code": response.revocation_code,
        "shared_secret": base64.b64encode(response.shared_secret).decode("ascii"),
        "token_gid": response.token_gid,
        "identity_secret": base64.b64encode(response.identity_secret).decode("ascii"),
        "uri": response.uri,
        "device_id": device_id,
        "secret_1": base64.b64encode(response.secret_1).decode("ascii"),
        "tokens": None,
    }
    padder = padding.PKCS7(128).padder()
    plaintext = msgspec.json.encode(record)
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = base64.b64encode(encryptor.update(padded) + encryptor.finalize())
    manifest = {
        "version": 1,
        "entries": [
            {
                "filename": filename,
                "steam_id": steam_id,
                "account_name": account_name,
                "encryption": {
                    "scheme": "Argon2idAes256",
                    "salt": base64.b64encode(salt).decode("ascii"),
                    "iv": base64.b64encode(iv).decode("ascii"),
                },
            }
        ],
    }
    try:
        _atomic_new_file(directory / "manifest.json", msgspec.json.encode(manifest))
        destination = directory / filename
        _atomic_new_file(destination, ciphertext)
    except OSError:
        raise EnrollmentError("authenticator backup could not be saved") from None
    return destination


@dataclass(slots=True)
class PendingGuardEnrollment:
    """Authenticator secrets have been backed up, but activation may be pending."""

    client: SteamClient = field(repr=False)
    tokens: AuthTokens = field(repr=False)
    account_name: str
    mafile_path: Path
    confirmation_type: int
    phone_hint: str
    recovery_code: str | None = field(repr=False)
    shared_secret: str = field(repr=False)
    server_time: int = field(repr=False)
    token_gid: str = field(repr=False)
    finalized: bool = False

    async def finalize(self, activation_code: str, *, timeout: float = 180.0) -> Path:
        """Activate using the SMS or email code, then verify Steam's status."""
        if not activation_code or timeout <= 0:
            raise ValueError("a nonempty activation code and positive timeout are required")
        if self.finalized:
            return self.mafile_path
        service = _TwoFactorService(self.client)
        try:
            async with asyncio.timeout(timeout):
                offset = await self.client.auth.steam_time_offset()
                for _ in range(_MAX_FINALIZE_ATTEMPTS):
                    now = max(self.server_time, int(time.time() + offset))
                    request = twofactor.CTwoFactor_FinalizeAddAuthenticator_Request(
                        steamid=self.tokens.steam_id,
                        authenticator_code=guard_code(self.shared_secret, timestamp=now),
                        authenticator_time=now,
                        activation_code=activation_code,
                        validate_sms_code=True,
                    )
                    response = await service.call(
                        "FinalizeAddAuthenticator",
                        request,
                        twofactor.CTwoFactor_FinalizeAddAuthenticator_Response,
                        self.tokens.access_token,
                    )
                    if response.want_more:
                        next_time = response.server_time
                        if next_time // 30 <= now // 30:
                            await asyncio.sleep(30 - ((time.time() + offset) % 30) + 0.25)
                            offset = await self.client.auth.steam_time_offset()
                            next_time = int(time.time() + offset)
                        self.server_time = next_time
                        continue
                    if not response.success:
                        raise EnrollmentError("Steam did not confirm authenticator activation")
                    for check in range(3):
                        status = await service.call(
                            "QueryStatus",
                            twofactor.CTwoFactor_Status_Request(steamid=self.tokens.steam_id),
                            twofactor.CTwoFactor_Status_Response,
                            self.tokens.access_token,
                        )
                        if status.state and (
                            not self.token_gid
                            or not status.token_gid
                            or status.token_gid == self.token_gid
                        ):
                            self.finalized = True
                            return self.mafile_path
                        if check < 2:
                            await asyncio.sleep(1)
                    raise EnrollmentError("Steam did not verify the new authenticator")
                raise EnrollmentError("Steam requested too many authenticator codes")
        except TimeoutError:
            raise RequestTimeout("authenticator activation timed out") from None


class GuardEnrollmentClient:
    """Sign in as a mobile client, back up new secrets, and activate Guard."""

    def __init__(self, client: SteamClient) -> None:
        self._client = client

    async def _login_mobile(
        self,
        account_name: str,
        password: str,
        on_challenge: GuardChallengeHandler | None,
        timeout: float,
    ) -> AuthTokens:
        try:
            async with asyncio.timeout(timeout):
                session = await self._client.auth.begin_credentials(
                    account_name, password, remember_login=True, platform_kind="mobile"
                )
                tokens = await session.poll()
                if tokens is None:
                    allowed = session.allowed_confirmations
                    if 1 not in allowed:
                        selected = next((kind for kind in (4, 5, 2, 3) if kind in allowed), 0)
                        if not selected or on_challenge is None:
                            raise AuthenticationInteractionRequired(session, selected)
                        position = allowed.index(selected)
                        message = (
                            session.confirmation_messages[position]
                            if position < len(session.confirmation_messages)
                            else ""
                        )
                        code = await on_challenge(GuardChallenge(selected, message, session))
                        if selected in (2, 3):
                            if not code:
                                raise AuthenticationInteractionRequired(session, selected)
                            await session.submit_guard_code(code, code_type=selected)
                    tokens = await session.wait_for_tokens()
                if tokens.account_name.casefold() != account_name.casefold():
                    raise ProtocolError(
                        "authenticated account does not match the requested account"
                    )
                if not tokens.access_token:
                    renewed = await self._client.auth.generate_access_token_result(
                        tokens.refresh_token, steam_id=tokens.steam_id
                    )
                    tokens = AuthTokens(
                        tokens.steam_id,
                        tokens.account_name,
                        renewed.refresh_token,
                        renewed.access_token,
                        tokens.guard_data,
                    )
                return tokens
        except TimeoutError:
            raise RequestTimeout("mobile authentication timed out") from None

    async def login_and_begin(
        self,
        account_name: str,
        password: str,
        *,
        directory: str | Path,
        passphrase: str,
        on_challenge: GuardChallengeHandler | None = None,
        timeout: float = 180.0,
    ) -> PendingGuardEnrollment:
        """Log in and save a new encrypted maFile before activation begins."""
        if not passphrase:
            raise ValueError("an authenticator backup passphrase is required")
        destination = Path(directory)
        if destination.exists():
            raise EnrollmentError("authenticator backup directory must not already exist")
        tokens = await self._login_mobile(account_name, password, on_challenge, timeout)
        service = _TwoFactorService(self._client)
        status = await service.call(
            "QueryStatus",
            twofactor.CTwoFactor_Status_Request(steamid=tokens.steam_id),
            twofactor.CTwoFactor_Status_Response,
            tokens.access_token,
        )
        if status.state:
            raise EnrollmentError("an authenticator is already present on this account")
        _prepare_backup_directory(destination)
        device_id = f"android:{uuid.uuid4()}"
        added = await service.call(
            "AddAuthenticator",
            twofactor.CTwoFactor_AddAuthenticator_Request(
                steamid=tokens.steam_id,
                authenticator_type=1,
                device_identifier=device_id,
                sms_phone_id="1",
                version=2,
            ),
            twofactor.CTwoFactor_AddAuthenticator_Response,
            tokens.access_token,
        )
        if (
            len(added.shared_secret) != 20
            or len(added.identity_secret) != 20
            or not added.secret_1
            or not added.revocation_code
            or not added.uri
            or not added.token_gid
            or not added.account_name
            or not added.serial_number
            or not added.server_time
            or added.account_name.casefold() != account_name.casefold()
        ):
            raise ProtocolError("Steam returned incomplete authenticator details")
        mafile_path = _save_backup(
            destination,
            steam_id=tokens.steam_id,
            account_name=added.account_name,
            device_id=device_id,
            response=added,
            passphrase=passphrase,
            prepared=True,
        )
        imported = load_mafile(mafile_path, passphrase=passphrase)
        shared_secret = base64.b64encode(added.shared_secret).decode("ascii")
        if (
            imported.account_name.casefold() != account_name.casefold()
            or imported.credentials.steam_id != tokens.steam_id
            or imported.credentials.shared_secret != shared_secret
        ):
            raise EnrollmentError("authenticator backup verification failed")
        return PendingGuardEnrollment(
            self._client,
            tokens,
            added.account_name,
            mafile_path,
            added.confirm_type,
            added.phone_number_hint,
            added.revocation_code,
            shared_secret,
            added.server_time,
            added.token_gid,
        )

    async def login_and_resume(
        self,
        account_name: str,
        password: str,
        *,
        mafile_path: str | Path,
        passphrase: str,
        on_challenge: GuardChallengeHandler | None = None,
        timeout: float = 180.0,
    ) -> PendingGuardEnrollment:
        """Resume activation from a previously saved maFile after signing in again."""
        imported = load_mafile(mafile_path, passphrase=passphrase)
        if imported.account_name.casefold() != account_name.casefold():
            raise EnrollmentError("maFile account does not match the requested account")
        tokens = await self._login_mobile(account_name, password, on_challenge, timeout)
        if imported.credentials.steam_id != tokens.steam_id:
            raise EnrollmentError("maFile SteamID does not match the authenticated account")
        status = await _TwoFactorService(self._client).call(
            "QueryStatus",
            twofactor.CTwoFactor_Status_Request(steamid=tokens.steam_id),
            twofactor.CTwoFactor_Status_Response,
            tokens.access_token,
        )
        if status.state:
            raise EnrollmentError("authenticator is already active; no activation is pending")
        return PendingGuardEnrollment(
            self._client,
            tokens,
            imported.account_name,
            Path(mafile_path),
            0,
            "",
            None,
            imported.credentials.shared_secret or "",
            0,
            "",
        )
