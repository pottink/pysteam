"""Bounded Steam CM protobuf packet framing."""

from __future__ import annotations

import gzip
import struct
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

from google.protobuf.message import DecodeError

from pysteam.errors import ProtocolError
from pysteam.proto.steammessages_base_pb2 import CMsgMulti, CMsgProtoBufHeader

if TYPE_CHECKING:
    from google.protobuf.message import Message

PROTO_MASK = 0x80000000
MAX_PACKET_SIZE = 16 * 1024 * 1024
MAX_MULTI_SIZE = 64 * 1024 * 1024
MAX_MULTI_MESSAGES = 4096
INVALID_JOB_ID = 0xFFFFFFFFFFFFFFFF


@dataclass(frozen=True, slots=True)
class Packet:
    emsg: int
    header: CMsgProtoBufHeader
    body: bytes


def encode_packet(
    emsg: int, body: Message | bytes, header: CMsgProtoBufHeader | None = None
) -> bytes:
    """Encode a protobuf Steam CM packet; preserve caller supplied header fields."""
    if not 0 <= emsg < PROTO_MASK:
        raise ValueError("emsg out of range")
    encoded_body = body if isinstance(body, bytes) else body.SerializeToString()
    encoded_header = (header or CMsgProtoBufHeader()).SerializeToString()
    packet = (
        struct.pack("<II", emsg | PROTO_MASK, len(encoded_header)) + encoded_header + encoded_body
    )
    if len(packet) > MAX_PACKET_SIZE:
        raise ProtocolError("outbound packet exceeds size limit")
    return packet


def decode_packet(data: bytes) -> Packet:
    """Decode exactly one protobuf packet with bounded header and body sizes."""
    if len(data) < 8 or len(data) > MAX_PACKET_SIZE:
        raise ProtocolError("invalid packet size")
    tagged_emsg, header_size = struct.unpack_from("<II", data)
    if not tagged_emsg & PROTO_MASK:
        raise ProtocolError(f"non-protobuf CM packet EMsg {tagged_emsg} is unsupported")
    if header_size > len(data) - 8:
        raise ProtocolError("header length exceeds packet")
    header = CMsgProtoBufHeader()
    try:
        header.ParseFromString(data[8 : 8 + header_size])
    except DecodeError as exc:
        raise ProtocolError("invalid protobuf header") from exc
    return Packet(tagged_emsg & ~PROTO_MASK, header, data[8 + header_size :])


def peek_packet_type(data: bytes) -> tuple[int, bool]:
    """Read the bounded EMsg prefix without decoding an unsupported legacy body."""
    if len(data) < 4 or len(data) > MAX_PACKET_SIZE:
        raise ProtocolError("invalid packet size")
    tagged_emsg = struct.unpack_from("<I", data)[0]
    return tagged_emsg & ~PROTO_MASK, bool(tagged_emsg & PROTO_MASK)


def unpack_multi_raw(packet: Packet) -> list[bytes]:
    """Unpack bounded EMsg.Multi entries, preserving legacy packet framing."""
    message = CMsgMulti()
    try:
        message.ParseFromString(packet.body)
    except DecodeError as exc:
        raise ProtocolError("invalid multi-message body") from exc
    body = message.message_body
    if message.size_unzipped:
        try:
            with gzip.GzipFile(fileobj=BytesIO(body)) as stream:
                body = stream.read(MAX_MULTI_SIZE + 1)
        except (OSError, EOFError) as exc:
            raise ProtocolError("invalid compressed multi-message") from exc
        if len(body) != message.size_unzipped:
            raise ProtocolError("multi-message uncompressed size mismatch")
    if len(body) > MAX_MULTI_SIZE:
        raise ProtocolError("multi-message exceeds size limit")
    packets: list[bytes] = []
    offset = 0
    while offset < len(body):
        if len(packets) == MAX_MULTI_MESSAGES or len(body) - offset < 4:
            raise ProtocolError("invalid multi-message count or trailer")
        size = struct.unpack_from("<I", body, offset)[0]
        offset += 4
        if size == 0 or size > len(body) - offset:
            raise ProtocolError("invalid multi-message entry length")
        packets.append(body[offset : offset + size])
        offset += size
    return packets


def unpack_multi(packet: Packet) -> list[Packet]:
    """Unpack EMsg.Multi entries that all use protobuf framing."""
    return [decode_packet(raw) for raw in unpack_multi_raw(packet)]
