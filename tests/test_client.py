import asyncio

import httpx
import pytest

from pysteam import RequestTimeout, SteamClient, SteamResultError, TransportError
from pysteam.proto import enums_clientserver_pb2 as emsg
from pysteam.proto.steammessages_base_pb2 import CMsgProtoBufHeader
from pysteam.proto.steammessages_clientserver_2_pb2 import CMsgGCClient
from pysteam.proto.steammessages_clientserver_appinfo_pb2 import (
    CMsgClientPICSAccessTokenResponse,
    CMsgClientPICSProductInfoRequest,
    CMsgClientPICSProductInfoResponse,
)
from pysteam.proto.steammessages_clientserver_login_pb2 import CMsgClientHello
from pysteam.protocol import decode_packet, encode_packet


class FakeSocket:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.sent: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, data: bytes) -> None:
        await self.sent.put(data)

    async def close(self) -> None:
        await self.incoming.put(None)

    async def __aiter__(self):
        while True:
            item = await self.incoming.get()
            if item is None:
                break
            yield item


def _ready_client() -> tuple[SteamClient, FakeSocket]:
    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"], auto_reconnect=False)
    socket = FakeSocket()
    client._ws = socket  # type: ignore[assignment]
    client._receiver = asyncio.create_task(client._receive_loop())
    return client, socket


@pytest.mark.asyncio
async def test_um_job_correlation_and_pics_response() -> None:
    client, socket = _ready_client()
    try:
        first = asyncio.create_task(
            client.call_um("Test.One#1", CMsgClientHello(), CMsgClientHello)
        )
        second = asyncio.create_task(
            client.call_um("Test.Two#1", CMsgClientHello(), CMsgClientHello)
        )
        sent = [decode_packet(await socket.sent.get()) for _ in range(2)]
        assert sent[0].header.jobid_source != sent[1].header.jobid_source
        for packet in reversed(sent):
            reply = CMsgClientHello(protocol_version=packet.header.jobid_source & 0xFFFF)
            header = CMsgProtoBufHeader(jobid_target=packet.header.jobid_source)
            await socket.incoming.put(
                encode_packet(emsg.k_EMsgServiceMethodResponse, reply, header)
            )
        await asyncio.gather(first, second)

        pics = asyncio.create_task(client.get_product_info(app_ids=[10], timeout=1))
        request = decode_packet(await socket.sent.get())
        first_response = CMsgClientPICSProductInfoResponse(response_pending=True)
        first_response.apps.add(appid=10, buffer=b"app data")
        final_response = CMsgClientPICSProductInfoResponse(response_pending=False)
        for response in (first_response, final_response):
            await socket.incoming.put(
                encode_packet(
                    emsg.k_EMsgClientPICSProductInfoResponse,
                    response,
                    CMsgProtoBufHeader(jobid_target=request.header.jobid_source),
                )
            )
        assert (await pics).apps == {10: b"app data"}
        assert not client._pending
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_malformed_cm_packet_fails_pending_request() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(
            client.call_um("Test.One#1", CMsgClientHello(), CMsgClientHello)
        )
        await socket.sent.get()
        await socket.incoming.put(b"bad")
        with pytest.raises(TransportError):
            await asyncio.wait_for(pending, 1)
        assert not client.connected
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_send_without_connection() -> None:
    async with asyncio.timeout(1):
        client = SteamClient()
        with pytest.raises(TransportError):
            await client.send(emsg.k_EMsgClientHello, CMsgClientHello())
        await client.aclose()


@pytest.mark.asyncio
async def test_destination_job_failure() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(
            client.call_um("Test.Failure#1", CMsgClientHello(), CMsgClientHello)
        )
        request = decode_packet(await socket.sent.get())
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgDestJobFailed,
                b"",
                CMsgProtoBufHeader(jobid_target=request.header.jobid_source, eresult=15),
            )
        )
        with pytest.raises(SteamResultError) as captured:
            await pending
        assert captured.value.eresult == 15
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_gc_send_receive() -> None:
    client, socket = _ready_client()
    try:
        await client.send_gc(570, 10, b"hello")
        request = decode_packet(await socket.sent.get())
        assert request.emsg == emsg.k_EMsgClientToGC
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgClientFromGC,
                CMsgGCClient(appid=570, msgtype=11, payload=b"world"),
            )
        )
        reply = await client.recv_gc(timeout=1)
        assert (reply.appid, reply.msgtype, reply.payload) == (570, 11, b"world")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_discovery_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"success": 1, "serverlist": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SteamClient(http=http)
        with pytest.raises(TransportError):
            await client._discover()
        await client.aclose()


@pytest.mark.asyncio
async def test_websocket_connect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_connect(*_args, **_kwargs):
        raise OSError("synthetic socket failure")

    monkeypatch.setattr("pysteam.client.connect", fail_connect)
    client = SteamClient(cm_endpoints=["wss://unavailable.invalid/cmsocket/"], timeout=0.1)
    try:
        with pytest.raises(TransportError):
            await client.connect()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cm_server_unavailable_event() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(
            client.call_um("Test.One#1", CMsgClientHello(), CMsgClientHello)
        )
        await socket.sent.get()
        await socket.incoming.put(encode_packet(emsg.k_EMsgClientServerUnavailable, b""))
        with pytest.raises(TransportError, match="server unavailable"):
            await pending
        assert (await client.recv_packet(timeout=1)).emsg == emsg.k_EMsgClientServerUnavailable
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_reconnect_restores_session_and_cancellation_cleans_job() -> None:
    client = SteamClient(
        cm_endpoints=["wss://one.invalid/cmsocket/", "wss://two.invalid/cmsocket/"],
        auto_reconnect=True,
        reconnect_delay=0.01,
    )
    old_socket, new_socket = FakeSocket(), FakeSocket()
    client._ws = old_socket  # type: ignore[assignment]
    client._resume_anonymous = True
    restored = asyncio.Event()

    async def open_new():
        return new_socket

    async def restore():
        restored.set()

    client._open_socket = open_new  # type: ignore[method-assign]
    client._restore_session = restore  # type: ignore[method-assign]
    client._receiver = asyncio.create_task(client._receive_loop())
    try:
        pending = asyncio.create_task(
            client.call_um("Test.One#1", CMsgClientHello(), CMsgClientHello)
        )
        await old_socket.sent.get()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not client._pending
        await old_socket.incoming.put(None)
        await asyncio.wait_for(restored.wait(), 1)
        assert client._ws is new_socket
        assert client._endpoint_offset == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_request_timeout_removes_waiter() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(
            client.call_um("Test.Timeout#1", CMsgClientHello(), CMsgClientHello, timeout=0.01)
        )
        request = decode_packet(await socket.sent.get())
        with pytest.raises(RequestTimeout):
            await pending
        assert not client._pending
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgServiceMethodResponse,
                CMsgClientHello(),
                CMsgProtoBufHeader(jobid_target=request.header.jobid_source),
            )
        )
        assert (await client.recv_packet(timeout=1)).emsg == emsg.k_EMsgServiceMethodResponse
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pics_access_tokens() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(client.get_access_tokens(app_ids=[570], package_ids=[1]))
        request = decode_packet(await socket.sent.get())
        assert request.emsg == emsg.k_EMsgClientPICSAccessTokenRequest
        response = CMsgClientPICSAccessTokenResponse()
        response.app_access_tokens.add(appid=570, access_token=123)
        response.package_denied_tokens.append(1)
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgClientPICSAccessTokenResponse,
                response,
                CMsgProtoBufHeader(jobid_target=request.header.jobid_source),
            )
        )
        tokens = await pending
        assert tokens.apps == {570: 123}
        assert tokens.denied_package_ids == frozenset({1})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_app_info_retries_with_access_token() -> None:
    client, socket = _ready_client()
    try:
        pending = asyncio.create_task(client.get_app_manifest_ids(570))
        first = decode_packet(await socket.sent.get())
        assert first.emsg == emsg.k_EMsgClientPICSProductInfoRequest
        missing = CMsgClientPICSProductInfoResponse()
        missing.apps.add(appid=570, missing_token=True)
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgClientPICSProductInfoResponse,
                missing,
                CMsgProtoBufHeader(jobid_target=first.header.jobid_source),
            )
        )

        access = decode_packet(await socket.sent.get())
        assert access.emsg == emsg.k_EMsgClientPICSAccessTokenRequest
        tokens = CMsgClientPICSAccessTokenResponse()
        tokens.app_access_tokens.add(appid=570, access_token=123)
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgClientPICSAccessTokenResponse,
                tokens,
                CMsgProtoBufHeader(jobid_target=access.header.jobid_source),
            )
        )

        second = decode_packet(await socket.sent.get())
        assert second.emsg == emsg.k_EMsgClientPICSProductInfoRequest
        request = CMsgClientPICSProductInfoRequest.FromString(second.body)
        assert request.apps[0].access_token == 123
        found = CMsgClientPICSProductInfoResponse()
        found.apps.add(
            appid=570,
            buffer=(
                b'"appinfo" { "appid" "570" "depots" { '
                b'"1" { "manifests" { "public" { "gid" "2" } } } } }'
            ),
        )
        await socket.incoming.put(
            encode_packet(
                emsg.k_EMsgClientPICSProductInfoResponse,
                found,
                CMsgProtoBufHeader(jobid_target=second.header.jobid_source),
            )
        )
        assert await pending == {1: 2}
    finally:
        await client.aclose()
