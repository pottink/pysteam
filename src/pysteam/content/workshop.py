"""PublishedFile unified messages for Workshop discovery and preservation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pysteam.errors import ProtocolError, SteamResultError
from pysteam.proto import steammessages_publishedfile_steamclient_pb2 as published

if TYPE_CHECKING:
    from pysteam.client import SteamClient


@dataclass(frozen=True, slots=True)
class WorkshopItem:
    published_file_id: int
    app_id: int
    manifest_id: int
    title: str
    file_url: str = field(repr=False)
    file_size: int
    raw: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class WorkshopQuery:
    total: int
    items: tuple[WorkshopItem, ...]
    next_cursor: str


def _item(detail: published.PublishedFileDetails) -> WorkshopItem:
    if detail.result != 1:
        raise SteamResultError("Workshop item", detail.result)
    if not detail.publishedfileid or not detail.consumer_appid:
        raise ProtocolError("Workshop item has no ID or app")
    return WorkshopItem(
        detail.publishedfileid,
        detail.consumer_appid,
        detail.hcontent_file,
        detail.title,
        detail.file_url,
        detail.file_size,
        detail.SerializeToString(),
    )


class WorkshopClient:
    def __init__(self, client: SteamClient) -> None:
        self._client = client

    async def get_details(self, published_file_id: int) -> WorkshopItem:
        if published_file_id <= 0:
            raise ValueError("published file ID must be positive")
        response = await self._client.call_um(
            "PublishedFile.GetDetails#1",
            published.CPublishedFile_GetDetails_Request(publishedfileids=[published_file_id]),
            published.CPublishedFile_GetDetails_Response,
        )
        if len(response.publishedfiledetails) != 1:
            raise ProtocolError("Workshop details response has no single item")
        item = _item(response.publishedfiledetails[0])
        if item.published_file_id != published_file_id:
            raise ProtocolError("Workshop details response ID mismatch")
        return item

    async def query(
        self,
        app_id: int,
        *,
        search: str = "",
        page: int = 1,
        per_page: int = 20,
        query_type: int = 0,
    ) -> WorkshopQuery:
        if app_id <= 0 or not 1 <= page <= 10000 or not 1 <= per_page <= 100:
            raise ValueError("invalid Workshop query parameters")
        request = published.CPublishedFile_QueryFiles_Request(
            appid=app_id,
            page=page,
            numperpage=per_page,
            query_type=query_type,
            search_text=search,
            return_details=True,
        )
        response = await self._client.call_um(
            "PublishedFile.QueryFiles#1",
            request,
            published.CPublishedFile_QueryFiles_Response,
        )
        items = tuple(_item(detail) for detail in response.publishedfiledetails)
        return WorkshopQuery(response.total, items, response.next_cursor)
