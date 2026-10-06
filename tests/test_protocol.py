import gzip
import json
import struct
from pathlib import Path

import pytest

from pysteam import ProtocolError, SteamID, confirmation_key, guard_code
from pysteam.proto.steammessages_base_pb2 import CMsgMulti, CMsgProtoBufHeader
from pysteam.proto.steammessages_clientserver_login_pb2 import CMsgClientHello
from pysteam.protocol import Packet, decode_packet, encode_packet, unpack_multi


def test_packet_round_trip_and_invalid_lengths() -> None:
    original = encode_packet(42, b"payload", CMsgProtoBufHeader(jobid_source=123))
    packet = decode_packet(original)
    assert packet.emsg == 42
    assert packet.header.jobid_source == 123
    assert packet.body == b"payload"
    with pytest.raises(ProtocolError):
        decode_packet(original[:5])
    with pytest.raises(ProtocolError):
        decode_packet(struct.pack("<II", 42, 0))
    with pytest.raises(ProtocolError):
        decode_packet(original[:4] + struct.pack("<I", 999999) + original[8:])


def test_steamkit_client_hello_wire_fixture() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "steamkit_client_hello.json").read_text(
            encoding="utf-8"
        )
    )
    packet = encode_packet(
        fixture["emsg"], CMsgClientHello(protocol_version=fixture["protocol_version"])
    )
    assert packet.hex() == fixture["packet_hex"]
    decoded = decode_packet(bytes.fromhex(fixture["packet_hex"]))
    body = CMsgClientHello()
    body.ParseFromString(decoded.body)
    assert body.protocol_version == fixture["protocol_version"]


def test_multi_gzip_and_malformed_entry() -> None:
    inner = encode_packet(42, b"hello")
    framed = struct.pack("<I", len(inner)) + inner
    body = CMsgMulti(size_unzipped=len(framed), message_body=gzip.compress(framed))
    assert (
        unpack_multi(Packet(1, CMsgProtoBufHeader(), body.SerializeToString()))[0].body == b"hello"
    )
    bad = CMsgMulti(message_body=struct.pack("<I", len(inner) + 1) + inner)
    with pytest.raises(ProtocolError):
        unpack_multi(Packet(1, CMsgProtoBufHeader(), bad.SerializeToString()))


def test_steamid_and_guard_regressions() -> None:
    steam_id = SteamID.parse("STEAM_1:1:1")
    assert steam_id == SteamID.from_account_id(3)
    assert SteamID.parse(str(steam_id)) == steam_id
    assert SteamID.parse("[U:1:3]") == steam_id
    with pytest.raises(ValueError):
        SteamID.parse("STEAM_1:1:999999999999")
    code = guard_code("AQIDBAUGBwgJCgsMDQ4PEA==", timestamp=1_700_000_000)
    assert len(code) == 5
    assert code == guard_code("AQIDBAUGBwgJCgsMDQ4PEA==", timestamp=1_700_000_005)
    assert len(confirmation_key("AQIDBAUGBwgJCgsMDQ4PEA==", "conf", timestamp=100)) == 28
    with pytest.raises(ValueError):
        guard_code("not base64!", timestamp=0)
