"""Isolated real HTTP E2E backend. Every generated observation is TEST_ONLY.

This helper never writes the workspace database or publishes performance claims.
"""
import argparse
import hashlib
import json
import os
from dataclasses import replace
from datetime import date, timedelta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    from pathlib import Path
    folder = Path(args.folder)
    os.environ["SAMAY_DATABASE_URL"] = f"sqlite:///{(folder / 'test-only.db').as_posix()}"
    os.environ["SAMAY_ENVIRONMENT"] = "test"
    os.environ["SAMAY_HISTORICAL_DEMO_DATE"] = "2025-11-04"
    os.environ["SAMAY_SERVICE_REGISTRY_PATH"] = str(folder / "registry.json")
    (folder / "research-registry.json").write_text("[]")
    os.environ["SAMAY_RESEARCH_REGISTRY_PATH"] = str(folder / "research-registry.json")
    from alembic import command
    from alembic.config import Config
    from app.backtesting import run_backtest
    from app.db import engine
    from app.features import FEATURES, Plan, load_vintages
    from app.forecasting import examples, fit, save_champion
    from app.ingestion import SourceManifest, import_csv
    from app.main import app
    from sqlalchemy.orm import Session

    command.upgrade(Config("backend/alembic.ini"), "head")
    start, last = date(2025, 1, 1), date(2025, 11, 2)
    cursor = start
    with Session(engine) as session, session.begin():
        while cursor <= last:
            end = min(cursor + timedelta(days=6), last)
            path = folder / f"TEST_ONLY-{end}.csv"
            lines = ["State,District,Market,Commodity,Variety,Grade,Arrival_Date,Min_Price,Max_Price,Modal_Price"]
            for i in range((end - cursor).days + 1):
                day = cursor + timedelta(days=i)
                lines.append(f"Karnataka,Kolar,Kolar,Tomato,Tomato,Local,{day:%d/%m/%Y},900,1200,{1000 + day.day % 5}")
            path.write_text("\n".join(lines))
            manifest = SourceManifest(source_label="HTTP_E2E_TEST_ONLY_NOT_GOVERNMENT_DATA", data_kind="official",
                source_url="https://data.gov.in/resource/variety-wise-daily-market-prices-data-commodity",
                fetched_at=f"{end}T18:00:00Z", price_unit="INR/quintal", unit_evidence="TEST_ONLY synthetic schema for isolated integration assertions")
            import_csv(session, path, manifest, folder / "imports")
            cursor = end + timedelta(days=1)
    plan = Plan(start, date(2025, 3, 15), date(2025, 11, 2), date(2025, 12, 31), "tomato", "local")
    feature = folder / "features"
    feature.mkdir()
    with Session(engine) as session:
        vintages, _ = load_vintages(session, plan)
    (feature / "metadata.json").write_text(json.dumps({"plan": plan.serializable(), "artifact_sha256": {}, "feature_columns": FEATURES,
        "vintages_sha256": hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()}))
    training = examples(vintages, date(2025, 2, 1), date(2025, 3, 15), 3, date(2025, 3, 16))
    champions = folder / "champions"
    save_champion(champions / "champion-3d", {"champion": "naive", "horizon": 3, "note": "TEST_ONLY predeclared baseline; not production selection"},
        fit("naive", training), training, replace(plan, train_end=date(2025, 3, 1), validation_end=date(2025, 3, 15)), "TEST_ONLY")
    # Only 3d has a saved artifact; other horizons use predeclared baselines for test evidence.
    # Build matching 3d evidence via the existing service, without test-only interval constants.
    with Session(engine) as session:
        evidence, _ = run_backtest(session, feature, date(2025, 4, 1), date(2025, 6, 30), date(2025, 10, 31), folder / "evidence")
    # Recompute 3d using the actually saved frozen champion, retain consistent artifact checksums.
    from app.reliability import calibrate, dated_predictions, evaluate
    meta = json.loads((evidence / "summary.json").read_text())
    version = json.loads((champions / "champion-3d/metadata.json").read_text())["version"]
    calibration_rows = dated_predictions(vintages, plan, date(2025, 4, 1), date(2025, 6, 30), 3, date(2025, 7, 1), champions / "champion-3d")
    calibration = calibrate(calibration_rows, 3, date(2025, 7, 1), meta["scope"], version)
    evaluated, assessment = evaluate(dated_predictions(vintages, plan, date(2025, 7, 1), date(2025, 10, 31), 3, date(2025, 11, 1), champions / "champion-3d"), calibration)
    calibration_rows.to_csv(evidence / "calibration-3d.csv", index=False)
    evaluated.to_csv(evidence / "evaluation-3d.csv", index=False)
    item = next(item for item in meta["horizons"] if item["horizon"] == 3)
    item.update(calibration=calibration, assessment=assessment, model_version=version)
    for name in meta["artifact_sha256"]:
        meta["artifact_sha256"][name] = hashlib.sha256((evidence / name).read_bytes()).hexdigest()
    (evidence / "summary.json").write_text(json.dumps(meta))
    (folder / "registry.json").write_text(json.dumps([{"feature_run": str(feature), "champions": str(champions), "evidence": str(evidence)}]))
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
