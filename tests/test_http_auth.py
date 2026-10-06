import base64

import httpx
import msgspec
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from pysteam import (
    AuthenticationClient,
    AuthenticationError,
    ProtocolError,
    SteamResultError,
    TransportError,
    WebAPIClient,
    WebAPIError,
)
from pysteam.proto import steammessages_auth_steamclient_pb2 as auth_proto


@pytest.mark.asyncio
async def test_webapi_result_and_key_redaction() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "private-test-key"
        assert request.extensions["timeout"]["read"] == 20.0
        return httpx.Response(200, json={"response": {"eresult": 1, "value": 42}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        api = WebAPIClient(key="private-test-key", http=http)
        assert (await api.call("ITest", "GetThing"))["value"] == 42

    async def error_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(error_handler)) as http:
        api = WebAPIClient(key="private-test-key", http=http)
        with pytest.raises(TransportError) as captured:
            await api.call("ITest", "GetThing")
        assert captured.value.__cause__ is None
        assert "private-test-key" not in str(captured.value)

    async def steam_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"eresult": 15}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(steam_error)) as http:
        with pytest.raises(SteamResultError) as captured:
            await WebAPIClient(http=http).call("ITest", "GetThing")
        assert captured.value.eresult == 15
        assert captured.value.response_body == {"eresult": 15}


@pytest.mark.asyncio
async def test_webapi_typed_response_and_http_error_body() -> None:
    class Result(msgspec.Struct):
        count: int

    async def good(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"count": 3}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(good)) as http:
        assert (await WebAPIClient(http=http).call_typed("ITest", "GetThing", Result)).count == 3

    async def denied(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"playerstats": {"error": "Profile is not public"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(denied)) as http:
        with pytest.raises(WebAPIError) as captured:
            await WebAPIClient(http=http).call("ITest", "GetThing")
        assert captured.value.status_code == 403
        assert captured.value.response_body == {"playerstats": {"error": "Profile is not public"}}


@pytest.mark.asyncio
async def test_auth_result_code_preserved() -> None:
    class RateLimitedCM:
        async def call_um(self, _name, _request, _response_type):
            raise SteamResultError("QR authentication", 84)

    with pytest.raises(AuthenticationError) as captured:
        await AuthenticationClient(RateLimitedCM()).begin_qr()
    assert captured.value.eresult == 84


class FakeAuthCM:
    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.request: auth_proto.CAuthentication_BeginAuthSessionViaCredentials_Request | None = (
            None
        )

    async def call_um(self, name, request, _response_type):
        if "GetPasswordRSAPublicKey" in name:
            numbers = self.private_key.public_key().public_numbers()
            return auth_proto.CAuthentication_GetPasswordRSAPublicKey_Response(
                publickey_mod=format(numbers.n, "x"),
                publickey_exp=format(numbers.e, "x"),
                timestamp=123,
            )
        if "BeginAuthSessionViaCredentials" in name:
            self.request = request
            return auth_proto.CAuthentication_BeginAuthSessionViaCredentials_Response(
                client_id=1, request_id=b"request", interval=1, steamid=76561198000000000
            )
        raise AssertionError(name)


@pytest.mark.asyncio
async def test_credential_auth_challenge_request() -> None:
    fake = FakeAuthCM()
    session = await AuthenticationClient(fake).begin_credentials("user", "password")
    assert session.client_id == 1
    assert fake.request is not None
    assert fake.request.account_name == "user"
    assert fake.request.encryption_timestamp == 123
    assert base64.b64decode(fake.request.encrypted_password)
    with pytest.raises(ValueError):
        await session.submit_guard_code("12345", code_type=999)


@pytest.mark.asyncio
async def test_webapi_rejects_invalid_json() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ProtocolError):
            await WebAPIClient(http=http).call("ITest", "GetThing")


@pytest.mark.asyncio
async def test_http_error_result() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"response": {"eresult": 15}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SteamResultError) as captured:
            await WebAPIClient(http=http).call("ITest", "GetThing")
        assert captured.value.eresult == 15
