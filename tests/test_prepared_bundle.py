import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("restore_prepared_data", Path(__file__).parents[1] / "scripts/restore_prepared_data.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_restore_verifies_hash_and_never_overwrites_local_data(tmp_path):
    source = tmp_path / "prepared.db"
    source.write_bytes(b"TEST_ONLY")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"database_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}))
    target = tmp_path / "local.db"
    assert "restored" in module.restore(source, manifest, target)
    assert target.read_bytes() == b"TEST_ONLY"
    target.write_bytes(b"EXISTING_LOCAL_DATA")
    assert "preserved" in module.restore(source, manifest, target)
    assert target.read_bytes() == b"EXISTING_LOCAL_DATA"


def test_restore_rejects_modified_bundle_before_writing(tmp_path):
    source = tmp_path / "prepared.db"
    source.write_bytes(b"CORRUPT_TEST_ONLY")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"database_sha256": "0" * 64}))
    target = tmp_path / "local.db"
    with pytest.raises(ValueError, match="hash mismatch"):
        module.restore(source, manifest, target)
    assert not target.exists()
