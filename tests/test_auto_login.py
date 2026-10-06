import asyncio
import base64
import json
import logging
import os
from pathlib import Path

import httpx
import pytest

from pysteam import (
    AccessTokenResult,
    AuthenticationError,
    AuthenticationInteractionRequired,
    AuthTokens,
    CredentialStoreError,
    EncryptedFileCredentialStore,
    LoginCredentials,
    ProtocolError,
    RequestTimeout,
    SteamClient,
    SteamResultError,
    guard_code,
    load_mafile,
)
from pysteam.accounts.auth import AuthenticationClient
from pysteam.proto import steammessages_auth_steamclient_pb2 as auth_proto


class MemoryStore:
    def __init__(self, value: LoginCredentials | None = None) -> None:
        self.value = value
        self.saves: list[LoginCredentials] = []

    async def load(self, _account: str) -> LoginCredentials | None:
        return self.value

    async def save(self, _account: str, value: LoginCredentials) -> None:
        self.value = value
        self.saves.append(value)

    async def delete(self, _account: str) -> None:
        self.value = None


class FakeSession:
    def __init__(self, allowed: tuple[int, ...], *, mismatch: bool = False) -> None:
        self.allowed_confirmations = allowed
        self.confirmation_messages = tuple("hint" for _ in allowed)
        self.steam_id = 42
        self.submitted: list[tuple[str, int]] = []
        self.mismatch = mismatch

    async def poll(self) -> AuthTokens | None:
        return None

    async def submit_guard_code(self, code: str, *, code_type: int) -> None:
        self.submitted.append((code, code_type))
        if self.mismatch and len(self.submitted) == 1:
            raise AuthenticationError("Guard", 88)

    async def wait_for_tokens(self, *, timeout: float = 180.0) -> AuthTokens:
        return AuthTokens(42, "user", "new-refresh", "new-access", "new-guard")


class FakeAuth:
    def __init__(self, session: FakeSession | None = None, *, cm_result_code: int | None = None):
        self.session = session
        self.cm_result_code = cm_result_code
        self.began = 0
        self.guard_data = ""
        self.password = ""
        self.renewal = False
        self.events: list[str] = []

    async def generate_access_token_result(
        self, _token: str, *, steam_id: int | None = None, allow_renewal: bool = False
    ) -> AccessTokenResult:
        self.events.append("generate")
        self.renewal = allow_renewal
        return AccessTokenResult("access", "renewed-refresh")

    async def begin_credentials(
        self, _user: str, password: str, *, guard_data: str = "", remember_login: bool = False
    ) -> FakeSession:
        self.began += 1
        self.password = password
        self.guard_data = guard_data
        assert remember_login
        assert self.session is not None
        return self.session

    async def steam_time_offset(self) -> float:
        return 60.0


async def _client(auth: FakeAuth) -> tuple[SteamClient, list[tuple[str, int, str]]]:
    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"])
    logons: list[tuple[str, int, str]] = []

    async def logon(refresh: str, steam_id: int, account_name: str) -> None:
        auth.events.append("logon")
        if auth.cm_result_code is not None and refresh in {"old", "renewed-refresh"}:
            raise SteamResultError("CM logon", auth.cm_result_code)
        logons.append((refresh, steam_id, account_name))

    client._auth = auth  # type: ignore[assignment]
    client._logon_refresh_token = logon  # type: ignore[assignment]
    return client, logons


@pytest.mark.asyncio
async def test_refresh_renewal_and_invalid_token_fallback() -> None:
    store = MemoryStore(LoginCredentials("password", "secret", "old", 42, "trusted"))
    auth = FakeAuth()
    client, logons = await _client(auth)
    try:
        result = await client.login_auto("user", store=store)
        assert result.method == "refresh_token"
        assert result.tokens.refresh_token == "renewed-refresh"
        assert auth.renewal and auth.began == 0
        assert auth.events == ["logon", "generate"]
        assert store.value is not None and store.value.refresh_token == "renewed-refresh"
        assert logons == [("old", 42, "user")]
        assert "renewed-refresh" not in repr(result)
    finally:
        await client.aclose()

    auth = FakeAuth(FakeSession((1,)), cm_result_code=5)
    client, logons = await _client(auth)
    try:
        result = await client.login_auto("user", store=store)
        assert result.method == "credentials"
        assert auth.began == 1 and auth.guard_data == "trusted"
        assert store.value is not None and store.value.guard_data == "new-guard"
        assert logons == [("new-refresh", 42, "user")]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_issued_refresh_token_is_saved_before_cm_logon() -> None:
    store = MemoryStore()
    client, _ = await _client(FakeAuth(FakeSession((1,))))

    async def disconnected(_refresh: str, _steam_id: int, _account_name: str) -> None:
        raise SteamResultError("CM logon", 15)

    client._logon_refresh_token = disconnected  # type: ignore[assignment]
    try:
        with pytest.raises(SteamResultError, match="EResult 15"):
            await client.login_auto(
                "user",
                credentials=LoginCredentials(password="password", shared_secret="secret"),
                store=store,
            )
        assert store.value is not None
        assert store.value.refresh_token == "new-refresh"
        assert store.value.password == "password"
        assert store.value.shared_secret == "secret"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auto_reconnect_recovers_with_saved_credentials() -> None:
    store = MemoryStore(LoginCredentials("password", "secret", "old", 42, "trusted"))
    auth = FakeAuth(FakeSession((1,)))
    client, logons = await _client(auth)
    try:
        await client.login_auto("user", store=store)
        auth.cm_result_code = 5
        await client._restore_session()
        assert auth.began == 1
        assert client.last_session_error is None
        assert logons[-1] == ("new-refresh", 42, "user")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_does_not_retry_credentials() -> None:
    auth = FakeAuth(FakeSession((1,)), cm_result_code=84)
    client, _ = await _client(auth)
    try:
        with pytest.raises(SteamResultError) as captured:
            await client.login_auto(
                "user", credentials=LoginCredentials("password", refresh_token="old", steam_id=42)
            )
        assert captured.value.eresult == 84
        assert auth.began == 0
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_explicit_credentials_override_store_and_session_expiry() -> None:
    class ExpiredSession(FakeSession):
        async def wait_for_tokens(self, *, timeout: float = 180.0) -> AuthTokens:
            raise AuthenticationError("poll authentication", 27)

    store = MemoryStore(LoginCredentials("old-password", refresh_token="old", steam_id=42))
    auth = FakeAuth(ExpiredSession((1,)))
    client, _ = await _client(auth)
    try:
        with pytest.raises(AuthenticationError) as captured:
            await client.login_auto(
                "user",
                credentials=LoginCredentials(password="new-password", refresh_token=""),
                store=store,
            )
        assert captured.value.eresult == 27
        assert auth.password == "new-password"
        assert store.saves == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auth_result_requests_refresh_renewal() -> None:
    class FakeCM:
        async def call_um(self, name, request, _response_type):
            assert name == "Authentication.GenerateAccessTokenForApp#1"
            assert request.renewal_type == auth_proto.k_ETokenRenewalType_Allow
            assert request.steamid == 42
            return auth_proto.CAuthentication_AccessToken_GenerateForApp_Response(
                access_token="access", refresh_token="rotated"
            )

    result = await AuthenticationClient(FakeCM()).generate_access_token_result(
        "refresh", steam_id=42, allow_renewal=True
    )
    assert (result.access_token, result.refresh_token) == ("access", "rotated")
    assert "rotated" not in repr(result)


@pytest.mark.asyncio
async def test_authenticated_account_must_match_requested_account() -> None:
    class OtherAccount(FakeSession):
        async def wait_for_tokens(self, *, timeout: float = 180.0) -> AuthTokens:
            return AuthTokens(42, "other", "refresh", "access", "guard")

    store = MemoryStore()
    client, _ = await _client(FakeAuth(OtherAccount((1,))))
    try:
        with pytest.raises(ProtocolError, match="authenticated account does not match"):
            await client.login_auto("user", credentials=LoginCredentials(password="p"), store=store)
        assert store.saves == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auto_guard_code_uses_steam_time_and_retries_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="pysteam")
    clock = [1_700_000_000.0]

    async def advance(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr("pysteam.client.time.time", lambda: clock[0])
    monkeypatch.setattr("pysteam.client.asyncio.sleep", advance)
    session = FakeSession((3,), mismatch=True)
    auth = FakeAuth(session)
    client, _ = await _client(auth)
    shared_secret = "AQIDBAUGBwgJCgsMDQ4PEA=="
    password = "test-password-please-redact"
    try:
        await client.login_auto(
            "user",
            credentials=LoginCredentials(password=password, shared_secret=shared_secret),
        )
        assert len(session.submitted) == 2
        assert session.submitted[0] == (
            guard_code(shared_secret, timestamp=1_700_000_060),
            3,
        )
        assert session.submitted[1][0] != session.submitted[0][0]
        assert password not in caplog.text
        assert shared_secret not in caplog.text
        assert session.submitted[0][0] not in caplog.text
        assert "new-refresh" not in caplog.text
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_imported_mafile_can_supply_auto_guard_code(tmp_path: Path) -> None:
    secret = base64.b64encode(b"01234567890123456789").decode("ascii")
    path = tmp_path / "user.maFile"
    path.write_text(
        json.dumps({"account_name": "user", "steam_id": 42, "shared_secret": secret}),
        encoding="utf-8",
    )
    imported = load_mafile(path)
    session = FakeSession((3,))
    store = MemoryStore()
    client, _ = await _client(FakeAuth(session))
    try:
        result = await client.login_auto(
            imported.account_name,
            credentials=imported.credentials.with_fallback(LoginCredentials(password="p")),
            store=store,
        )
        assert result.method == "credentials"
        assert session.submitted and session.submitted[0][1] == 3
        assert store.value is not None and store.value.shared_secret == secret
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmation,code", [(2, "email-code"), (4, None)])
async def test_human_challenge_callback(confirmation: int, code: str | None) -> None:
    session = FakeSession((confirmation,))
    client, _ = await _client(FakeAuth(session))
    seen: list[int] = []

    async def answer(challenge):
        seen.append(challenge.confirmation_type)
        assert challenge.associated_message == "hint"
        return code

    try:
        with pytest.raises(AuthenticationInteractionRequired) as captured:
            await client.login_auto("user", credentials=LoginCredentials(password="p"))
        assert captured.value.session is session
        result = await client.login_auto(
            "user", credentials=LoginCredentials(password="p"), on_challenge=answer
        )
        assert result.method == "credentials"
        assert seen == [confirmation]
        assert session.submitted == ([("email-code", 2)] if confirmation == 2 else [])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auto_login_timeout_and_cancellation() -> None:
    class SlowAuth(FakeAuth):
        async def begin_credentials(self, *_args, **_kwargs):
            await asyncio.sleep(60)

    client, _ = await _client(SlowAuth())
    try:
        with pytest.raises(RequestTimeout):
            await client.login_auto(
                "user", credentials=LoginCredentials(password="p"), timeout=0.01
            )
        task = asyncio.create_task(
            client.login_auto("user", credentials=LoginCredentials(password="p"))
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_steam_time_query_midpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/ITwoFactorService/QueryTime/v1/")
        return httpx.Response(200, json={"response": {"server_time": 130}})

    monkeypatch.setattr("pysteam.accounts.auth.time.time", lambda: 100.0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SteamClient(http=http)
        assert await AuthenticationClient(client).steam_time_offset() == 30.0
        await client.aclose()


@pytest.mark.asyncio
async def test_encrypted_store_roundtrip_concurrency_and_errors(tmp_path: Path) -> None:
    path = tmp_path / "private" / "accounts.bin"
    store = EncryptedFileCredentialStore(path, "test-passphrase")
    await asyncio.gather(
        store.save("one", LoginCredentials("password-one", "secret-one")),
        store.save("two", LoginCredentials(refresh_token="token-two", steam_id=42)),
    )
    assert (await store.load("one")).password == "password-one"  # type: ignore[union-attr]
    assert (await store.load("two")).refresh_token == "token-two"  # type: ignore[union-attr]
    assert b"password-one" not in path.read_bytes()
    assert "secret-one" not in repr(await store.load("one"))
    with pytest.raises(CredentialStoreError, match="wrong passphrase"):
        await EncryptedFileCredentialStore(path, "wrong").load("one")
    await store.delete("one")
    assert await store.load("one") is None
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(CredentialStoreError, match="wrong passphrase"):
        await store.load("two")


@pytest.mark.asyncio
async def test_encrypted_store_rejects_plaintext_symlink_and_loose_permissions(
    tmp_path: Path,
) -> None:
    path = tmp_path / "accounts.bin"
    store = EncryptedFileCredentialStore(path, "passphrase")
    path.write_bytes(b'{"password":"plaintext"}')
    with pytest.raises(CredentialStoreError, match="unsupported"):
        await store.load("one")
    path.unlink()
    await store.save("one", LoginCredentials(password="synthetic"))
    if os.name != "nt":
        path.chmod(0o644)
        with pytest.raises(CredentialStoreError, match="permissions"):
            await store.load("one")
        path.chmod(0o600)
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(CredentialStoreError):
        await EncryptedFileCredentialStore(link, "passphrase").load("one")
