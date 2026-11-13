"""Summarize saved, hash-verified daily horizon evidence without training or selection."""
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

from app.config import ROOT


def main():
    registry=json.loads((ROOT/'research-serving-registry.json').read_text(encoding='utf-8-sig'))
    models=[]
    for entry in registry:
        raw=(ROOT/entry['directory']/'metadata.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['metadata_sha256']:
            raise ValueError('Serving metadata hash mismatch')
        models.append(json.loads(raw))
    result={'generated_at':datetime.now(UTC).isoformat(),'new_final_test_performed':False,
        'research_only':True,'all_saved_models':len(models),'crops':[]}
    lines=['# Daily crop horizon evidence','',
        'Retrospective snapshot research. Original publication/revision times are unverified.',
        'New horizons exclude the previously consumed final period. No new final accuracy is claimed.',
        'Most additions are predeclared last-observed-price baselines, not trained ML.', '',
        '| Crop | Saved current-grade calendar days | New daily artifacts | Development-selected | Fixed baseline only |',
        '|---|---|---:|---:|---:|']
    details=['','| Crop | Days | Evidence | Pairs / selection validation n | Nonoverlapping cases | MAE INR/quintal | RMSE INR/quintal | WAPE error % |',
        '|---|---:|---|---|---:|---:|---:|---:|']
    for path in sorted((ROOT/'reports').glob('daily-*-entry.json')):
        entry=json.loads(path.read_text(encoding='utf-8'))
        raw=(ROOT/entry['directory']/'comparison.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['comparison_sha256']:
            raise ValueError('Frozen daily evidence hash mismatch')
        report=json.loads(raw)
        plan=report['plan']
        scope=tuple(plan[k] for k in ('market','commodity','variety','grade'))
        saved=sorted(m['horizon'] for m in models if tuple(m[k] for k in ('market','commodity','variety','grade'))==scope)
        available=[r for r in report['horizons'] if r['champion']]
        statuses=Counter(r['status'] for r in available)
        algorithms=Counter(r['champion'] for r in available)
        crop={'commodity':plan['commodity'],'market':plan['market'],'variety':plan['variety'],'grade':plan['grade'],
            'saved_calendar_days':saved,'new_artifacts':len(available),'evidence_counts':dict(statuses),
            'algorithms':dict(algorithms),'source_fingerprint':report['source_fingerprint'],
            'development_end':plan['validation_end'],'no_new_final_test':True,'report':entry['directory']+'/comparison.json','examples':[]}
        result['crops'].append(crop)
        label=f'1–{max(saved)} (every day)' if saved==list(range(1,max(saved)+1)) else ', '.join(map(str,saved))
        lines.append(f"| {plan['commodity']} / {plan['variety']} / {plan['grade']} | {label} | {len(available)} | {statuses['selected_validation_only']} | {statuses['baseline_only']} |")
        ceiling=report['identity']['daily_horizon_ceiling']
        for horizon in sorted({14,30,60,90,120,180,365,730,ceiling}):
            if horizon>ceiling:
                continue
            row=next((r for r in report['horizons'] if r['horizon']==horizon),None)
            if not row:
                continue
            metrics=(row.get('retrospective_benchmark') or next((r['validation'] for r in row['comparisons'] if r['candidate']==row['champion']),{}))
            kind='fixed-rule retrospective benchmark' if row['status']=='baseline_only' else 'selection validation; not final' if row['champion'] else 'INSUFFICIENT'
            record={'horizon':horizon,'kind':kind,'model':row['champion'],'metrics':metrics or None,
                'sample_counts':row['sample_policy'],'reasons':row['reason']}
            crop['examples'].append(record)
            def fmt(key,metrics=metrics):
                return f"{metrics[key]:.2f}" if metrics.get(key) is not None else 'unavailable'
            sample=row['sample_policy']
            details.append(f"| {plan['commodity']} | {horizon} | {kind} | {sample['available_development_pairs']} / {sample['effective_validation_samples']} | {sample['nonoverlapping_benchmark_cases']} | {fmt('mae_inr_per_quintal')} | {fmt('rmse_inr_per_quintal')} | {fmt('wape_pct')} |")
    lines+=details+['',
        'WAPE is percentage error; 100 minus WAPE is not an accuracy score.',
        'Overlapping daily errors are dependent; the nonoverlapping count exposes how little independent long-horizon evidence exists.',
        'Three nonoverlapping cases are a minimal baseline-only gate, not proof of stable forecast quality or interval coverage.',
        'Validation errors participated in selection and are optimistic as performance estimates. Previously reported short-horizon final errors remain unchanged.',
        'A baseline may output the same point at several horizons because its rule is to retain the latest observed price. No upward trend is invented.',
        'No empirical interval is available for these additions; user stress bounds are assumptions, not calibrated probabilities.',
        'Audit rows and exact candidate comparisons live alongside each frozen comparison.json. Missing targets are excluded, never interpolated.']
    path=ROOT/'reports/daily-horizon-results.json'
    path.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(path.with_suffix('.md').read_text(encoding='utf-8'))


if __name__=='__main__':
    main()
