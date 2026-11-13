"""Verified local bundle restoration; existing databases are never replaced."""
import hashlib
import json
from pathlib import Path


def restore(source: Path, manifest: Path, target: Path):
    if target.exists():
        return "Existing local database preserved"
    content = source.read_bytes()
    expected = json.loads(manifest.read_text(encoding="utf-8"))["database_sha256"]
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Prepared database hash mismatch; refusing restoration")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(content)
    except FileExistsError:
        return "Existing local database preserved"
    return "Prepared official observations restored; recommendation history is empty"


def bundled_environment(root: Path, environment: dict[str, str]):
    """Opt-in isolated research profile. Do not rewrite .env or an older samay.db."""
    folder = root / 'data/prepared'
    source, manifest = folder / 'samay.db', folder / 'manifest.json'
    expected = json.loads(manifest.read_text(encoding='utf-8'))['database_sha256']
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError('Prepared database hash mismatch; refusing bundled research profile')
    target = root / '.local-data' / f'bundled-{expected[:16]}.db'
    message = restore(source, manifest, target)
    env = {**environment, 'SAMAY_DATABASE_URL': f'sqlite:///{target.as_posix()}',
        'SAMAY_ENABLE_RESEARCH_FORECASTS': 'true', 'SAMAY_BUNDLED_RESEARCH_MODE': 'true',
        'SAMAY_RESEARCH_REGISTRY_PATH': str(root/'research-registry.json'),
        'SAMAY_RESEARCH_SERVING_REGISTRY_PATH': str(root/'research-serving-registry.json')}
    return env, target, message
