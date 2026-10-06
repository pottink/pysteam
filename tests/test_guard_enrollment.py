"""Offline Steam Guard enrollment and backup behavior."""

import base64
import os
import time
from pathlib import Path

import httpx
import pytest

from pysteam import (
    AuthTokens,
    EnrollmentError,
    GuardEnrollmentClient,
    LoginCredentials,
    MaFileError,
    PendingGuardEnrollment,
    ProtocolError,
    SteamClient,
    SteamResultError,
    load_mafile,
)
from pysteam.guard_enrollment import _save_backup, _TwoFactorService
from pysteam.proto import steammessages_twofactor_steamclient_pb2 as twofactor

STEAM_ID = 76561197960265729
SECRET = b"01234567890123456789"
TOKENS = AuthTokens(STEAM_ID, "example", "refresh-secret", "access-secret")


def _added() -> twofactor.CTwoFactor_AddAuthenticator_Response:
    return twofactor.CTwoFactor_AddAuthenticator_Response(
        shared_secret=SECRET,
        serial_number=42,
        revocation_code="R12345",
        uri="otpauth://totp/Steam:example?secret=test",
        server_time=1_700_000_000,
        account_name="example",
        token_gid="gid-1",
        identity_secret=b"abcdefghijklmnopqrst",
        secret_1=b"other-secret-123456",
        phone_number_hint="42",
        confirm_type=1,
    )


def test_overlay_fields_and_encrypted_backup_round_trip(tmp_path: Path) -> None:
    assert (
        twofactor.CTwoFactor_AddAuthenticator_Request.DESCRIPTOR.fields_by_name[
            "sms_phone_id"
        ].number
        == 6
    )
    assert (
        twofactor.CTwoFactor_FinalizeAddAuthenticator_Response.DESCRIPTOR.fields_by_name[
            "want_more"
        ].number
        == 2
    )
    output = tmp_path / "new-authenticator"
    path = _save_backup(
        output,
        steam_id=STEAM_ID,
        account_name="example",
        device_id="android:test-id",
        response=_added(),
        passphrase="backup-passphrase",
    )
    assert path.name == f"{STEAM_ID}.maFile"
    assert not path.read_bytes().startswith(b"{")
    imported = load_mafile(path, passphrase="backup-passphrase")
    assert imported.credentials == LoginCredentials(
        shared_secret=base64.b64encode(SECRET).decode(), steam_id=STEAM_ID
    )
    with pytest.raises(MaFileError):
        load_mafile(path, passphrase="wrong")
    with pytest.raises(EnrollmentError, match=r"must not already exist|must be new"):
        _save_backup(
            output,
            steam_id=STEAM_ID,
            account_name="example",
            device_id="android:test-id",
            response=_added(),
            passphrase="backup-passphrase",
        )
    if os.name != "nt":
        assert output.stat().st_mode & 0o077 == 0
        assert path.stat().st_mode & 0o077 == 0
        assert (output / "manifest.json").stat().st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_twofactor_transport_protobuf_and_result_codes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["access_token"] == "access-secret"
        assert request.method == "POST"
        assert b"input_protobuf_encoded=" in request.content
        encoded = request.content.split(b"input_protobuf_encoded=", 1)[1]
        decoded = twofactor.CTwoFactor_Status_Request.FromString(base64.b64decode(encoded))
        assert decoded.steamid == STEAM_ID
        return httpx.Response(
            200,
            content=twofactor.CTwoFactor_Status_Response(state=1).SerializeToString(),
            headers={"x-eresult": "1"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SteamClient(http=http)
        result = await _TwoFactorService(client).call(
            "QueryStatus",
            twofactor.CTwoFactor_Status_Request(steamid=STEAM_ID),
            twofactor.CTwoFactor_Status_Response,
            "access-secret",
        )
        assert result.state == 1

    async def denied(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"x-eresult": "84"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(denied)) as http:
        with pytest.raises(SteamResultError) as captured:
            await _TwoFactorService(SteamClient(http=http)).call(
                "QueryStatus",
                twofactor.CTwoFactor_Status_Request(steamid=STEAM_ID),
                twofactor.CTwoFactor_Status_Response,
                "access-secret",
            )
        assert captured.value.eresult == 84
        assert "access-secret" not in str(captured.value)

    async def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\xff", headers={"x-eresult": "1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as http:
        with pytest.raises(ProtocolError, match="invalid protobuf"):
            await _TwoFactorService(SteamClient(http=http)).call(
                "QueryStatus",
                twofactor.CTwoFactor_Status_Request(steamid=STEAM_ID),
                twofactor.CTwoFactor_Status_Response,
                "access-secret",
            )


class _FakeSession:
    allowed_confirmations = (1,)
    confirmation_messages: tuple[str, ...] = ()

    async def poll(self) -> AuthTokens:
        return TOKENS


class _FakeAuth:
    async def begin_credentials(self, _account: str, _password: str, **kwargs: object):
        assert kwargs["platform_kind"] == "mobile"
        return _FakeSession()

    async def steam_time_offset(self) -> float:
        return 1_700_000_000 - time.time()


@pytest.mark.asyncio
async def test_mobile_login_handles_email_code() -> None:
    class EmailSession:
        allowed_confirmations = (2,)
        confirmation_messages = ("email hint",)

        def __init__(self) -> None:
            self.submitted: list[tuple[str, int]] = []

        async def poll(self) -> None:
            return None

        async def submit_guard_code(self, code: str, *, code_type: int) -> None:
            self.submitted.append((code, code_type))

        async def wait_for_tokens(self) -> AuthTokens:
            return TOKENS

    class EmailAuth:
        def __init__(self) -> None:
            self.session = EmailSession()

        async def begin_credentials(self, _account: str, _password: str, **_kwargs: object):
            return self.session

    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"])
    auth = EmailAuth()
    client._auth = auth  # type: ignore[assignment]

    async def answer(challenge):
        assert challenge.confirmation_type == 2
        assert challenge.associated_message == "email hint"
        return "123456"

    try:
        assert (
            await GuardEnrollmentClient(client)._login_mobile("example", "password", answer, 10.0)
            == TOKENS
        )
        assert auth.session.submitted == [("123456", 2)]
    finally:
        await client.aclose()


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.active = False
        self.want_more = False

    async def call(self, method: str, request: object, _response_type: object, _token: str):
        self.calls.append(method)
        if method == "QueryStatus":
            return twofactor.CTwoFactor_Status_Response(
                state=1 if self.active else 0, token_gid="gid-1" if self.active else ""
            )
        if method == "AddAuthenticator":
            assert isinstance(request, twofactor.CTwoFactor_AddAuthenticator_Request)
            assert request.version == 2 and request.sms_phone_id == "1"
            return _added()
        if method == "FinalizeAddAuthenticator":
            assert isinstance(request, twofactor.CTwoFactor_FinalizeAddAuthenticator_Request)
            assert request.activation_code == "activation-secret"
            if self.want_more:
                self.want_more = False
                return twofactor.CTwoFactor_FinalizeAddAuthenticator_Response(
                    want_more=True, server_time=1_700_000_030
                )
            self.active = True
            return twofactor.CTwoFactor_FinalizeAddAuthenticator_Response(success=True)
        raise AssertionError(method)


@pytest.mark.asyncio
async def test_login_begin_finalize_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeService()
    monkeypatch.setattr("pysteam.guard_enrollment._TwoFactorService", lambda _client: fake)
    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"])
    client._auth = _FakeAuth()  # type: ignore[assignment]
    enrollment = GuardEnrollmentClient(client)
    output = tmp_path / "new-authenticator"
    try:
        pending = await enrollment.login_and_begin(
            "example", "password", directory=output, passphrase="backup-passphrase"
        )
        assert isinstance(pending, PendingGuardEnrollment)
        assert pending.mafile_path.is_file()
        assert not pending.finalized
        assert "R12345" not in repr(pending)
        assert "access-secret" not in repr(pending)
        fake.want_more = True
        assert await pending.finalize("activation-secret") == pending.mafile_path
        assert pending.finalized
        assert fake.calls == [
            "QueryStatus",
            "AddAuthenticator",
            "FinalizeAddAuthenticator",
            "FinalizeAddAuthenticator",
            "QueryStatus",
        ]
        with pytest.raises(EnrollmentError, match="already active"):
            await enrollment.login_and_resume(
                "example",
                "password",
                mafile_path=pending.mafile_path,
                passphrase="backup-passphrase",
            )
        fake.active = False
        resumed = await enrollment.login_and_resume(
            "example",
            "password",
            mafile_path=pending.mafile_path,
            passphrase="backup-passphrase",
        )
        assert resumed.recovery_code is None
        assert await resumed.finalize("activation-secret") == pending.mafile_path
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_existing_authenticator_blocks_add(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeService()
    fake.active = True
    monkeypatch.setattr("pysteam.guard_enrollment._TwoFactorService", lambda _client: fake)
    client = SteamClient(cm_endpoints=["wss://example.invalid/cmsocket/"])
    client._auth = _FakeAuth()  # type: ignore[assignment]
    try:
        with pytest.raises(EnrollmentError, match="already present"):
            await GuardEnrollmentClient(client).login_and_begin(
                "example", "password", directory=tmp_path / "unused", passphrase="passphrase"
            )
        assert fake.calls == ["QueryStatus"]
    finally:
        await client.aclose()
