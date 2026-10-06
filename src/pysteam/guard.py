"""Pure Steam Guard code and confirmation-key helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import struct
import time

_ALPHABET = "23456789BCDFGHJKMNPQRTVWXY"


def _secret(encoded: str) -> bytes:
    try:
        result = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Steam Guard secret must be valid base64") from exc
    if not result:
        raise ValueError("Steam Guard secret is empty")
    return result


def guard_code(shared_secret: str, *, timestamp: int | None = None) -> str:
    """Calculate a five-character Steam Guard code for a Unix timestamp."""
    when = int(time.time()) if timestamp is None else timestamp
    if when < 0:
        raise ValueError("timestamp must be nonnegative")
    digest = hmac.new(_secret(shared_secret), struct.pack(">Q", when // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0xF
    number = struct.unpack_from(">I", digest, offset)[0] & 0x7FFFFFFF
    characters: list[str] = []
    for _ in range(5):
        number, index = divmod(number, len(_ALPHABET))
        characters.append(_ALPHABET[index])
    return "".join(characters)


def confirmation_key(identity_secret: str, tag: str, *, timestamp: int | None = None) -> str:
    """Calculate a base64 confirmation key. The tag is limited to 32 UTF-8 bytes."""
    when = int(time.time()) if timestamp is None else timestamp
    if when < 0:
        raise ValueError("timestamp must be nonnegative")
    payload = struct.pack(">Q", when) + tag.encode("utf-8")[:32]
    return base64.b64encode(
        hmac.new(_secret(identity_secret), payload, hashlib.sha1).digest()
    ).decode("ascii")
