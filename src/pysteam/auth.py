"""Current Steam Authentication unified-message sessions."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import platform
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from google.protobuf.message import Message

from pysteam.errors import AuthenticationError, ProtocolError, RequestTimeout, SteamResultError
from pysteam.proto import enums_pb2
from pysteam.proto import steammessages_auth_steamclient_pb2 as auth_proto

if TYPE_CHECKING:
    from pysteam.client import SteamClient

_T = TypeVar("_T", bound=Message)
_PREFIX = "Authentication."


def _os_type() -> int:
    return {"Windows": 16, "Linux": -203, "Darwin": -102}.get(platform.system(), 0)


def _steam_id_from_jwt(token: str) -> int:
    """Read the unverified subject for request routing; Steam validates the token."""
    try:
        encoded = token.split(".")[1]
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        subject = json.loads(payload)["sub"]
        steam_id = int(subject)
    except (IndexError, ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise ProtocolError("Steam token has no usable SteamID subject") from exc
    if not 0 < steam_id <= 0xFFFFFFFFFFFFFFFF:
        raise ProtocolError("Steam token SteamID subject is out of range")
    return steam_id


@dataclass(frozen=True, slots=True)
class AuthTokens:
    steam_id: int
    account_name: str
    refresh_token: str = field(repr=False)
    access_token: str = field(repr=False)
    guard_data: str = field(repr=False, default="")


@dataclass(slots=True)
class AuthSession:
    """A credential or QR session awaiting Steam Guard approval."""

    client: SteamClient = field(repr=False)
    client_id: int
    request_id: bytes = field(repr=False)
    interval: float
    allowed_confirmations: tuple[int, ...]
    challenge_url: str | None = field(repr=False, default=None)
    steam_id: int | None = None

    async def submit_guard_code(self, code: str, *, code_type: int) -> None:
        if not code or code_type not in (
            auth_proto.k_EAuthSessionGuardType_EmailCode,
            auth_proto.k_EAuthSessionGuardType_DeviceCode,
        ):
            raise ValueError("provide a nonempty email or device Guard code")
        if code_type not in self.allowed_confirmations or self.steam_id is None:
            raise ValueError("this session does not allow that Guard code")
        request = auth_proto.CAuthentication_UpdateAuthSessionWithSteamGuardCode_Request(
            client_id=self.client_id,
            steamid=self.steam_id,
            code=code,
            code_type=code_type,
        )
        try:
            await self.client.call_um(
                _PREFIX + "UpdateAuthSessionWithSteamGuardCode#1",
                request,
                auth_proto.CAuthentication_UpdateAuthSessionWithSteamGuardCode_Response,
            )
        except SteamResultError as exc:
            if exc.eresult != 29:  # DuplicateRequest can follow a mobile-app approval.
                raise AuthenticationError("submit Steam Guard code", exc.eresult) from exc

    async def poll(self) -> AuthTokens | None:
        request = auth_proto.CAuthentication_PollAuthSessionStatus_Request(
            client_id=self.client_id,
            request_id=self.request_id,
        )
        try:
            response = await self.client.call_um(
                _PREFIX + "PollAuthSessionStatus#1",
                request,
                auth_proto.CAuthentication_PollAuthSessionStatus_Response,
            )
        except SteamResultError as exc:
            raise AuthenticationError("poll authentication", exc.eresult) from exc
        if response.new_client_id:
            self.client_id = response.new_client_id
        if response.new_challenge_url:
            self.challenge_url = response.new_challenge_url
        if not response.refresh_token:
            return None
        return AuthTokens(
            steam_id=_steam_id_from_jwt(response.refresh_token),
            account_name=response.account_name,
            refresh_token=response.refresh_token,
            access_token=response.access_token,
            guard_data=response.new_guard_data,
        )

    async def wait_for_tokens(self, *, timeout: float = 180.0) -> AuthTokens:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise RequestTimeout("authentication session timed out")
            await asyncio.sleep(min(max(self.interval, 1.0), remaining))
            try:
                result = await asyncio.wait_for(self.poll(), timeout=remaining)
            except TimeoutError as exc:
                raise RequestTimeout("authentication session timed out") from exc
            if result is not None:
                return result


class AuthenticationClient:
    def __init__(self, client: SteamClient) -> None:
        self._client = client

    async def _call(self, method: str, request: Message, response_type: type[_T]) -> _T:
        try:
            return await self._client.call_um(_PREFIX + method + "#1", request, response_type)
        except SteamResultError as exc:
            raise AuthenticationError(method, exc.eresult) from exc

    async def begin_credentials(
        self,
        username: str,
        password: str,
        *,
        guard_data: str = "",
        remember_login: bool = False,
        device_name: str | None = None,
    ) -> AuthSession:
        if not username or not password:
            raise ValueError("username and password are required")
        key = await self._call(
            "GetPasswordRSAPublicKey",
            auth_proto.CAuthentication_GetPasswordRSAPublicKey_Request(account_name=username),
            auth_proto.CAuthentication_GetPasswordRSAPublicKey_Response,
        )
        try:
            modulus = int(key.publickey_mod, 16)
            exponent = int(key.publickey_exp, 16)
            public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
            encrypted = public_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
        except (ValueError, OverflowError) as exc:
            raise ProtocolError("Steam returned an invalid password public key") from exc
        details = auth_proto.CAuthentication_DeviceDetails(
            device_friendly_name=device_name or f"pysteam ({platform.node()})",
            platform_type=auth_proto.k_EAuthTokenPlatformType_SteamClient,
            os_type=_os_type(),
        )
        request = auth_proto.CAuthentication_BeginAuthSessionViaCredentials_Request(
            account_name=username,
            encrypted_password=base64.b64encode(encrypted).decode("ascii"),
            encryption_timestamp=key.timestamp,
            remember_login=remember_login,
            platform_type=auth_proto.k_EAuthTokenPlatformType_SteamClient,
            persistence=(
                enums_pb2.k_ESessionPersistence_Persistent
                if remember_login
                else enums_pb2.k_ESessionPersistence_Ephemeral
            ),
            website_id="Client",
            device_details=details,
            guard_data=guard_data,
        )
        response = await self._call(
            "BeginAuthSessionViaCredentials",
            request,
            auth_proto.CAuthentication_BeginAuthSessionViaCredentials_Response,
        )
        return AuthSession(
            self._client,
            response.client_id,
            response.request_id,
            response.interval,
            tuple(item.confirmation_type for item in response.allowed_confirmations),
            steam_id=response.steamid,
        )

    async def begin_qr(self, *, device_name: str | None = None) -> AuthSession:
        details = auth_proto.CAuthentication_DeviceDetails(
            device_friendly_name=device_name or f"pysteam ({platform.node()})",
            platform_type=auth_proto.k_EAuthTokenPlatformType_SteamClient,
            os_type=_os_type(),
        )
        request = auth_proto.CAuthentication_BeginAuthSessionViaQR_Request(
            device_details=details,
            website_id="Client",
        )
        response = await self._call(
            "BeginAuthSessionViaQR",
            request,
            auth_proto.CAuthentication_BeginAuthSessionViaQR_Response,
        )
        return AuthSession(
            self._client,
            response.client_id,
            response.request_id,
            response.interval,
            tuple(item.confirmation_type for item in response.allowed_confirmations),
            challenge_url=response.challenge_url,
        )

    async def generate_access_token(
        self, refresh_token: str, *, steam_id: int | None = None
    ) -> str:
        if not refresh_token:
            raise ValueError("refresh token is empty")
        resolved_id = steam_id or _steam_id_from_jwt(refresh_token)
        request = auth_proto.CAuthentication_AccessToken_GenerateForApp_Request(
            steamid=resolved_id,
            refresh_token=refresh_token,
        )
        response = await self._call(
            "GenerateAccessTokenForApp",
            request,
            auth_proto.CAuthentication_AccessToken_GenerateForApp_Response,
        )
        if not response.access_token:
            raise ProtocolError("Steam did not return an access token")
        return response.access_token
