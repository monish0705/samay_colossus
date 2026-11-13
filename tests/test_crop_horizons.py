"""TEST_ONLY leakage checks plus real, hash-pinned daily-horizon artifacts."""
import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from app.api_schemas import PredictRequest
from app.api_services import ServiceProblem, predict
from app.config import ROOT, get_settings
from app.crop_horizons import causal_origins, chronological_folds, horizon_frame, select_direct
from app.features import FEATURES, features_at
from app.forecasting import examples
from app.research_service import bundles
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_forecasting import case


def test_cached_horizons_match_original_exact_calendar_features_and_labels():
    rows,plan=case()
    origins=causal_origins(rows,plan.start,plan.validation_end)
    for horizon in (2,14,30,90,180):
        frame=horizon_frame(origins,rows,horizon,plan.validation_end)
        original=examples(rows,plan.start,plan.validation_end,horizon,plan.validation_end+timedelta(days=1))
        columns=['origin_date','target_date',*FEATURES,'target_modal_price_inr_per_quintal','label_available_at']
        pd.testing.assert_frame_equal(frame[columns].reset_index(drop=True),original[columns].reset_index(drop=True),check_dtype=False)
        assert (pd.to_datetime(frame.target_date)-pd.to_datetime(frame.origin_date)).dt.days.eq(horizon).all()


def test_long_horizon_features_and_folds_never_use_future_or_cross_boundary_labels():
    rows,plan=case()
    origin=plan.start+timedelta(days=100)
    before,_=features_at(rows,origin,90)
    changed=rows.copy()
    changed.loc[changed.report_date>=origin,'price']=999999
    after,_=features_at(changed,origin,90)
    assert before==after
    frame=horizon_frame(causal_origins(rows,plan.start,plan.validation_end),rows,30,plan.validation_end)
    train=frame[frame.target_date<=plan.train_end.isoformat()]
    folds=chronological_folds(train)
    assert len(folds)==3
    targets=[]
    for past,valid in folds:
        assert past.target_date.max()<valid.origin_date.min()
        targets.extend(valid.target_date)
    assert len(targets)==len(set(targets))
    # An absent target is not substituted with a neighbouring day.
    missing=rows.iloc[100].report_date
    sparse=rows[rows.report_date!=missing]
    other=horizon_frame(causal_origins(sparse,plan.start,plan.validation_end),sparse,30,plan.validation_end)
    assert missing.isoformat() not in set(other.target_date)


def test_longer_than_history_is_insufficient_and_fixed_baseline_is_explicit():
    rows,plan=case()
    origins=causal_origins(rows,plan.start,plan.validation_end)
    frame=horizon_frame(origins,rows,730,plan.validation_end)
    result,_=select_direct(frame,plan,730)
    assert result['champion'] is None and result['status']=='insufficient_data'
    frame=horizon_frame(origins,rows,90,plan.validation_end)
    result,_=select_direct(frame,replace(plan,min_train=90),90)
    assert result['status']=='baseline_only' and result['champion']=='naive'
    assert result['retrospective_benchmark']['mae_inr_per_quintal']==0
    assert result['final_evaluation'].startswith('not_performed')


def test_daily_training_artifacts_match_real_predictions_and_reject_missing_horizons(monkeypatch):
    monkeypatch.setenv('SAMAY_ENABLE_RESEARCH_FORECASTS','true')
    monkeypatch.setenv('SAMAY_RESEARCH_SERVING_REGISTRY_PATH',str(ROOT/'research-serving-registry.json'))
    get_settings.cache_clear()
    artifacts=[(folder,meta) for folder,meta in bundles() if meta.get('horizon_evidence_status')]
    assert len(artifacts)>=200
    when=max(datetime.fromisoformat(m['trained_before']) for _,m in artifacts)+timedelta(seconds=1)
    origin=when.astimezone(ZoneInfo('Asia/Kolkata')).date()
    db=ROOT/'data/prepared/samay.db'
    engine=create_engine('sqlite://',creator=lambda:sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True))
    selected={}
    try:
        for folder,meta in artifacts:
            assert hashlib.sha256((folder/'model.pkl').read_bytes()).hexdigest()==meta['model_sha256']
            key=meta['commodity']
            if key not in selected or meta['horizon']>selected[key][1]['horizon']:
                selected[key]=(folder,meta)
        with Session(engine) as session:
            for _,meta in selected.values():
                query=PredictRequest(**{k:meta[k] for k in ('market','commodity','variety','grade','horizon')})
                raw,result=predict(session,query,origin,'TEST_ONLY_DAILY',when)
                assert result.prediction_inr_per_quintal>0 and result.intervals==[]
                assert raw.reliability_status=='limited evidence'
                assert 'extended_horizon_no_new_final_test' in raw.flags
                with pytest.raises(ServiceProblem) as stale:
                    predict(session,query,origin+timedelta(days=10),'TEST_ONLY',when+timedelta(days=10))
                assert stale.value.code=='stale_market_data'
            query=PredictRequest(market='Tiptur APMC',commodity='Copra',variety='other',grade='local',horizon=365)
            with pytest.raises(ServiceProblem) as absent:
                predict(session,query,origin,'TEST_ONLY_DAILY',when)
            assert absent.value.code=='insufficient_horizon_evidence'
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_frozen_daily_reports_exclude_final_dates_and_benchmark_metrics_recompute():
    for entry_path in (ROOT/'reports').glob('daily-*-entry.json'):
        entry=json.loads(entry_path.read_text(encoding='utf-8'))
        folder=ROOT/entry['directory']
        content=(folder/'comparison.json').read_bytes()
        assert hashlib.sha256(content).hexdigest()==entry['comparison_sha256']
        report=json.loads(content)
        assert report['final_evaluation'] is None
        if not report['predictions_sha256']:
            continue
        raw=(folder/'development-predictions.csv').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==report['predictions_sha256']
        frame=pd.read_csv(folder/'development-predictions.csv')
        assert frame.target_date.max()<=report['plan']['validation_end']
        for row in report['horizons']:
            if not row['champion']:
                continue
            records=frame[frame.horizon==row['horizon']]
            metrics=row['retrospective_benchmark'] if row['status']=='baseline_only' else next(r['validation'] for r in row['comparisons'] if r['candidate']==row['champion'])
            assert len(records)==metrics['n']
            actual=np.mean(abs(records.prediction_inr_per_quintal-records.target_modal_price_inr_per_quintal))
            assert actual==pytest.approx(metrics['mae_inr_per_quintal'])


@pytest.mark.parametrize('crop,ceiling',[('Tomato',7),('Copra',365),('Arecanut',730),('Onion',120),('Potato',180)])
def test_crop_horizon_limits_are_strict(crop,ceiling):
    assert PredictRequest(commodity=crop,variety='local',grade='faq',horizon=ceiling).horizon==ceiling
    for value in (True,'30',0,ceiling+1):
        with pytest.raises(ValueError):
            PredictRequest(commodity=crop,variety='local',grade='faq',horizon=value)


def test_real_monthly_api_and_advisor_wiring_use_saved_model_and_fail_safely(tmp_path,monkeypatch):
    from app.api_routes import get_clock
    from app.main import app
    from app.prices import get_session
    from fastapi.testclient import TestClient
    from test_api_integration import recommendation

    monkeypatch.setenv('SAMAY_ENABLE_RESEARCH_FORECASTS','true')
    monkeypatch.setenv('SAMAY_RESEARCH_SERVING_REGISTRY_PATH',str(ROOT/'research-serving-registry.json'))
    get_settings.cache_clear()
    metadata=[m for _,m in bundles() if m.get('horizon_evidence_status')]
    when=max(datetime.fromisoformat(m['trained_before']) for m in metadata)+timedelta(seconds=1)
    database=tmp_path/'TEST_ONLY_monthly.db'
    with sqlite3.connect(ROOT/'data/prepared/samay.db') as source,sqlite3.connect(database) as destination:
        source.backup(destination)
    engine=create_engine(f'sqlite:///{database.as_posix()}',connect_args={'check_same_thread':False})
    def session_override():
        with Session(engine) as session:
            yield session
    previous=dict(app.dependency_overrides)
    app.dependency_overrides[get_session]=session_override
    app.dependency_overrides[get_clock]=lambda:when
    try:
        with TestClient(app) as client:
            scope={'market':'Tiptur APMC','commodity':'Copra','variety':'other','grade':'local'}
            response=client.get('/api/v1/models/horizons',params={**scope,'horizon':30})
            assert response.status_code==200,response.text
            coverage=response.json()
            assert coverage['saved_horizons']==list(range(1,61))
            assert coverage['requested_status']=='baseline_only'
            unavailable=client.get('/api/v1/models/horizons',params={**scope,'horizon':365}).json()
            assert unavailable['requested_status']=='insufficient_data' and unavailable['reasons']
            forecast=client.post('/api/v1/predict',json={**scope,'horizon':30})
            assert forecast.status_code==200,forecast.text
            body=recommendation()
            body.update(**scope,decision_at=when.isoformat(),maximum_horizon_days=365,today_price_inr_per_quintal='15000')
            body['crop_storage_profile'].update(commodity='Copra',maximum_holding_days=365)
            option=body['holding_options'][0]
            option.update(days=30,daily_loss_fractions=['.0003']*30,daily_storage_inr_per_quintal=['1.5']*30,
                realization_multiplier='1',adverse_inr_per_quintal='0')
            body['decision_policy']={'long_horizon_mode':'saved_forecast','assumption_source':'TEST_ONLY reviewed price stresses'}
            result=client.post('/api/v1/recommend',json=body)
            assert result.status_code==200,result.text
            data=result.json()
            assert data['predictions'][0]['model_version']==forecast.json()['model_version']
            assert data['predictions'][0]['horizon_calendar_days']==30
            assert float(data['decision_support']['plan']['cash_today_inr'])>=float(body['required_net_cash_inr'])
            assert data['optimization']['recommended_plan']['holding_days']==0
            option.update(days=365,daily_loss_fractions=['.0003']*365,daily_storage_inr_per_quintal=['1.5']*365)
            absent=client.post('/api/v1/recommend',json=body)
            assert absent.status_code==200,absent.text
            assert absent.json()['decision_support']['action']=='insufficient_evidence'
            assert absent.json()['decision_support']['plan'] is None
            assert absent.json()['decision_support']['safe_fallback_plan']['holding_days']==0
            assert absent.json()['predictions']==[]
            assert '365d:insufficient_horizon_evidence' in absent.json()['reliability_warnings']
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
        get_settings.cache_clear()
