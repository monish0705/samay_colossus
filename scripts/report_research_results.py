"""Verify frozen prediction errors and publish an honest research report; never retrain."""
import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("research-registry.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/MODEL-RESULTS.md"))
    args = parser.parse_args()
    lines = ["# Actual SAMAY model results · 2026-11-04", "", "**Retrospective snapshot research only; not verified live/as-of performance.**",
        "", "Six genuine government CSV exports were downloaded through the official AGMARKNET website with CAPTCHA authorization. Original bytes, actual fetch times and hashes are retained. No fetch timestamp was backdated.",
        "", "1,943 official records were imported with zero quarantined, duplicate or revised rows in these six batches. Original source grades differ: 1,562 Tomato/FAQ, 371 Tomato/Local, 5 Tomato/Grade Range-1, 3 Hybrid/FAQ and 2 Hybrid/Local. Grades and varieties were not merged.",
        "", "FAQ ends 2025-06-30; Local begins 2025-07-03. That source metadata break required separate study windows before fitting. Counts/date coverage, rather than future price outcomes, determined those windows.",
        "", "All saved champions are baselines. Ridge, histogram boosting and (for the broad FAQ study) LightGBM were actually fitted/compared. They did not satisfy the predeclared baseline promotion policy.",
        "", "There is no defensible single price-regression 'accuracy percentage'. MAE/RMSE are INR/quintal errors; WAPE/sMAPE are percentage errors. Lower is better. Direction accuracy includes unchanged-price ties. Do not convert 100−WAPE into a claimed accuracy."]
    entries = json.loads(args.registry.read_text(encoding="utf-8"))
    for entry in entries:
        folder = Path(entry["directory"])
        content = (folder / "comparison.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["comparison_sha256"]:
            raise ValueError("Frozen research report hash changed")
        report = json.loads(content)
        plan = report["plan"]
        lines += ["", f"## Tomato / {plan['grade']}", "", f"Train: **{plan['start']}–{plan['train_end']}**. Selection validation: **{pd.Timestamp(plan['train_end']).date() + timedelta(days=1)}–{plan['validation_end']}**. Final holdout: **{pd.Timestamp(plan['validation_end']).date() + timedelta(days=1)}–{plan['holdout_end']}**.",
            "", f"Run: `{folder.as_posix()}`. Three chronological rolling-origin folds inside training; model choice uses development only. All selections were frozen before final rows were loaded. Final holdout was consumed once; no tuning or champion replacement used final errors.",
            "", "| Horizon | Frozen champion | Train n | Validation n | Final n | MAE | Naive MAE | RMSE | sMAPE % | WAPE % | Direction % |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        plot_folder = Path("reports/research") / folder.name
        plot_folder.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True)
        for final, ax in zip(report["final_evaluation"]["results"], axes, strict=True):
            horizon = final["horizon"]
            rows = pd.read_csv(folder / f"final-predictions-{horizon}d.csv")
            error = rows.prediction_inr_per_quintal.to_numpy() - rows.target_modal_price_inr_per_quintal.to_numpy()
            actual = rows.target_modal_price_inr_per_quintal.to_numpy()
            naive_error = rows.lag_1_obs_inr_per_quintal.to_numpy() - actual
            m, naive = final["metrics"], final["baseline_metrics"]["naive"]
            # Independent arithmetic checks against the auditable dated prediction CSV.
            assert len(rows) == final["n"]
            assert np.isclose(np.abs(error).mean(), m["mae_inr_per_quintal"])
            assert np.isclose(np.sqrt(np.mean(error ** 2)), m["rmse_inr_per_quintal"])
            assert np.isclose(100 * np.abs(error).sum() / np.abs(actual).sum(), m["wape_pct"])
            assert np.isclose(np.abs(naive_error).mean(), naive["mae_inr_per_quintal"])
            comparison = next(r for r in report["horizons"] if r["horizon"] == horizon)
            policy = comparison["sample_policy"]
            lines.append(f"| {horizon}d | {final['champion']} | {policy['effective_train_samples']} | {policy['effective_validation_samples']} | {final['n']} | {m['mae_inr_per_quintal']:.2f} | {naive['mae_inr_per_quintal']:.2f} | {m['rmse_inr_per_quintal']:.2f} | {m['smape_pct']:.2f} | {m['wape_pct']:.2f} | {100*m['directional_accuracy']:.2f} |")
            # Reindex for drawing gaps only; never interpolate or add scored observations.
            plotted = rows.set_index(pd.to_datetime(rows.target_date)).reindex(pd.date_range(rows.target_date.min(), rows.target_date.max()))
            ax.plot(plotted.index, plotted.target_modal_price_inr_per_quintal, label="Actual official modal price", linewidth=1.4, color="#163f32", marker=".", markersize=2)
            ax.plot(plotted.index, plotted.prediction_inr_per_quintal, label=f"Frozen {final['champion']}", linewidth=1, alpha=.85, color="#d7862d")
            ax.set_title(f"{horizon} calendar days · final n={final['n']} · MAE ₹{m['mae_inr_per_quintal']:.2f}/quintal")
            ax.set_ylabel("INR/quintal")
            ax.legend(loc="upper left", fontsize=8)
        fig.suptitle(f"SAMAY Tomato / {plan['grade']} — retrospective final holdout\nCurrent snapshot; original publication/revision timing unverified", fontsize=12)
        fig.savefig(plot_folder / "final-predictions.png", dpi=140)
        plt.close(fig)
        lines += ["", "### Actual candidate comparisons used for selection", "", "| Horizon | Candidate | CV mean MAE | CV MAE std | Selection-validation MAE | Promotable advanced candidate |",
            "| --- | --- | ---: | ---: | ---: | --- |"]
        for h in report["horizons"]:
            for candidate in h["comparisons"]:
                lines.append(f"| {h['horizon']}d | {candidate['candidate']} | {candidate['cv_mean_mae']:.2f} | {candidate['cv_std_mae']:.2f} | {candidate['validation']['mae_inr_per_quintal']:.2f} | {candidate.get('promotion_eligible', 'core baseline')} |")
        lines += ["", f"![Actual held-out predictions](../{plot_folder.as_posix()}/final-predictions.png)",
            "", f"Full metrics, all fold sizes, exclusions and runtime: `../{folder.as_posix()}/comparison.json`. Saved frozen artifacts: `champion-1d`, `champion-3d`, `champion-7d`. Each contains model.pkl, feature schema, actual training timestamp, source fingerprint and research-only metadata."]
        if plan["grade"] == "local":
            lines += ["", "**Failure disclosed:** the validation-selected 3d rolling mean has final MAE ₹212.82 versus naive ₹174.74. It did not generalize better. The 7d rolling mean only marginally improves final MAE (₹240.32 versus ₹240.57). The frozen choices were not swapped after observing these results."]
    lines += ["", "## Interpretation and limits", "", "A next-day midnight availability assumption is applied only in an explicitly labeled temporary research feature view. Actual database fetch timestamps remain unchanged. Current snapshot revisions may contain information unavailable at historical origins. Therefore these figures are conditional retrospective estimates, not validated live results.",
        "", "Missing exact target dates are excluded, not filled. Observation lags are not calendar-day lags. Targets crossing split boundaries are purged; fold scaling/fitting uses training data only. Final test sizes differ by horizon for these reasons.",
        "", "FAQ models concern an older grade series and cannot be presented as today's Local-grade forecasts. Local test evidence spans only two months. Neither study establishes agronomic holding safety, farmer transaction-price accuracy, profit improvement, calibrated uncertainty or guaranteed future coverage.",
        "", "Research artifacts are explicitly rejected by the production predictor and are displayed only as research evidence on the Transparency screen. No research result enables confident holding. Full source archive hashes and exact acquisition details are in ACQUISITION.md.",
        "", "## Reproduce / inspect frozen results", "", "```powershell",
        ".\\.venv\\Scripts\\python.exe scripts/train_research_snapshot.py --start 2021-01-01 --train-end 2023-12-31 --validation-end 2024-12-31 --test-end 2025-06-30 --variety tomato --grade faq --acknowledge-retrospective-limitations --evaluate-final",
        ".\\.venv\\Scripts\\python.exe scripts/train_research_snapshot.py --start 2025-07-03 --train-end 2026-06-30 --validation-end 2026-08-31 --test-end 2026-10-31 --variety tomato --grade local --acknowledge-retrospective-limitations --evaluate-final",
        ".\\.venv\\Scripts\\python.exe scripts/report_research_results.py", "```", "",
        "The same frozen run is returned on an unchanged rerun. A new selection/evaluation on the same consumed research holdout is refused. Retain final_evaluation_registry. Raw data, model binaries and generated reports are git-ignored and must be transferred separately with hashes."]
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Verified saved prediction metrics for all six horizon/series combinations. Report: {args.output}")


if __name__ == "__main__":
    main()
