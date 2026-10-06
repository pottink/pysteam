import pytest

from pysteam import ProtocolError, extract_manifest_ids, parse_app_vdf


def test_modern_and_legacy_manifest_references() -> None:
    data = b""""appinfo"
    {
        "appid" "570"
        "depots" {
            "570" { "manifests" { "public" { "gid" "6409137169988641422" } } }
            "571" { "manifests" { "public" "123456789" } }
            "branches" { "public" { "buildid" "99" } }
            "572" { "depotfromapp" "228980" }
        }
    }\x00"""
    app_info = parse_app_vdf(data)
    assert app_info["appid"] == "570"
    assert extract_manifest_ids(app_info) == {570: 6409137169988641422, 571: 123456789}
    assert extract_manifest_ids(app_info, branch="beta") == {}


def test_vdf_escapes_comments_and_malformed_input() -> None:
    parsed = parse_app_vdf(b'"appinfo" { // comment\n "appid" "42" "name" "a\\"b" }')
    assert parsed == {"appid": "42", "name": 'a"b'}
    for data in (b"", b'"appinfo" { "appid"', b'"appinfo" { "appid" "1" } extra'):
        with pytest.raises(ProtocolError):
            parse_app_vdf(data)
    with pytest.raises(ProtocolError):
        extract_manifest_ids({"depots": {"570": {"manifests": {"public": {"gid": "no"}}}}})
    with pytest.raises(ProtocolError):
        parse_app_vdf(b'"appinfo" {' * 65 + b'"x" "y"' + b"}" * 65)
