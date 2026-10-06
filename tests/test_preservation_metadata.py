"""Offline fixtures for Workshop and Steam client package metadata."""

from __future__ import annotations

import pytest

from pysteam import CDNError, WorkshopClient
from pysteam.clientpackages import parse_client_manifest
from pysteam.proto import steammessages_publishedfile_steamclient_pb2 as published


def test_client_manifest_package_validation() -> None:
    sha = "a" * 64
    raw = (
        f'"win32" {{ "version" "123" "package" {{ "file" "client.zip" '
        f'"sha2" "{sha}" }} }} "kvsign2" {{ "win32" "signature" }}'
    ).encode()
    version, packages = parse_client_manifest(raw, "steam_client_win32")
    assert version == "123" and packages[0].filename == "client.zip"
    with pytest.raises(CDNError, match="filename or checksum"):
        parse_client_manifest(raw.replace(b"client.zip", b"../evil.zip"), "steam_client_win32")


@pytest.mark.asyncio
async def test_workshop_query_and_details_identity() -> None:
    class FakeSteam:
        async def call_um(self, name: str, _request: object, _response: object) -> object:
            detail = published.PublishedFileDetails(
                result=1,
                publishedfileid=42,
                consumer_appid=220,
                hcontent_file=123456,
                title="example",
            )
            if name == "PublishedFile.QueryFiles#1":
                return published.CPublishedFile_QueryFiles_Response(
                    total=1, publishedfiledetails=[detail]
                )
            return published.CPublishedFile_GetDetails_Response(publishedfiledetails=[detail])

    workshop = WorkshopClient(FakeSteam())  # type: ignore[arg-type]
    assert (await workshop.query(220)).items[0].manifest_id == 123456
    assert (await workshop.get_details(42)).title == "example"
    with pytest.raises(Exception, match="mismatch"):
        await workshop.get_details(43)
