"""Save separately evidenced daily horizons, preserving all existing frozen studies.

Only development data through 15 September 2026 are opened for new configurations.
The already reported final period is never retuned or scored as a new final test.
Research snapshot assumptions apply; no weather/news price coefficients are learned.
"""
import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from app.config import ROOT
from app.crop_horizons import POLICY, benchmark_rows, causal_origins, horizon_frame, select_direct
from app.db import SessionLocal
from app.decision_support import CROP_PLANNING_CEILINGS
from app.features import FEATURES, Plan
from app.forecasting import fit, runtime_versions, save_champion
from app.research import LIMITATION, snapshot
from train_current_crops import SCOPES, study_plan

SCOPES = {'Tomato':('Kolar APMC','Tomato','tomato','local'), **SCOPES}


def crop_plan(crop):
    if crop != 'Tomato':
        return study_plan(crop)
    return Plan(date(2025,7,3),date(2026,7,15),date(2026,9,15),date(2026,11,4),
        'tomato','local',source_kind='verified',candidate_suite='recent_v3',min_train=90,
        min_validation=20,min_train_span_days=90)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train_crop(crop, register):
    plan=crop_plan(crop)
    with SessionLocal() as session:
        development,sources=snapshot(session,plan)
    fingerprint=hashlib.sha256(development.to_csv(index=False).encode()).hexdigest()
    identity={'plan':plan.serializable(),'fingerprint':fingerprint,'policy':POLICY,
        'code_sha256':{name:digest(ROOT/'backend/app'/name) for name in ('crop_horizons.py','features.py','forecasting.py')},
        'training_script_sha256':digest(ROOT/'scripts/train_crop_horizons.py'),
        'runtime':runtime_versions(),'daily_horizon_ceiling':CROP_PLANNING_CEILINGS[crop]}
    identity_hash=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
    folder=ROOT/'models/crop-horizons'/identity_hash
    report_path=folder/'comparison.json'
    scope=SCOPES[crop]
    registry_path=ROOT/'research-serving-registry.json'
    registry=json.loads(registry_path.read_text(encoding='utf-8-sig')) if registry_path.exists() else []
    # Existing 1/3/7 champions and their consumed tests are immutable.
    preserved={1,3,7}
    if report_path.exists():
        report=json.loads(report_path.read_text(encoding='utf-8'))
        if report['identity']!=identity:
            raise ValueError('Frozen daily-horizon run changed')
        print('FROZEN_REUSE',crop,identity_hash,flush=True)
    else:
        folder.mkdir(parents=True)
        origins=causal_origins(development,plan.start,plan.validation_end)
        report={'identity':identity,'version':identity_hash,'plan':plan.serializable(),
            'created_at':datetime.now(UTC).isoformat(),'research_only':True,'source':sources,
            'source_fingerprint':fingerprint,'status':'daily_horizon_research','horizons':[],
            'limitations':LIMITATION+' This extension has NO new final test. Selection validation scores are not final accuracy.',
            'final_evaluation':None,'final_holdout':'excluded; previously consumed final dates never opened',
            'selection_policy':'Horizon-specific direct models; predeclared naive only where selection is impossible but baseline evidence meets policy.'}
        dated=[]
        for horizon in range(1,CROP_PLANNING_CEILINGS[crop]+1):
            if horizon in preserved:
                continue
            frame=horizon_frame(origins,development,horizon,plan.validation_end)
            result,model=select_direct(frame,plan,horizon)
            report['horizons'].append(result)
            if result['champion']:
                champion=folder/f'champion-{horizon}d'
                meta=save_champion(champion,result,model,frame,plan,fingerprint)
                meta.update(research_only=True,limitations=report['limitations'],
                    trained_before=datetime.now(UTC).isoformat(),selection_report=report_path.relative_to(ROOT).as_posix(),
                    source=sources,empirical_calibration={'radii':{},'reason':'No independent long-horizon residual calibration; sensitivity scenarios are not prediction intervals'},
                    horizon_evidence_status=result['status'],feature_schema=FEATURES,
                    refit_policy='Frozen development-selected configuration. No new final holdout evaluation.')
                # Refit on all eligible current labels only after selection freezes.
                # Current prices are not loaded during selection or benchmark scoring.
                dated.append(benchmark_rows(frame,result,model))
                (champion/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8')
            if horizon<=14 or horizon%30==0 or horizon==CROP_PLANNING_CEILINGS[crop]:
                print('HORIZON',crop,horizon,result['status'],result['champion'],result['sample_policy'],flush=True)
        if dated:
            pd.concat(dated,ignore_index=True).to_csv(folder/'development-predictions.csv',index=False)
        report['predictions_sha256']=digest(folder/'development-predictions.csv') if dated else None
        report_path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        # Reports freeze before runtime refits; source fingerprints stay separate.
        with SessionLocal() as session:
            from dataclasses import replace
            today=datetime.now(UTC).date()
            current,current_sources=snapshot(session,replace(plan,validation_end=today,holdout_end=today+timedelta(days=1)))
        current_origins=causal_origins(current,plan.start,today)
        for result in report['horizons']:
            if not result['champion']:
                continue
            horizon=result['horizon']
            path=folder/f'champion-{horizon}d'
            frame=horizon_frame(current_origins,current,horizon,today)
            # Use the existing helper to write a fresh refit in a child directory.
            import pickle
            payload=pickle.dumps(fit(result['champion'],frame),protocol=5)
            (path/'model.pkl').write_bytes(payload)
            meta=json.loads((path/'metadata.json').read_text(encoding='utf-8'))
            meta.update(model_sha256=hashlib.sha256(payload).hexdigest(),selection_report_sha256=digest(report_path),
                training_samples=len(frame),training_window=[frame.origin_date.min(),frame.origin_date.max()],
                training_source_fingerprint=hashlib.sha256(current.to_csv(index=False).encode()).hexdigest(),
                source=current_sources,trained_before=datetime.now(UTC).isoformat())
            (path/'metadata.json').write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8')
    if register:
        # Replace only this scope's previous daily extension, preserving short models.
        kept=[]
        for item in registry:
            meta=json.loads((ROOT/item['directory']/'metadata.json').read_text(encoding='utf-8'))
            if tuple(meta[k] for k in ('market','commodity','variety','grade'))==scope and meta.get('horizon_evidence_status'):
                continue
            kept.append(item)
        for result in report['horizons']:
            path=folder/f"champion-{result['horizon']}d"
            if result['champion']:
                kept.append({'directory':path.relative_to(ROOT).as_posix(),'metadata_sha256':digest(path/'metadata.json')})
        registry_path.write_text(json.dumps(kept,indent=2),encoding='utf-8')
    entry={'directory':folder.relative_to(ROOT).as_posix(),'comparison_sha256':digest(report_path)}
    (ROOT/'reports'/f'daily-{crop.lower()}-entry.json').write_text(json.dumps(entry,indent=2),encoding='utf-8')
    active=[r['horizon'] for r in report['horizons'] if r['champion']]
    selected=sum(r['status']=='selected_validation_only' for r in report['horizons'])
    print('SAVED',crop,len(active),'new horizons; selected',selected,'max',max(active,default=None),flush=True)
    return report,entry


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commodity',choices=[*SCOPES,'all'],default='all')
    parser.add_argument('--register',action='store_true')
    args=parser.parse_args()
    selected=SCOPES if args.commodity=='all' else [args.commodity]
    reports=[]
    for crop in selected:
        report,entry=train_crop(crop,args.register)
        reports.append({'commodity':crop,'entry':entry,'available':[r for r in report['horizons'] if r['champion']],
            'unavailable':[{'horizon':r['horizon'],'reasons':r['reason'],'samples':r['sample_policy']} for r in report['horizons'] if not r['champion']]})
    path=ROOT/'reports/daily-horizon-coverage.json'
    path.write_text(json.dumps({'research_only':True,'final_test_performed':False,'crops':reports},indent=2,allow_nan=False),encoding='utf-8')
    print('REPORT',path,flush=True)


if __name__=='__main__':
    main()
