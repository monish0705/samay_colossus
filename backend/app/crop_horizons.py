"""Direct calendar-horizon research. Never recursively invent future input prices.

Existing final tests are excluded from this extension. Validation errors are
selection diagnostics, not new untouched final-test accuracy. A predeclared
persistence rule may be saved where selection is impossible, explicitly labeled
baseline-only; it is not described as a trained learned estimator.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.features import FEATURES, features_at, midnight
from app.forecasting import BASELINES, TARGET, fit, predict_rows, score

POLICY = {
    "minimum_baseline_pairs": 60,
    "minimum_baseline_span_days": 90,
    "minimum_nonoverlapping_cases": 3,
    "minimum_selection_train": 90,
    "minimum_selection_validation": 20,
    "minimum_fold_train": 60,
    "minimum_fold_validation": 14,
}


def causal_origins(vintages, start, end):
    """Compute each decision's history once, strictly before that decision."""
    rows = []
    for stamp in pd.date_range(start, end):
        origin = stamp.date()
        feature, audit = features_at(vintages, origin, 1)
        if np.isfinite(list(feature.values())).all() and feature['days_since_latest_report'] <= 7:
            rows.append({"origin_date": origin.isoformat(), **feature, **audit})
    return pd.DataFrame(rows, columns=['origin_date', *FEATURES, 'decision_at', 'history_count',
        'max_feature_report_date', 'max_feature_available_at', 'source_row_ids'])


def horizon_frame(origins, vintages, horizon, end):
    """Exact +h day labels; absent report dates remain absent, never filled."""
    from app.features import asof
    labels = asof(vintages, midnight(end + timedelta(days=1)), inclusive=False)
    mapping = {r.report_date.isoformat(): r for r in labels.itertuples()}
    frame = origins.copy()
    targets = [date.fromisoformat(origin)+timedelta(days=horizon) for origin in frame.origin_date]
    frame['target_date'] = [target.isoformat() for target in targets]
    frame['target_weekday'] = [target.weekday() for target in targets]
    frame['target_month'] = [target.month for target in targets]
    frame[TARGET] = frame.target_date.map(lambda key: float(mapping[key].price) if key in mapping else np.nan)
    frame['label_available_at'] = frame.target_date.map(lambda key: mapping[key].available_at.isoformat() if key in mapping else None)
    return frame[(frame.target_date <= end.isoformat()) & frame[TARGET].notna()].reset_index(drop=True)


def chronological_folds(train):
    """Disjoint validation targets; train labels settle before each fold starts."""
    for initial in range(POLICY['minimum_fold_train'], len(train)):
        first = train.iloc[initial].origin_date
        if sum(train.target_date < first) >= POLICY['minimum_fold_train']:
            break
    else:
        return []
    if len(train)-initial < 3*POLICY['minimum_fold_validation']:
        return []
    folds = []
    for lo, hi in zip(np.linspace(initial, len(train), 4, dtype=int)[:-1],
                      np.linspace(initial, len(train), 4, dtype=int)[1:], strict=True):
        valid = train.iloc[lo:hi].copy()
        first = valid.origin_date.min()
        cutoff = midnight(date.fromisoformat(first))
        past = train[(train.target_date < first) & (pd.to_datetime(train.label_available_at, utc=True) < cutoff)].copy()
        if len(past) < POLICY['minimum_fold_train'] or len(valid) < POLICY['minimum_fold_validation']:
            return []
        folds.append((past, valid))
    return folds


def nonoverlapping(frame, horizon):
    chosen, next_origin = [], ''
    for row in frame.itertuples():
        if row.origin_date >= next_origin:
            chosen.append(row.Index)
            next_origin = (date.fromisoformat(row.target_date)+timedelta(days=1)).isoformat()
    return frame.loc[chosen]


def select_direct(frame, plan, horizon):
    train = frame[(frame.target_date <= plan.train_end.isoformat()) &
        (pd.to_datetime(frame.label_available_at, utc=True)<midnight(plan.train_end+timedelta(days=1)))].copy()
    valid = frame[frame.origin_date > plan.train_end.isoformat()].copy()
    # Discard boundary origins whose labels cross train/validation boundaries.
    independent = nonoverlapping(frame, horizon)
    span = (date.fromisoformat(frame.origin_date.max())-date.fromisoformat(frame.origin_date.min())).days+1 if len(frame) else 0
    sample = {'effective_train_samples':len(train), 'effective_validation_samples':len(valid),
        'available_development_pairs':len(frame), 'nonoverlapping_benchmark_cases':len(independent),
        'train_span_calendar_days':span, 'status':'insufficient_data'}
    result = {'horizon':horizon, 'sample_policy':sample, 'status':'insufficient_data',
        'champion':None, 'comparisons':[], 'learned_model_eligible':False,
        'final_evaluation':'not_performed; existing final period excluded', 'reason':[],
        'selection_train_end':plan.train_end.isoformat()}
    if len(frame)<POLICY['minimum_baseline_pairs']:
        result['reason'].append('fewer_than_60_exact_dated_development_pairs')
    if span<POLICY['minimum_baseline_span_days']:
        result['reason'].append('less_than_90_calendar_days_of_origins')
    if len(independent)<POLICY['minimum_nonoverlapping_cases']:
        result['reason'].append('fewer_than_3_nonoverlapping_forecast_cases')
    if result['reason']:
        return result, None
    folds = chronological_folds(train)
    selection = len(train)>=90 and len(valid)>=20 and len(folds)==3
    if not selection:
        # This rule is fixed in advance, never selected using these errors.
        result.update(status='baseline_only', champion='naive', selection_reason='Predeclared last-observed-price rule; not selected/tuned on these errors',
            reason=['insufficient_separated_train_validation_folds_for_model_selection'],
            retrospective_benchmark=score('naive',None,frame),
            nonoverlapping_benchmark=score('naive',None,independent))
        sample['status']='baseline_only_limited_evidence'
        return result, None
    train_span=(date.fromisoformat(train.origin_date.max())-date.fromisoformat(train.origin_date.min())).days+1
    learned = len(train)>=120 and len(valid)>=30 and train_span>=180
    candidates=list(BASELINES)
    if learned:
        candidates += ['ridge_1','ridge_10','ridge_100','hist_gradient_boosting', 'ridge_return_10','ridge_return_100']
    for name in candidates:
        cv=[score(name,fit(name,t),v) for t,v in folds]
        result['comparisons'].append({'candidate':name, 'cv':cv,
            'cv_mean_mae':float(np.mean([m['mae_inr_per_quintal'] for m in cv])),
            'cv_std_mae':float(np.std([m['mae_inr_per_quintal'] for m in cv])),
            'validation':score(name,fit(name,train),valid)})
    by_name={r['candidate']:r for r in result['comparisons']}
    def rank(row):
        return row['validation']['mae_inr_per_quintal'],row['cv_std_mae'],row['validation']['p90_overprediction_inr_per_quintal'],row['candidate']
    admissible=[by_name[n] for n in BASELINES]
    reference=min(admissible,key=rank)
    for row in result['comparisons']:
        if row['candidate'] in BASELINES:
            continue
        wins=sum(all(row['cv'][i]['mae_inr_per_quintal']<by_name[b]['cv'][i]['mae_inr_per_quintal'] for b in BASELINES) for i in range(3))
        row['promotion_eligible']=wins>=2 and row['cv_mean_mae']<reference['cv_mean_mae'] and rank(row)[0]<rank(reference)[0]
        if row['promotion_eligible']:
            admissible.append(row)
    winner=min(admissible,key=rank)['candidate']
    result.update(status='selected_validation_only',champion=winner,learned_model_eligible=learned,
        selection_reason='Validation MAE with CV stability and downside tie-breaks; ML must beat all baselines in >=2/3 folds and the best validation baseline',
        folds=[{'train_n':len(t),'validation_n':len(v),'latest_training_target':t.target_date.max(),
            'first_validation_origin':v.origin_date.min(),'last_validation_target':v.target_date.max()} for t,v in folds])
    sample['status']='development_selection_only'
    return result, fit(winner,frame)


def benchmark_rows(frame, result, model):
    """Selection validation rows only for fitted models; fixed rule can use all origins."""
    if not result['champion']:
        return pd.DataFrame()
    if result['status']=='baseline_only':
        scored=frame
        predictions=predict_rows('naive',None,scored)
        kind='predeclared_baseline_retrospective_benchmark'
    else:
        # Use separately fitted training partition model; never the refit model.
        split=result['selection_train_end']
        train=frame[(frame.target_date<=split) & (pd.to_datetime(frame.label_available_at, utc=True)<midnight(date.fromisoformat(split)+timedelta(days=1)))]
        scored=frame[frame.origin_date>split]
        predictions=predict_rows(result['champion'],fit(result['champion'],train),scored)
        kind='selection_validation_not_final_test'
    output=scored[['origin_date','target_date',TARGET,'lag_1_obs_inr_per_quintal']].copy()
    output['prediction_inr_per_quintal']=predictions
    output['absolute_error_inr_per_quintal']=abs(predictions-output[TARGET])
    output['horizon']=result['horizon']
    output['evaluation_kind']=kind
    return output
