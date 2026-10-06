"""Async Steam CM client over secure WebSocket connections."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
import msgspec
from google.protobuf.message import DecodeError, Message
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from pysteam.credentials import CredentialStore, EncryptedFileCredentialStore, LoginCredentials
from pysteam.errors import (
    AuthenticationError,
    ProfileError,
    ProtocolError,
    RequestTimeout,
    SteamError,
    SteamResultError,
    TransportError,
)
from pysteam.pics import KVValue, PICSAccessTokens, extract_manifest_ids, parse_app_vdf
from pysteam.proto import enums_clientserver_pb2 as emsg
from pysteam.proto.steammessages_base_pb2 import CMsgProtoBufHeader
from pysteam.proto.steammessages_clientserver_2_pb2 import CMsgGCClient
from pysteam.proto.steammessages_clientserver_appinfo_pb2 import (
    CMsgClientPICSAccessTokenRequest,
    CMsgClientPICSAccessTokenResponse,
    CMsgClientPICSProductInfoRequest,
    CMsgClientPICSProductInfoResponse,
)
from pysteam.proto.steammessages_clientserver_login_pb2 import (
    CMsgClientHeartBeat,
    CMsgClientHello,
    CMsgClientLogon,
    CMsgClientLogonResponse,
)
from pysteam.protocol import (
    INVALID_JOB_ID,
    MAX_PACKET_SIZE,
    Packet,
    decode_packet,
    encode_packet,
    peek_packet_type,
    unpack_multi_raw,
)

if TYPE_CHECKING:
    from pysteam.auth import AuthenticationClient, GuardChallengeHandler, LoginResult
    from pysteam.cdn import CDNClient
    from pysteam.workshop import WorkshopClient

_LOG = logging.getLogger(__name__)
_T = TypeVar("_T", bound=Message)
_DEFAULT_TIMEOUT = 20.0
_MAX_PENDING = 4096
_UNSET = object()


def _emsg_name(value: int) -> str:
    try:
        return emsg.EMsg.Name(value).removeprefix("k_EMsg")
    except ValueError:
        return "Unknown"


def _os_type() -> int:
    system = platform.system()
    return {"Windows": 16, "Linux": -203, "Darwin": -102}.get(system, 0)


@dataclass(frozen=True, slots=True)
class PICSInfo:
    apps: dict[int, bytes] = field(repr=False)
    packages: dict[int, bytes] = field(repr=False)
    unknown_app_ids: frozenset[int]
    unknown_package_ids: frozenset[int]
    missing_app_tokens: frozenset[int]
    missing_package_tokens: frozenset[int]


class SteamClient:
    """CM transport and core requests. A client is bound to one event loop."""

    def __init__(
        self,
        *,
        cm_endpoints: Sequence[str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        auto_reconnect: bool = True,
        reconnect_delay: float = 1.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout <= 0 or reconnect_delay <= 0:
            raise ValueError("timeout and reconnect delay must be positive")
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect
        self._reconnect_delay = reconnect_delay
        self._endpoints = tuple(cm_endpoints or ())
        self._endpoint_offset = 0
        self._owned_http = http is None
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._ws: ClientConnection | None = None
        self._receiver: asyncio.Task[None] | None = None
        self._heartbeat: asyncio.Task[None] | None = None
        self._reauth_task: asyncio.Task[None] | None = None
        self._resume_anonymous = False
        self._resume_token: str | None = None
        self._resume_steam_id: int | None = None
        self._resume_account_name: str | None = None
        self._resume_auto: (
            tuple[str, LoginCredentials, CredentialStore | None, GuardChallengeHandler | None]
            | None
        ) = None
        self.last_session_error: Exception | None = None
        self._pending: dict[int, asyncio.Queue[Packet | Exception]] = {}
        self._emsg_waiters: dict[int, asyncio.Future[Packet]] = {}
        self._events: asyncio.Queue[Packet] = asyncio.Queue(maxsize=1024)
        self._send_lock = asyncio.Lock()
        self._closed = False
        self._job_id = random.randrange(1, 1 << 32)
        self.steam_id: int | None = None
        self.session_id: int | None = None
        self.cell_id = 0
        self._auth: AuthenticationClient | None = None
        self._cdn: CDNClient | None = None
        self._workshop: WorkshopClient | None = None

    async def __aenter__(self) -> SteamClient:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    @property
    def connected(self) -> bool:
        return self._ws is not None

    @property
    def auth(self) -> AuthenticationClient:
        if self._auth is None:
            from pysteam.auth import AuthenticationClient

            self._auth = AuthenticationClient(self)
        return self._auth

    @property
    def cdn(self) -> CDNClient:
        if self._cdn is None:
            from pysteam.cdn import CDNClient

            self._cdn = CDNClient(self, http=self._http)
        return self._cdn

    @property
    def workshop(self) -> WorkshopClient:
        if self._workshop is None:
            from pysteam.workshop import WorkshopClient

            self._workshop = WorkshopClient(self)
        return self._workshop

    def _next_job_id(self) -> int:
        self._job_id = (self._job_id + 1) % INVALID_JOB_ID or 1
        return self._job_id

    async def _discover(self) -> tuple[str, ...]:
        try:
            response = await self._http.get(
                "https://api.steampowered.com/ISteamDirectory/GetCMListForConnect/v1/",
                params={"cellid": self.cell_id},
            )
            response.raise_for_status()
            data = msgspec.json.decode(response.content)
        except (httpx.HTTPError, msgspec.DecodeError) as exc:
            raise TransportError("CM discovery failed") from exc
        if not isinstance(data, dict) or not isinstance(data.get("response"), dict):
            raise ProtocolError("CM discovery returned an invalid response")
        result = data["response"]
        if result.get("success") not in (True, 1):
            raise TransportError("CM discovery reported failure")
        servers = result.get("serverlist")
        if not isinstance(servers, list):
            raise ProtocolError("CM discovery omitted serverlist")
        endpoints: list[str] = []
        for item in servers:
            if not isinstance(item, dict) or item.get("type") != "websockets":
                continue
            endpoint = item.get("endpoint")
            if (
                isinstance(endpoint, str)
                and endpoint
                and "/" not in endpoint
                and "@" not in endpoint
            ):
                endpoints.append(f"wss://{endpoint}/cmsocket/")
        if not endpoints:
            raise TransportError("CM discovery found no WebSocket endpoints")
        _LOG.debug("CM discovery found %d WebSocket endpoints", len(endpoints))
        return tuple(endpoints)

    async def _open_socket(self) -> ClientConnection:
        endpoints = self._endpoints or await self._discover()
        start = self._endpoint_offset % len(endpoints)
        endpoints = endpoints[start:] + endpoints[:start]
        last_error: Exception | None = None
        for index, candidate in enumerate(endpoints[:8], start=1):
            uri = candidate if candidate.startswith("wss://") else f"wss://{candidate}/cmsocket/"
            if not uri.startswith("wss://"):
                continue
            _LOG.debug("Connecting to CM WebSocket candidate %d", index)
            try:
                socket = await asyncio.wait_for(
                    connect(uri, max_size=MAX_PACKET_SIZE, open_timeout=self.timeout),
                    timeout=self.timeout,
                )
                hello = CMsgClientHello(protocol_version=65581)
                try:
                    await socket.send(encode_packet(emsg.k_EMsgClientHello, hello))
                except Exception:
                    await socket.close()
                    raise
                _LOG.debug("CM WebSocket connected; ClientHello sent")
                return socket
            except (OSError, TimeoutError, WebSocketException) as exc:
                last_error = exc
                _LOG.debug("CM candidate %d failed (%s)", index, type(exc).__name__)
        raise TransportError("could not connect to a CM WebSocket endpoint") from last_error

    async def connect(self) -> None:
        if self._closed:
            raise TransportError("client is closed")
        if self._ws is not None:
            return
        if self._receiver is not None and not self._receiver.done():
            raise TransportError("CM is reconnecting")
        self._ws = await self._open_socket()
        self._receiver = asyncio.create_task(self._receive_loop(), name="pysteam-cm-receiver")

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._heartbeat is not None:
            self._heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat
        if self._reauth_task is not None:
            self._reauth_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reauth_task
        self._resume_token = None
        self._resume_account_name = None
        self._resume_auto = None
        receiver = self._receiver
        if receiver is not None:
            receiver.cancel()
        socket, self._ws = self._ws, None
        if socket is not None:
            await socket.close()
        if receiver is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await receiver
        self._fail_waiters(TransportError("client closed"))
        if self._owned_http:
            await self._http.aclose()

    async def send(
        self,
        emsg_id: int,
        body: Message | bytes,
        *,
        job_name: str | None = None,
        steam_id: int | None = None,
        session_id: int | None = None,
    ) -> None:
        socket = self._ws
        if socket is None:
            raise TransportError("CM is not connected")
        header = CMsgProtoBufHeader()
        effective_steam_id = steam_id if steam_id is not None else self.steam_id
        effective_session_id = session_id if session_id is not None else self.session_id
        if effective_steam_id is not None:
            header.steamid = effective_steam_id
        if effective_session_id is not None:
            header.client_sessionid = effective_session_id
        if job_name is not None:
            header.target_job_name = job_name
        async with self._send_lock:
            try:
                await socket.send(encode_packet(emsg_id, body, header))
                _LOG.debug("CM TX %s (%d)", _emsg_name(emsg_id), emsg_id)
            except (OSError, ConnectionClosed, WebSocketException) as exc:
                raise TransportError("CM send failed") from exc

    async def _request(
        self,
        emsg_id: int,
        body: Message,
        response_emsg: int,
        *,
        timeout: float | None = None,
        job_name: str | None = None,
        until: Any = None,
    ) -> list[Packet]:
        socket = self._ws
        if socket is None:
            raise TransportError("CM is not connected")
        if len(self._pending) >= _MAX_PENDING:
            raise TransportError("too many pending CM requests")
        job_id = self._next_job_id()
        queue: asyncio.Queue[Packet | Exception] = asyncio.Queue(maxsize=32)
        self._pending[job_id] = queue
        header = CMsgProtoBufHeader(jobid_source=job_id)
        if self.steam_id is not None:
            header.steamid = self.steam_id
        if self.session_id is not None:
            header.client_sessionid = self.session_id
        if job_name is not None:
            header.target_job_name = job_name
        packets: list[Packet] = []
        try:
            async with self._send_lock:
                await socket.send(encode_packet(emsg_id, body, header))
                _LOG.debug("CM TX %s (%d)", _emsg_name(emsg_id), emsg_id)
            deadline = asyncio.get_running_loop().time() + (
                self.timeout if timeout is None else timeout
            )
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError
                item = await asyncio.wait_for(queue.get(), remaining)
                if isinstance(item, Exception):
                    raise item
                if item.emsg != response_emsg:
                    raise ProtocolError("CM response EMsg does not match request")
                if item.header.HasField("eresult") and item.header.eresult != 1:
                    raise SteamResultError(job_name or str(emsg_id), item.header.eresult)
                packets.append(item)
                if until is None or until(item):
                    return packets
        except TimeoutError as exc:
            raise RequestTimeout(f"CM request {job_name or emsg_id} timed out") from exc
        except (OSError, ConnectionClosed, WebSocketException) as exc:
            raise TransportError("CM request send failed") from exc
        finally:
            self._pending.pop(job_id, None)

    async def call_um(
        self,
        name: str,
        request: Message,
        response_type: type[_T],
        *,
        timeout: float | None = None,
    ) -> _T:
        if not name or "." not in name or "#" not in name:
            raise ValueError("UM method must be Service.Method#Version")
        request_emsg = (
            emsg.k_EMsgServiceMethodCallFromClient
            if self.steam_id is not None
            else emsg.k_EMsgServiceMethodCallFromClientNonAuthed
        )
        packets = await self._request(
            request_emsg,
            request,
            emsg.k_EMsgServiceMethodResponse,
            timeout=timeout,
            job_name=name,
        )
        response = response_type()
        try:
            response.ParseFromString(packets[0].body)
        except DecodeError as exc:
            raise ProtocolError(f"invalid UM response for {name}") from exc
        return response

    async def _wait_for_emsg(
        self, wanted: int, send_coroutine: Any, *, timeout: float | None = None
    ) -> Packet:
        if wanted in self._emsg_waiters:
            send_coroutine.close()
            raise ProtocolError("another operation is awaiting this EMsg")
        future: asyncio.Future[Packet] = asyncio.get_running_loop().create_future()
        self._emsg_waiters[wanted] = future
        try:
            await send_coroutine
            _LOG.debug("Waiting for CM %s (%d)", _emsg_name(wanted), wanted)
            return await asyncio.wait_for(future, self.timeout if timeout is None else timeout)
        except TimeoutError as exc:
            raise RequestTimeout(f"CM message {wanted} timed out") from exc
        finally:
            self._emsg_waiters.pop(wanted, None)

    async def login_anonymous(self) -> None:
        body = CMsgClientLogon(protocol_version=65581, client_language="english")
        body.client_os_type = _os_type() & 0xFFFFFFFF
        body.cell_id = self.cell_id
        packet = await self._wait_for_emsg(
            emsg.k_EMsgClientLogOnResponse,
            self.send(emsg.k_EMsgClientLogon, body, steam_id=0x01A0000000000000, session_id=0),
        )
        self._accept_logon(packet)
        self._resume_anonymous = True
        self._resume_token = None
        self._resume_steam_id = None
        self._resume_account_name = None
        self._resume_auto = None
        self.last_session_error = None

    async def logon(
        self, refresh_token: str, *, account_name: str, steam_id: int | None = None
    ) -> None:
        if not refresh_token or not account_name:
            raise ValueError("refresh token and account name are required")
        from pysteam.auth import _steam_id_from_jwt

        resolved_id = steam_id or _steam_id_from_jwt(refresh_token)
        await self._logon_refresh_token(refresh_token, resolved_id, account_name)
        self._resume_auto = None

    async def _logon_refresh_token(
        self, refresh_token: str, steam_id: int, account_name: str
    ) -> None:
        _LOG.debug("Starting CM refresh-token logon")
        body = CMsgClientLogon(
            protocol_version=65581,
            access_token=refresh_token,
            account_name=account_name,
            should_remember_password=True,
            client_package_version=1771,
            supports_rate_limit_response=True,
        )
        body.client_language = "english"
        body.client_os_type = _os_type() & 0xFFFFFFFF
        body.cell_id = self.cell_id
        packet = await self._wait_for_emsg(
            emsg.k_EMsgClientLogOnResponse,
            self.send(
                emsg.k_EMsgClientLogon,
                body,
                steam_id=0x0110000100000000,
                session_id=0,
            ),
        )
        self._accept_logon(packet)
        _LOG.debug("CM refresh-token logon accepted")
        if self.steam_id is None:
            self.steam_id = steam_id
        self._resume_anonymous = False
        self._resume_token = refresh_token
        self._resume_steam_id = steam_id
        self._resume_account_name = account_name
        self.last_session_error = None

    async def login_auto(
        self,
        account_name: str,
        *,
        credentials: LoginCredentials | None = None,
        store: CredentialStore | None = None,
        on_challenge: GuardChallengeHandler | None = None,
        timeout: float = 180.0,
    ) -> LoginResult:
        """Log on using a refresh token or credentials and an allowed Guard method."""
        if not account_name or timeout <= 0:
            raise ValueError("account name and positive timeout are required")
        try:
            async with asyncio.timeout(timeout):
                result = await self._login_auto(account_name, credentials, store, on_challenge)
                supplied = credentials or LoginCredentials()
                self._resume_auto = (
                    account_name,
                    LoginCredentials(
                        supplied.password,
                        supplied.shared_secret,
                        result.tokens.refresh_token,
                        result.tokens.steam_id,
                        result.tokens.guard_data,
                    ),
                    store,
                    on_challenge,
                )
                return result
        except TimeoutError as exc:
            raise RequestTimeout("automatic login timed out") from exc

    async def login_saved(
        self,
        account_name: str | None = None,
        *,
        passphrase: str | None = None,
        profile_dir: str | Path | None = None,
        on_challenge: GuardChallengeHandler | None = None,
        timeout: float = 180.0,
    ) -> LoginResult:
        """Log in with an explicitly registered account profile.

        This is opt-in; constructing a SteamClient never reads local profiles.
        The SDK does not prompt for a missing encryption passphrase.
        """
        from pysteam.profiles import ProfileRegistry
        from pysteam.vault import Vault, vault_passphrase

        profile = ProfileRegistry(profile_dir).select(account_name)
        secret = vault_passphrase(passphrase)
        if not secret:
            raise ProfileError("set PYSTEAM_VAULT_PASSPHRASE or pass a vault password")
        if profile.store_path.parent.name == "accounts":
            secret_bytes: str | bytes = Vault.open(secret, profile_dir).credential_passphrase
        else:
            secret_bytes = secret
        store = EncryptedFileCredentialStore(profile.store_path, secret_bytes)
        saved = await store.load(profile.account_name)
        if saved is None or saved.steam_id != profile.steam_id:
            raise ProfileError("saved account credentials are missing or mismatched")
        result = await self.login_auto(
            profile.account_name,
            credentials=saved,
            store=store,
            on_challenge=on_challenge,
            timeout=timeout,
        )
        if result.tokens.steam_id != profile.steam_id:
            raise ProfileError("signed-in SteamID does not match its profile")
        return result

    async def _login_auto(
        self,
        account_name: str,
        credentials: LoginCredentials | None,
        store: CredentialStore | None,
        on_challenge: GuardChallengeHandler | None,
    ) -> LoginResult:
        from pysteam.auth import (
            AuthenticationInteractionRequired,
            AuthTokens,
            GuardChallenge,
            LoginResult,
            _steam_id_from_jwt,
        )
        from pysteam.guard import guard_code

        stored = await store.load(account_name) if store is not None else None
        supplied = credentials or LoginCredentials()
        material = supplied.with_fallback(stored)

        token_failure: Exception | None = None
        if material.refresh_token:
            _LOG.debug("Automatic login: trying refresh token")
            try:
                steam_id = material.steam_id or _steam_id_from_jwt(material.refresh_token)
            except ProtocolError as exc:
                token_failure = exc
            else:
                try:
                    await self._logon_refresh_token(material.refresh_token, steam_id, account_name)
                except SteamResultError as exc:
                    if exc.eresult not in {5, 26, 27}:
                        raise
                    _LOG.debug("Automatic login: refresh token rejected (EResult %d)", exc.eresult)
                    token_failure = exc
                else:
                    _LOG.debug("Automatic login: renewing access token after CM logon")
                    result = await self.auth.generate_access_token_result(
                        material.refresh_token, steam_id=steam_id, allow_renewal=True
                    )
                    self._resume_token = result.refresh_token
                    if store is not None:
                        await store.save(
                            account_name,
                            LoginCredentials(
                                material.password,
                                material.shared_secret,
                                result.refresh_token,
                                steam_id,
                                material.guard_data,
                            ),
                        )
                    refresh_tokens = AuthTokens(
                        steam_id,
                        account_name,
                        result.refresh_token,
                        result.access_token,
                        material.guard_data or "",
                    )
                    return LoginResult("refresh_token", refresh_tokens)

        if not material.password:
            if token_failure is not None:
                raise token_failure
            raise ValueError("a password or refresh token is required")
        _LOG.debug("Automatic login: starting credential authentication")
        session = await self.auth.begin_credentials(
            account_name,
            material.password,
            guard_data=material.guard_data or "",
            remember_login=True,
        )
        credential_tokens = await session.poll()
        if credential_tokens is None:
            confirmations = session.allowed_confirmations
            device = 3  # EAuthSessionGuardType.DeviceCode
            email = 2  # EAuthSessionGuardType.EmailCode
            if 1 in confirmations:  # None
                pass
            elif device in confirmations and material.shared_secret:
                _LOG.debug("Automatic login: using an allowed device code")
                try:
                    offset = await self.auth.steam_time_offset()
                except (SteamError, ValueError):
                    offset = 0.0
                timestamp = int(time.time() + offset)
                try:
                    await session.submit_guard_code(
                        guard_code(material.shared_secret, timestamp=timestamp), code_type=device
                    )
                except AuthenticationError as exc:
                    if exc.eresult != 88:  # TwoFactorCodeMismatch
                        raise
                    _LOG.debug("Automatic login: device code mismatch; waiting for next window")
                    delay = 30 - ((time.time() + offset) % 30) + 0.25
                    await asyncio.sleep(delay)
                    try:
                        offset = await self.auth.steam_time_offset()
                    except (SteamError, ValueError):
                        pass
                    await session.submit_guard_code(
                        guard_code(material.shared_secret, timestamp=int(time.time() + offset)),
                        code_type=device,
                    )
            else:
                selected = next(
                    (item for item in (device, email, 4, 5) if item in confirmations),
                    confirmations[0] if confirmations else 0,
                )
                if on_challenge is None:
                    raise AuthenticationInteractionRequired(session, selected)
                _LOG.debug("Automatic login: requesting confirmation type %d", selected)
                position = confirmations.index(selected) if selected in confirmations else -1
                message = (
                    session.confirmation_messages[position]
                    if position < len(session.confirmation_messages) and position >= 0
                    else ""
                )
                code = await on_challenge(GuardChallenge(selected, message, session))
                if selected in (device, email):
                    if not code:
                        raise AuthenticationInteractionRequired(session, selected)
                    await session.submit_guard_code(code, code_type=selected)
                elif selected not in (4, 5):
                    raise AuthenticationInteractionRequired(session, selected)
            credential_tokens = await session.wait_for_tokens()

        authenticated_name = credential_tokens.account_name or account_name
        if authenticated_name.casefold() != account_name.casefold():
            raise ProtocolError("authenticated account does not match the requested account")
        _LOG.debug("Automatic login: credential session issued tokens")
        refresh_token = credential_tokens.refresh_token
        guard_data = credential_tokens.guard_data or material.guard_data or ""
        if store is not None:
            await store.save(
                account_name,
                LoginCredentials(
                    material.password,
                    material.shared_secret,
                    refresh_token,
                    credential_tokens.steam_id,
                    guard_data,
                ),
            )
        await self._logon_refresh_token(refresh_token, credential_tokens.steam_id, account_name)
        access_token = credential_tokens.access_token
        if not access_token:
            replacement = await self.auth.generate_access_token_result(
                refresh_token, steam_id=credential_tokens.steam_id, allow_renewal=True
            )
            refresh_token, access_token = replacement.refresh_token, replacement.access_token
            self._resume_token = refresh_token
            if store is not None:
                await store.save(
                    account_name,
                    LoginCredentials(
                        material.password,
                        material.shared_secret,
                        refresh_token,
                        credential_tokens.steam_id,
                        guard_data,
                    ),
                )
        tokens = AuthTokens(
            credential_tokens.steam_id,
            authenticated_name,
            refresh_token,
            access_token,
            guard_data,
        )
        return LoginResult("credentials", tokens)

    def _accept_logon(self, packet: Packet) -> None:
        result = CMsgClientLogonResponse()
        try:
            result.ParseFromString(packet.body)
        except DecodeError as exc:
            raise ProtocolError("invalid logon response") from exc
        if result.eresult != 1:
            raise SteamResultError("CM logon", result.eresult)
        self.steam_id = packet.header.steamid or result.client_supplied_steamid or None
        self.session_id = (
            packet.header.client_sessionid if packet.header.HasField("client_sessionid") else None
        )
        self.cell_id = result.cell_id
        if self._heartbeat is not None:
            self._heartbeat.cancel()
        if result.heartbeat_seconds > 0:
            self._heartbeat = asyncio.create_task(
                self._heartbeat_loop(result.heartbeat_seconds), name="pysteam-heartbeat"
            )

    async def _heartbeat_loop(self, interval: int) -> None:
        try:
            while not self._closed and self.connected:
                await asyncio.sleep(interval)
                await self.send(emsg.k_EMsgClientHeartBeat, CMsgClientHeartBeat())
        except (asyncio.CancelledError, TransportError):
            return

    async def get_product_info(
        self,
        *,
        app_ids: Sequence[int] = (),
        package_ids: Sequence[int] = (),
        app_tokens: dict[int, int] | None = None,
        package_tokens: dict[int, int] | None = None,
        timeout: float | None = None,
    ) -> PICSInfo:
        if not app_ids and not package_ids:
            raise ValueError("provide at least one app or package ID")
        request = CMsgClientPICSProductInfoRequest()
        request.single_response = False
        for app_id in app_ids:
            if not 0 <= app_id <= 0xFFFFFFFF:
                raise ValueError("app ID out of range")
            app_entry = request.apps.add()
            app_entry.appid = app_id
            if app_tokens and app_id in app_tokens:
                app_entry.access_token = app_tokens[app_id]
        for package_id in package_ids:
            if not 0 <= package_id <= 0xFFFFFFFF:
                raise ValueError("package ID out of range")
            package_entry = request.packages.add()
            package_entry.packageid = package_id
            if package_tokens and package_id in package_tokens:
                package_entry.access_token = package_tokens[package_id]

        def complete(packet: Packet) -> bool:
            response = CMsgClientPICSProductInfoResponse()
            try:
                response.ParseFromString(packet.body)
            except DecodeError as exc:
                raise ProtocolError("invalid PICS response") from exc
            return not response.response_pending

        packets = await self._request(
            emsg.k_EMsgClientPICSProductInfoRequest,
            request,
            emsg.k_EMsgClientPICSProductInfoResponse,
            timeout=timeout,
            until=complete,
        )
        apps: dict[int, bytes] = {}
        packages: dict[int, bytes] = {}
        unknown_apps: set[int] = set()
        unknown_packages: set[int] = set()
        missing_apps: set[int] = set()
        missing_packages: set[int] = set()
        for packet in packets:
            response = CMsgClientPICSProductInfoResponse()
            try:
                response.ParseFromString(packet.body)
            except DecodeError as exc:
                raise ProtocolError("invalid PICS response") from exc
            apps.update({item.appid: item.buffer for item in response.apps})
            packages.update({item.packageid: item.buffer for item in response.packages})
            unknown_apps.update(response.unknown_appids)
            unknown_packages.update(response.unknown_packageids)
            missing_apps.update(item.appid for item in response.apps if item.missing_token)
            missing_packages.update(
                item.packageid for item in response.packages if item.missing_token
            )
        return PICSInfo(
            apps,
            packages,
            frozenset(unknown_apps),
            frozenset(unknown_packages),
            frozenset(missing_apps),
            frozenset(missing_packages),
        )

    async def get_access_tokens(
        self,
        *,
        app_ids: Sequence[int] = (),
        package_ids: Sequence[int] = (),
        timeout: float | None = None,
    ) -> PICSAccessTokens:
        """Request access tokens for PICS app and package metadata."""
        if not app_ids and not package_ids:
            raise ValueError("provide at least one app or package ID")
        for item_id in (*app_ids, *package_ids):
            if not 0 <= item_id <= 0xFFFFFFFF:
                raise ValueError("PICS ID out of range")
        request = CMsgClientPICSAccessTokenRequest(appids=app_ids, packageids=package_ids)
        packet = (
            await self._request(
                emsg.k_EMsgClientPICSAccessTokenRequest,
                request,
                emsg.k_EMsgClientPICSAccessTokenResponse,
                timeout=timeout,
            )
        )[0]
        response = CMsgClientPICSAccessTokenResponse()
        try:
            response.ParseFromString(packet.body)
        except DecodeError as exc:
            raise ProtocolError("invalid PICS access-token response") from exc
        return PICSAccessTokens(
            apps={item.appid: item.access_token for item in response.app_access_tokens},
            packages={item.packageid: item.access_token for item in response.package_access_tokens},
            denied_app_ids=frozenset(response.app_denied_tokens),
            denied_package_ids=frozenset(response.package_denied_tokens),
        )

    async def get_app_info(
        self,
        app_id: int,
        *,
        access_token: int | None = None,
        auto_access_token: bool = True,
        timeout: float | None = None,
    ) -> dict[str, KVValue]:
        """Fetch and parse a text VDF PICS app-info response."""
        result = await self.get_product_info(
            app_ids=(app_id,),
            app_tokens={app_id: access_token} if access_token is not None else None,
            timeout=timeout,
        )
        if app_id in result.missing_app_tokens:
            if not auto_access_token or access_token is not None:
                raise ProtocolError("PICS app info requires a valid access token")
            tokens = await self.get_access_tokens(app_ids=(app_id,), timeout=timeout)
            token = tokens.apps.get(app_id)
            if token is None:
                raise ProtocolError("PICS app access token is unavailable")
            result = await self.get_product_info(
                app_ids=(app_id,), app_tokens={app_id: token}, timeout=timeout
            )
            if app_id in result.missing_app_tokens:
                raise ProtocolError("PICS app access token was rejected")
        payload = result.apps.get(app_id)
        if payload is None:
            raise KeyError(app_id)
        app_info = parse_app_vdf(payload)
        if app_info.get("appid") != str(app_id):
            raise ProtocolError("PICS app-info ID does not match the request")
        return app_info

    async def get_app_manifest_ids(
        self,
        app_id: int,
        *,
        branch: str = "public",
        access_token: int | None = None,
        timeout: float | None = None,
    ) -> dict[int, int]:
        """Return depot manifest IDs from PICS app info for one branch."""
        app_info = await self.get_app_info(app_id, access_token=access_token, timeout=timeout)
        return extract_manifest_ids(app_info, branch=branch)

    async def send_gc(self, app_id: int, msg_type: int, payload: bytes) -> None:
        if not 0 <= app_id <= 0xFFFFFFFF or not 0 <= msg_type <= 0xFFFFFFFF:
            raise ValueError("GC app ID or message type out of range")
        await self.send(
            emsg.k_EMsgClientToGC, CMsgGCClient(appid=app_id, msgtype=msg_type, payload=payload)
        )

    async def recv_packet(self, *, timeout: float | None = None) -> Packet:
        try:
            return await asyncio.wait_for(
                self._events.get(), self.timeout if timeout is None else timeout
            )
        except TimeoutError as exc:
            raise RequestTimeout("no CM event received") from exc

    async def recv_gc(self, *, timeout: float | None = None) -> CMsgGCClient:
        deadline = asyncio.get_running_loop().time() + (
            self.timeout if timeout is None else timeout
        )
        while True:
            packet = await self.recv_packet(timeout=deadline - asyncio.get_running_loop().time())
            if packet.emsg == emsg.k_EMsgClientFromGC:
                message = CMsgGCClient()
                try:
                    message.ParseFromString(packet.body)
                except DecodeError as exc:
                    raise ProtocolError("invalid GC packet") from exc
                return message

    async def _receive_loop(self) -> None:
        delay = self._reconnect_delay
        while not self._closed:
            socket = self._ws
            if socket is None:
                return
            try:
                async for raw in socket:
                    if not isinstance(raw, bytes):
                        raise ProtocolError("CM sent a text WebSocket frame")
                    await self._dispatch_wire(raw, depth=0)
                failure: Exception = TransportError("CM closed the connection")
            except asyncio.CancelledError:
                return
            except ConnectionClosed as exc:
                close = exc.rcvd or exc.sent
                failure = TransportError(
                    f"CM WebSocket closed with code {close.code}"
                    if close is not None
                    else "CM WebSocket closed without a close frame"
                )
                _LOG.debug("CM receiver stopped: ConnectionClosed")
            except (TransportError, ProtocolError) as exc:
                failure = exc
                _LOG.debug("CM receiver stopped: %s", type(exc).__name__)
            except Exception as exc:
                failure = TransportError(f"CM receiver failed ({type(exc).__name__})")
                _LOG.debug("CM receiver stopped: %s", type(exc).__name__)
            with contextlib.suppress(Exception):
                await socket.close()
            self._ws = None
            self._endpoint_offset += 1
            self.steam_id = None
            self.session_id = None
            if self._reauth_task is not None:
                self._reauth_task.cancel()
                self._reauth_task = None
            if self._heartbeat is not None:
                self._heartbeat.cancel()
                self._heartbeat = None
            self._fail_waiters(failure)
            if not self.auto_reconnect or self._closed:
                return
            await asyncio.sleep(delay + random.uniform(0, delay / 4))
            try:
                self._ws = await self._open_socket()
                delay = self._reconnect_delay
                if self._resume_anonymous or self._resume_token is not None or self._resume_auto:
                    self._reauth_task = asyncio.create_task(
                        self._restore_session(), name="pysteam-session-restore"
                    )
            except (TransportError, ProtocolError):
                delay = min(delay * 2, 30.0)

    async def _restore_session(self) -> None:
        try:
            if self._resume_anonymous:
                await self.login_anonymous()
            elif self._resume_auto is not None:
                account_name, credentials, store, on_challenge = self._resume_auto
                await self.login_auto(
                    account_name,
                    credentials=credentials,
                    store=store,
                    on_challenge=on_challenge,
                )
            elif self._resume_token is not None and self._resume_account_name is not None:
                await self.logon(
                    self._resume_token,
                    steam_id=self._resume_steam_id,
                    account_name=self._resume_account_name,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_session_error = exc
            _LOG.warning("CM session restoration failed: %s", type(exc).__name__)

    async def _dispatch_wire(self, raw: bytes, *, depth: int) -> None:
        emsg_id, is_proto = peek_packet_type(raw)
        if not is_proto:
            if len(raw) < 20:
                raise ProtocolError("legacy CM packet is truncated")
            if emsg_id == emsg.k_EMsgClientLogOnResponse:
                raise TransportError("CM sent a legacy logon response")
            if emsg_id in (emsg.k_EMsgClientLoggedOff, emsg.k_EMsgClientServerUnavailable):
                raise TransportError(f"CM sent legacy control EMsg {emsg_id}")
            _LOG.debug("CM RX legacy %s (%d) skipped", _emsg_name(emsg_id), emsg_id)
            return
        packet = decode_packet(raw)
        label = f"CM RX {'>' * depth}" if depth else "CM RX"
        _LOG.debug("%s %s (%d)", label, _emsg_name(packet.emsg), packet.emsg)
        await self._dispatch(packet, depth=depth)

    async def _dispatch(self, packet: Packet, *, depth: int) -> None:
        if packet.emsg == emsg.k_EMsgMulti:
            if depth >= 4:
                raise ProtocolError("nested multi-message depth exceeded")
            for raw in unpack_multi_raw(packet):
                await self._dispatch_wire(raw, depth=depth + 1)
            return
        if packet.emsg == emsg.k_EMsgClientServerUnavailable:
            self._events.put_nowait(packet)
            raise TransportError("CM reported a server unavailable")
        job_id = packet.header.jobid_target
        queue = self._pending.get(job_id)
        if queue is not None:
            try:
                if packet.emsg == emsg.k_EMsgDestJobFailed:
                    result = packet.header.eresult if packet.header.HasField("eresult") else 2
                    queue.put_nowait(SteamResultError("CM destination job", result))
                else:
                    queue.put_nowait(packet)
            except asyncio.QueueFull as exc:
                raise ProtocolError("CM request response queue overflow") from exc
            return
        waiter = self._emsg_waiters.get(packet.emsg)
        if waiter is not None and not waiter.done():
            waiter.set_result(packet)
            return
        try:
            self._events.put_nowait(packet)
        except asyncio.QueueFull as exc:
            raise ProtocolError("CM event queue overflow") from exc

    def _fail_waiters(self, error: Exception) -> None:
        for queue in self._pending.values():
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(error)
        for future in self._emsg_waiters.values():
            if not future.done():
                future.set_exception(error)
