"""Async Steam CM client over secure WebSocket connections."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
import msgspec
from google.protobuf.message import DecodeError, Message
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from pysteam.errors import (
    ProtocolError,
    RequestTimeout,
    SteamResultError,
    TransportError,
)
from pysteam.proto import enums_clientserver_pb2 as emsg
from pysteam.proto.steammessages_base_pb2 import CMsgProtoBufHeader
from pysteam.proto.steammessages_clientserver_2_pb2 import CMsgGCClient
from pysteam.proto.steammessages_clientserver_appinfo_pb2 import (
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
    unpack_multi,
)

if TYPE_CHECKING:
    from pysteam.auth import AuthenticationClient
    from pysteam.cdn import CDNClient

_LOG = logging.getLogger(__name__)
_T = TypeVar("_T", bound=Message)
_DEFAULT_TIMEOUT = 20.0
_MAX_PENDING = 4096
_UNSET = object()


def _os_type() -> int:
    system = platform.system()
    return {"Windows": 16, "Linux": -203, "Darwin": -102}.get(system, 0)


@dataclass(frozen=True, slots=True)
class PICSInfo:
    apps: dict[int, bytes]
    packages: dict[int, bytes]
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
        return tuple(endpoints)

    async def _open_socket(self) -> ClientConnection:
        endpoints = self._endpoints or await self._discover()
        start = self._endpoint_offset % len(endpoints)
        endpoints = endpoints[start:] + endpoints[:start]
        last_error: Exception | None = None
        for candidate in endpoints[:8]:
            uri = candidate if candidate.startswith("wss://") else f"wss://{candidate}/cmsocket/"
            if not uri.startswith("wss://"):
                continue
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
                return socket
            except (OSError, TimeoutError, WebSocketException) as exc:
                last_error = exc
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
        self.last_session_error = None

    async def logon(self, refresh_token: str, *, steam_id: int | None = None) -> None:
        if not refresh_token:
            raise ValueError("refresh token is empty")
        from pysteam.auth import _steam_id_from_jwt

        resolved_id = steam_id or _steam_id_from_jwt(refresh_token)
        access_token = await self.auth.generate_access_token(refresh_token, steam_id=resolved_id)
        body = CMsgClientLogon(protocol_version=65581, access_token=access_token)
        body.client_language = "english"
        body.client_os_type = _os_type() & 0xFFFFFFFF
        body.cell_id = self.cell_id
        body.client_supplied_steam_id = resolved_id
        packet = await self._wait_for_emsg(
            emsg.k_EMsgClientLogOnResponse,
            self.send(emsg.k_EMsgClientLogon, body, steam_id=resolved_id, session_id=0),
        )
        self._accept_logon(packet)
        self._resume_anonymous = False
        self._resume_token = refresh_token
        self._resume_steam_id = resolved_id
        self.last_session_error = None

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
                    await self._dispatch(decode_packet(raw), depth=0)
                failure: Exception = TransportError("CM closed the connection")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                failure = (
                    exc
                    if isinstance(exc, TransportError)
                    else TransportError("CM connection ended")
                )
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
                if self._resume_anonymous or self._resume_token is not None:
                    self._reauth_task = asyncio.create_task(
                        self._restore_session(), name="pysteam-session-restore"
                    )
            except (TransportError, ProtocolError):
                delay = min(delay * 2, 30.0)

    async def _restore_session(self) -> None:
        try:
            if self._resume_anonymous:
                await self.login_anonymous()
            elif self._resume_token is not None:
                await self.logon(self._resume_token, steam_id=self._resume_steam_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_session_error = exc
            _LOG.warning("CM session restoration failed: %s", type(exc).__name__)

    async def _dispatch(self, packet: Packet, *, depth: int) -> None:
        if packet.emsg == emsg.k_EMsgMulti:
            if depth >= 4:
                raise ProtocolError("nested multi-message depth exceeded")
            for nested in unpack_multi(packet):
                await self._dispatch(nested, depth=depth + 1)
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
