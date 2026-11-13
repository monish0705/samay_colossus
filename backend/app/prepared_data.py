"""Verified local bundle restoration; existing databases are never replaced."""
import hashlib
import json
import sqlite3
from pathlib import Path


def assert_public_market_snapshot(connection):
    """A market bundle must never publish accounts, contact tokens or sale histories."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    private = {'mandi_users', 'mandi_user_market_assignments', 'mandi_registrations',
               'notifications', 'notification_preferences', 'notification_deliveries', 'notification_outbox'}
    private |= {name for name in tables if name.startswith('sale_')}
    private |= {name for name in tables if name.startswith(('business_', 'private_', 'purchase_', 'farmer_sale_'))}
    private |= {'account_roles', 'account_workspace_preferences'}
    for name in sorted(tables & private):
        # Names originate from our schema, not request input.
        quoted = name.replace('"', '""')
        if connection.execute(f'SELECT EXISTS(SELECT 1 FROM "{quoted}")').fetchone()[0]:
            raise ValueError('Source contains private marketplace data. Build public bundles from a clean market-only database.')


def restore(source: Path, manifest: Path, target: Path):
    if target.exists():
        return "Existing local database preserved"
    content = source.read_bytes()
    expected = json.loads(manifest.read_text(encoding="utf-8"))["database_sha256"]
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Prepared database hash mismatch; refusing restoration")
    try:
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            assert_public_market_snapshot(connection)
    except sqlite3.DatabaseError as exc:
        raise ValueError('Prepared bundle is not a readable SQLite database') from exc
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
