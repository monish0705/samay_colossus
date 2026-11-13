"""Reclassify the known legacy synthetic batch without deleting observations."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def repair(path: Path):
    connection = sqlite3.connect(path)
    try:
        batches = connection.execute("SELECT id, manifest FROM import_batches WHERE filename = ? AND file_sha256 = ?",
            ("karnataka_mandis_multi_crop_2026.csv", hashlib.sha256(b"").hexdigest())).fetchall()
        corrected = 0
        with connection:
            for batch_id, original in batches:
                if json.loads(original).get("data_kind") == "demo":
                    continue
                corrected += connection.execute("UPDATE mandi_observations SET data_kind = 'demo', data_source = ? WHERE latest_batch_id = ? AND data_kind != 'demo'",
                    ("DEMO_DATA: generated random prices; not government observations", batch_id)).rowcount
                manifest = json.loads(original)
                if manifest.get("data_kind") != "demo":
                    manifest = {"data_kind": "demo", "source_label": "DEMO_DATA synthetic legacy series",
                        "reason": "Random generator previously mislabeled official; not eligible for training or live prices",
                        "corrected_at": datetime.now(UTC).isoformat(), "original_claims_for_audit_only": manifest}
                connection.execute("UPDATE import_batches SET data_kind = 'demo', source_label = ?, source_url = '', manifest = ? WHERE id = ?",
                    ("DEMO_DATA synthetic legacy series", json.dumps(manifest), batch_id))
            if corrected:
                connection.execute("UPDATE markets SET data_source = 'DEMO_DATA synthetic legacy series' WHERE id IN (SELECT market_id FROM mandi_observations GROUP BY market_id HAVING sum(data_kind = 'official') = 0 AND sum(data_kind = 'demo') > 0)")
                connection.execute("UPDATE commodities SET data_source = 'DEMO_DATA synthetic legacy series' WHERE id IN (SELECT commodity_id FROM mandi_observations GROUP BY commodity_id HAVING sum(data_kind = 'official') = 0 AND sum(data_kind = 'demo') > 0)")
        return {"corrected_observations": corrected, "observations_by_kind": dict(connection.execute("SELECT data_kind, count(*) FROM mandi_observations GROUP BY data_kind")),
                "action": "Reclassified in place; original generated values retained for audit; no authentic observations removed"}
    finally:
        connection.close()
