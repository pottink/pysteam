"""SteamPipe CSM/CSD and SKU round trips stay offline and source-preserving."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_archive import CONTENT, KEY, PASSWORD, _manifest

from pysteam import ArchiveStore, CDNError
from pysteam.sis import (
    export_sis,
    import_sis,
    inspect_csm,
    inspect_sis,
    repack_sis,
    write_csm_csd,
    write_sis,
)


def test_sis_round_trip_and_repack(tmp_path: Path) -> None:
    manifest, encrypted = _manifest()
    source = ArchiveStore(tmp_path / "archive", PASSWORD)
    source.save_key(123, KEY)
    source.save_manifest(manifest, app_id=220, branch="public")
    source.save_chunk(123, manifest.files[0].chunks[0], encrypted, KEY)
    record = source.list()[0]
    source.mark_complete(record)
    exported = export_sis(source, 220, tmp_path / "backup")
    assert exported.app_id == 220 and exported.manifests == {123: 456}
    assert exported.containers[0].read_chunk(exported.containers[0].entries[0]) == encrypted

    restored = ArchiveStore(tmp_path / "restored", PASSWORD)
    restored.save_key(123, KEY)
    restored.save_manifest(manifest, app_id=220, branch="public")
    assert import_sis(restored, exported) == {123: True}
    assert restored.extract(123, 456, tmp_path / "files")[0].read_bytes() == CONTENT
    repacked = repack_sis(exported, tmp_path / "repacked")
    assert repacked.containers[0].read_chunk(repacked.containers[0].entries[0]) == encrypted
    assert exported.path.read_bytes() == (tmp_path / "backup" / "sku.sis").read_bytes()


def test_sis_rejects_corrupt_index_and_overwrite(tmp_path: Path) -> None:
    sha, raw = b"a" * 20, b"encrypted-chunk"
    target = tmp_path / "123_depotcache_1"
    write_csm_csd(target, 123, ((sha, raw),))
    with pytest.raises(CDNError, match="exists"):
        write_csm_csd(target, 123, ((sha, raw),))
    write_sis(tmp_path / "sku.sis", 220, {123: 456})
    assert inspect_sis(tmp_path / "sku.sis").manifests == {123: 456}
    csm = target.with_suffix(".csm")
    csm.write_bytes(csm.read_bytes()[:-1])
    with pytest.raises(CDNError, match="invalid"):
        inspect_csm(csm)
