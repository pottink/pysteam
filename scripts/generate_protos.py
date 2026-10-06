"""Compile the pinned SteamTracking proto subset into pysteam.proto.

Only schemas needed for the first-release features and their transitive imports
are compiled. Generated imports are package-relative so the wheel needs no
global modules. Run ``--check`` in CI to detect stale generated files.
"""

from __future__ import annotations

import filecmp
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import grpc_tools
import typer
from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "vendor" / "steam-protobufs" / "steam"
DESTINATION = ROOT / "src" / "pysteam" / "proto"
ROOT_SCHEMAS = (
    "enums.proto",
    "enums_clientserver.proto",
    "enums_productinfo.proto",
    "steammessages_base.proto",
    "steammessages_clientserver_login.proto",
    "steammessages_clientserver_appinfo.proto",
    "steammessages_clientserver_2.proto",
    "steammessages_auth.steamclient.proto",
    "steammessages_twofactor.steamclient.proto",
    "steammessages_contentsystem.steamclient.proto",
    "steammessages_publishedfile.steamclient.proto",
    "content_manifest.proto",
)
IMPORT = re.compile(r'^import(?:\s+public|\s+weak)?\s+"([^"]+)";', re.MULTILINE)
GENERATED_IMPORT = re.compile(r"^import ([A-Za-z0-9_]+_pb2) as ", re.MULTILINE)


def _twofactor_compat_fields(source: str) -> str:
    """Restore two live Web API fields absent from SteamTracking's schema.

    steamguard-cli's public service_twofactor.proto documents field 6 of the
    add request and field 2 of the finalize response. Keep this small overlay
    explicit so a future upstream schema change cannot silently alter the wire.
    """
    fields = (
        (
            "\toptional string device_identifier = 5;\n",
            "\toptional string device_identifier = 5;\n\toptional string sms_phone_id = 6;\n",
            "optional string sms_phone_id = 6;",
        ),
        (
            "\toptional bool success = 1;\n\toptional uint64 server_time = 3;",
            "\toptional bool success = 1;\n\toptional bool want_more = 2;\n"
            "\toptional uint64 server_time = 3;",
            "optional bool want_more = 2;",
        ),
    )
    for old, new, present in fields:
        if present not in source:
            if old not in source:
                raise RuntimeError("two-factor schema overlay no longer matches upstream")
            source = source.replace(old, new, 1)
    return source


def dependencies(name: str, found: set[str]) -> None:
    if name in found or name.startswith("google/"):
        return
    source = SCHEMAS / name
    if not source.is_file():
        raise FileNotFoundError(f"Missing pinned schema: {source}")
    found.add(name)
    for imported in IMPORT.findall(source.read_text(encoding="utf-8")):
        dependencies(imported, found)


def generate(directory: Path) -> list[Path]:
    selected: set[str] = set()
    for name in ROOT_SCHEMAS:
        dependencies(name, selected)
    # protoc treats the extra dot in *.steamclient.proto as a Python package
    # boundary. Normalize just the copied compilation inputs instead.
    with tempfile.TemporaryDirectory(prefix="pysteam-schema-") as temporary:
        normalized = Path(temporary)
        for name in selected:
            source = (SCHEMAS / name).read_text(encoding="utf-8")
            if name == "steammessages_twofactor.steamclient.proto":
                source = _twofactor_compat_fields(source)
            source = source.replace(".steamclient.proto", "_steamclient.proto")
            (normalized / name.replace(".steamclient.proto", "_steamclient.proto")).write_text(
                source, encoding="utf-8", newline="\n"
            )
        bundled_protos = Path(grpc_tools.__file__).parent / "_proto"
        args = [
            "grpc_tools.protoc",
            f"-I{normalized}",
            f"-I{bundled_protos}",
            f"--python_out={directory}",
            f"--pyi_out={directory}",
        ]
        args.extend(
            str(normalized / name.replace(".steamclient.proto", "_steamclient.proto"))
            for name in sorted(selected)
        )
        if protoc.main(args) != 0:
            raise RuntimeError("protoc failed")
    generated = sorted((*directory.glob("*_pb2.py"), *directory.glob("*_pb2.pyi")))
    for path in generated:
        source = path.read_text(encoding="utf-8")
        source = GENERATED_IMPORT.sub(r"from . import \1 as ", source)
        path.write_text(source, encoding="utf-8", newline="\n")
    return generated


def _run(*, check: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="pysteam-proto-") as temporary:
        generated = generate(Path(temporary))
        if check:
            stale = [
                path.name
                for path in generated
                if not filecmp.cmp(path, DESTINATION / path.name, shallow=False)
            ]
            existing = {*DESTINATION.glob("*_pb2.py"), *DESTINATION.glob("*_pb2.pyi")}
            unexpected = {p.name for p in existing} - {p.name for p in generated}
            if stale or unexpected:
                print(f"Generated protobufs differ: stale={stale}, unexpected={sorted(unexpected)}")
                return 1
            print(f"Verified {len(generated)} generated protobuf modules")
            return 0
        DESTINATION.mkdir(parents=True, exist_ok=True)
        for path in (*DESTINATION.glob("*_pb2.py"), *DESTINATION.glob("*_pb2.pyi")):
            path.unlink()
        for path in generated:
            shutil.copy2(path, DESTINATION / path.name)
        print(f"Generated {len(generated)} protobuf modules")
        return 0


main = typer.Typer(
    help="Generate Python classes from the pinned Steam protobuf schemas.", add_completion=False
)


@main.command()
def generate_command(
    check: Annotated[
        bool, typer.Option("--check", help="Verify generated files are current.")
    ] = False,
) -> None:
    result = _run(check=check)
    if result:
        raise typer.Exit(code=result)


if __name__ == "__main__":
    main()
