"""Local recovery keeps old databases/settings and never substitutes demo prices."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from app.config import Settings
from app.prepared_data import bundled_environment


def bundle(root):
    folder=root/'data/prepared'
    folder.mkdir(parents=True)
    content=b'TEST_ONLY_BUNDLE_BYTES'
    (folder/'samay.db').write_bytes(content)
    (folder/'manifest.json').write_text(json.dumps({'database_sha256':hashlib.sha256(content).hexdigest()}))
    return folder


def test_bundled_profile_is_isolated_and_preserves_local_database_and_env(tmp_path):
    bundle(tmp_path)
    original_db=tmp_path/'samay.db'
    original_db.write_bytes(b'TEST_ONLY_EXISTING_DATABASE')
    settings=tmp_path/'.env'
    settings.write_text('SAMAY_ENABLE_RESEARCH_FORECASTS=false\n')
    environment={'SAMAY_DATABASE_URL':'sqlite:///old-empty.db','SAMAY_ENABLE_RESEARCH_FORECASTS':'false'}
    env,target,message=bundled_environment(tmp_path,environment)
    assert target.parent==tmp_path/'.local-data'
    assert target.read_bytes()==b'TEST_ONLY_BUNDLE_BYTES'
    assert env['SAMAY_DATABASE_URL']==f'sqlite:///{target.as_posix()}'
    assert env['SAMAY_ENABLE_RESEARCH_FORECASTS']=='true'
    assert env['SAMAY_RESEARCH_SERVING_REGISTRY_PATH']==str(tmp_path/'research-serving-registry.json')
    assert environment['SAMAY_ENABLE_RESEARCH_FORECASTS']=='false'
    assert original_db.read_bytes()==b'TEST_ONLY_EXISTING_DATABASE'
    assert settings.read_text()=='SAMAY_ENABLE_RESEARCH_FORECASTS=false\n'
    # Local recommendation history in the isolated database survives repeat launch.
    target.write_bytes(b'TEST_ONLY_EXISTING_PROFILE_HISTORY')
    _,same,message=bundled_environment(tmp_path,environment)
    assert same==target and 'preserved' in message
    assert target.read_bytes()==b'TEST_ONLY_EXISTING_PROFILE_HISTORY'


def test_bundled_profile_rejects_corrupt_source_even_if_profile_exists(tmp_path):
    folder=bundle(tmp_path)
    _,target,_=bundled_environment(tmp_path,{})
    (folder/'samay.db').write_bytes(b'TEST_ONLY_CORRUPTION')
    with pytest.raises(ValueError,match='hash mismatch'):
        bundled_environment(tmp_path,{})
    assert target.read_bytes()==b'TEST_ONLY_BUNDLE_BYTES'


def test_bundled_profile_overrides_old_replay_date_but_is_not_production_mode():
    settings=Settings(environment='test',bundled_research_mode=True,historical_demo_date='2025-01-01')
    assert settings.historical_demo_date is None
    with pytest.raises(ValueError,match='local development/test'):
        Settings(environment='production',bundled_research_mode=True)


def test_bundled_launcher_refuses_to_reuse_old_servers(tmp_path,monkeypatch):
    script=Path(__file__).resolve().parents[1]/'scripts/start_local.py'
    spec=importlib.util.spec_from_file_location('TEST_ONLY_start_local',script)
    launcher=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    python=tmp_path/'.venv/Scripts/python.exe'
    python.parent.mkdir(parents=True)
    python.write_text('TEST_ONLY never executed')
    vite=tmp_path/'frontend/node_modules/vite/bin/vite.js'
    vite.parent.mkdir(parents=True)
    vite.write_text('TEST_ONLY never executed')
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    monkeypatch.setattr(launcher,'ready',lambda url:True)
    monkeypatch.setattr(sys,'argv',['start_local.py','--bundled-research'])
    with pytest.raises(SystemExit,match='unused ports'):
        launcher.main()
    assert not (tmp_path/'.local-data').exists()
