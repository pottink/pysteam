"""Async Steam Web API transport with bounded, typed JSON decoding."""

from __future__ import annotations

import re
from typing import Any, TypeVar

import httpx
import msgspec

from pysteam.errors import ProtocolError, SteamResultError, TransportError, WebAPIError

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_T = TypeVar("_T")


class WebAPIClient:
    def __init__(
        self,
        *,
        key: str | None = None,
        base_url: str = "https://api.steampowered.com",
        timeout: float = 20.0,
        max_response_bytes: int = 16 * 1024 * 1024,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout <= 0 or max_response_bytes <= 0:
            raise ValueError("timeout and response size limit must be positive")
        self._key = key
        self._base_url = base_url.rstrip("/")
        self._max_response_bytes = max_response_bytes
        self._timeout = timeout
        self._owned_http = http is None
        self._http = http or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def __aenter__(self) -> WebAPIClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owned_http:
            await self._http.aclose()

    async def call(
        self,
        interface: str,
        method: str,
        *,
        version: int = 1,
        params: dict[str, str | int | bool] | None = None,
        http_method: str = "GET",
    ) -> dict[str, Any]:
        if not _NAME.fullmatch(interface) or not _NAME.fullmatch(method) or not 1 <= version <= 999:
            raise ValueError("invalid Web API interface, method, or version")
        if http_method not in {"GET", "POST"}:
            raise ValueError("HTTP method must be GET or POST")
        arguments: dict[str, str | int | bool] = dict(params or {})
        if self._key is not None:
            arguments["key"] = self._key
        path = f"{self._base_url}/{interface}/{method}/v{version}/"
        try:
            async with self._http.stream(
                http_method,
                path,
                params=arguments if http_method == "GET" else None,
                data=arguments if http_method == "POST" else None,
                timeout=self._timeout,
            ) as response:
                content = bytearray()
                async for part in response.aiter_bytes():
                    if len(content) + len(part) > self._max_response_bytes:
                        raise ProtocolError("Web API response exceeds size limit")
                    content.extend(part)
                status_code = response.status_code
        except httpx.HTTPError:
            raise TransportError(f"Web API {interface}.{method} request failed") from None
        try:
            decoded = msgspec.json.decode(content)
        except msgspec.DecodeError as exc:
            if status_code >= 300:
                raise WebAPIError(f"Web API {interface}.{method}", status_code) from None
            raise ProtocolError(f"Web API {interface}.{method} returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise ProtocolError("Web API response root is not an object")
        result = decoded.get("response", decoded)
        if not isinstance(result, dict):
            raise ProtocolError("Web API response is not an object")
        eresult = result.get("eresult")
        if isinstance(eresult, int) and eresult != 1:
            raise SteamResultError(f"Web API {interface}.{method}", eresult, response_body=result)
        if status_code >= 300:
            raise WebAPIError(f"Web API {interface}.{method}", status_code, result)
        return result

    async def call_typed(
        self,
        interface: str,
        method: str,
        response_type: type[_T],
        *,
        version: int = 1,
        params: dict[str, str | int | bool] | None = None,
        http_method: str = "GET",
    ) -> _T:
        """Decode the Web API response into a caller supplied msgspec Struct type."""
        result = await self.call(
            interface, method, version=version, params=params, http_method=http_method
        )
        try:
            return msgspec.convert(result, type=response_type)
        except msgspec.ValidationError as exc:
            raise ProtocolError(f"Web API {interface}.{method} response shape is invalid") from exc
