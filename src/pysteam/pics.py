"""Bounded PICS app-info text and manifest reference parsing."""

from __future__ import annotations

from dataclasses import dataclass, field

from pysteam.errors import ProtocolError

type KVValue = str | dict[str, KVValue]
_MAX_VDF_BYTES = 16 * 1024 * 1024
_MAX_TOKENS = 250_000
_MAX_DEPTH = 64


@dataclass(frozen=True, slots=True)
class PICSAccessTokens:
    apps: dict[int, int] = field(repr=False)
    packages: dict[int, int] = field(repr=False)
    denied_app_ids: frozenset[int]
    denied_package_ids: frozenset[int]


def _tokens(data: bytes) -> list[str]:
    if not data or len(data) > _MAX_VDF_BYTES:
        raise ProtocolError("PICS app-info size is invalid")
    source = data.decode("utf-8", "replace")
    result: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace() or char == "\x00":
            index += 1
            continue
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end + 1
            continue
        if char in "{}":
            result.append(char)
            index += 1
        elif char == '"':
            index += 1
            value: list[str] = []
            while index < len(source):
                char = source[index]
                if char == '"':
                    index += 1
                    break
                if char == "\\" and index + 1 < len(source):
                    next_char = source[index + 1]
                    if next_char in ('"', "\\"):
                        value.append(next_char)
                        index += 2
                        continue
                value.append(char)
                index += 1
            else:
                raise ProtocolError("PICS app-info has an unterminated string")
            result.append("".join(value))
        else:
            start = index
            while (
                index < len(source)
                and not source[index].isspace()
                and source[index] not in '{}"\x00'
            ):
                index += 1
            if start == index:
                raise ProtocolError("PICS app-info contains invalid syntax")
            result.append(source[start:index])
        if len(result) > _MAX_TOKENS:
            raise ProtocolError("PICS app-info has too many tokens")
    return result


def parse_vdf_document(data: bytes) -> dict[str, dict[str, KVValue]]:
    """Decode bounded text VDF, including signed multi-root update files."""
    tokens = _tokens(data)
    position = 0

    def read_object(depth: int) -> dict[str, KVValue]:
        nonlocal position
        if depth > _MAX_DEPTH:
            raise ProtocolError("PICS app-info nesting exceeds limit")
        obj: dict[str, KVValue] = {}
        while position < len(tokens):
            key = tokens[position]
            position += 1
            if key == "}":
                return obj
            if key == "{" or position >= len(tokens):
                raise ProtocolError("PICS app-info has malformed keys")
            value = tokens[position]
            position += 1
            if value == "{":
                obj[key] = read_object(depth + 1)
            elif value == "}":
                raise ProtocolError("PICS app-info has a missing value")
            else:
                obj[key] = value
        raise ProtocolError("PICS app-info has an unclosed object")

    document: dict[str, dict[str, KVValue]] = {}
    while position < len(tokens):
        if (
            position + 1 >= len(tokens)
            or tokens[position] in ("{", "}")
            or tokens[position + 1] != "{"
            or tokens[position] in document
        ):
            raise ProtocolError("VDF has an invalid root object")
        root = tokens[position]
        position += 2
        document[root] = read_object(1)
    if not document:
        raise ProtocolError("VDF has no root object")
    return document


def parse_vdf(data: bytes) -> tuple[str, dict[str, KVValue]]:
    """Decode one bounded VDF root, rejecting extra roots."""
    document = parse_vdf_document(data)
    if len(document) != 1:
        raise ProtocolError("VDF has multiple root objects")
    return next(iter(document.items()))


def parse_app_vdf(data: bytes) -> dict[str, KVValue]:
    """Decode a PICS text VDF appinfo buffer into bounded nested key/value data."""
    root, result = parse_vdf(data)
    if root.casefold() != "appinfo":
        raise ProtocolError("PICS app-info has no appinfo root")
    return result


def extract_manifest_ids(app_info: dict[str, KVValue], *, branch: str = "public") -> dict[int, int]:
    """Map depot IDs to manifest IDs from either modern gid objects or old scalar values."""
    if not branch:
        raise ValueError("branch must not be empty")
    depots = app_info.get("depots")
    if not isinstance(depots, dict):
        raise ProtocolError("PICS app-info has no depots object")
    result: dict[int, int] = {}
    for depot_text, depot in depots.items():
        if not depot_text.isdecimal() or not isinstance(depot, dict):
            continue
        depot_id = int(depot_text)
        if depot_id > 0xFFFFFFFF:
            raise ProtocolError("PICS depot ID is out of range")
        manifests = depot.get("manifests")
        if not isinstance(manifests, dict) or branch not in manifests:
            continue
        manifest = manifests[branch]
        gid = manifest.get("gid") if isinstance(manifest, dict) else manifest
        if not isinstance(gid, str) or not gid.isdecimal():
            raise ProtocolError("PICS manifest ID is invalid")
        manifest_id = int(gid)
        if not 0 < manifest_id <= 0xFFFFFFFFFFFFFFFF:
            raise ProtocolError("PICS manifest ID is out of range")
        result[depot_id] = manifest_id
    return result
