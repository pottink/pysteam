"""Public errors. Exception text never includes credentials or raw packets."""

from typing import Any


class SteamError(Exception):
    """Base error for Steam operations."""


class ProtocolError(SteamError):
    """A packet or response does not satisfy the expected protocol."""


class TransportError(SteamError):
    """A connection failed or ended unexpectedly."""


class RequestTimeout(SteamError):
    """A correlated request did not receive a reply before its deadline."""


class SteamResultError(SteamError):
    """Steam returned a non-OK EResult."""

    def __init__(
        self, operation: str, eresult: int, *, response_body: dict[str, Any] | None = None
    ) -> None:
        self.operation = operation
        self.eresult = eresult
        self.response_body = response_body
        super().__init__(f"{operation} failed with EResult {eresult}")


class AuthenticationError(SteamResultError):
    """An authentication operation returned a non-OK EResult."""


class CDNError(SteamError):
    """A CDN manifest or content request failed."""


class CDNHTTPError(CDNError):
    """A CDN server returned a non-success HTTP status."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"CDN returned HTTP {status_code}")


class WebAPIError(TransportError):
    """Web API HTTP failure with a parsed response body when available."""

    def __init__(
        self, operation: str, status_code: int, response_body: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"{operation} returned HTTP {status_code}")
