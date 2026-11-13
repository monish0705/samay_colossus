import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, CROP_SCOPES } from './api';
import { useApp } from './state';
import { localize, t } from './i18n';
import { buildRecommendation, getEffectiveAdvisorValues, validateAdvisor, type AdvisorValues } from './advisor';
import { Card, ErrorState, Notice, PageHeading, inr, qty, useResource } from './ui';
import { ResultSummary } from './Results';
import { MarketContextPanel } from './DecisionPanel';
import './simple-advisor.css';
import './crop-picker.css';

type NumericKey = 'quantity' | 'price' | 'cash' | 'capacity' | 'limit' | 'loss' | 'storage' | 'storageFixed' | 'transportFixed' | 'transportVariable' | 'commission' | 'marketFee' | 'handling' | 'fixedTransaction' | 'increment' | 'minimumLot' | 'step' | 'downsidePercent' | 'adversePercent' | 'upsidePercent' | 'realization' | 'adverse' | 'rainThreshold';
const steps = ['Crop and cash', 'Storage and costs', 'Review your plan'];

export function AdvisorPage({ explorer = false }: { explorer?: boolean }) {
  const { scope, setScope, draft, setDraft, setResult, result, catalog } = useApp();
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [advanced, setAdvanced] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const navigate = useNavigate();
  const crop = CROP_SCOPES[scope.commodity] || CROP_SCOPES.Tomato;
  const hasStorage = Number(draft.capacity) > 0;
  const latest = useResource(signal => api.latest(scope, signal), JSON.stringify(scope));
  const observation = latest.data?.observation;
  const mandiPrice = !latest.loading && !latest.error && !latest.data?.stale && observation?.market === scope.market && observation?.commodity === scope.commodity && observation?.variety === scope.variety && observation?.grade === scope.grade ? String(observation.modal_price_inr_per_quintal) : '';
  useEffect(() => {
    setDraft(old => ({ ...old, price: mandiPrice, notes: `Mandi modal reference dated ${observation?.report_date || 'unavailable'}; estimated realization, not a buyer offer.`, example: false }));
    if (mandiPrice) setErrors(old => ({ ...old, price: '' }));
  }, [mandiPrice, observation?.report_date, setDraft]);
  const availableHorizons = [...(catalog.data?.models.models || []), ...(catalog.data?.models.research_models || [])]
    .filter(m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade && m.model_version).map(m => m.horizon);
  const holdingDates = [...new Set([...crop.holdingOptions, ...availableHorizons.map(String)])].filter(d => Number(d) <= crop.maxDays).sort((a, b) => Number(a) - Number(b));
  const change = <K extends keyof AdvisorValues>(key: K, value: AdvisorValues[K]) => {
    setDraft({ ...draft, [key]: value, example: false });
    setErrors(old => ({ ...old, [key]: '' }));
  };
  const focusField = (key: string) => setTimeout(() => {
    const input = document.getElementById(`advisor-${key}`);
    let parent = input?.parentElement;
    while (parent) { if (parent instanceof HTMLDetailsElement) parent.open = true; parent = parent.parentElement; }
    input?.focus();
  }, 0);
  const move = (next: number) => { setStep(next); setError(null); setTimeout(() => heading.current?.focus(), 0); };
  const chooseCrop = (name: string) => {
    const selected = CROP_SCOPES[name];
    setScope({ market: selected.market, commodity: selected.commodity, variety: selected.variety, grade: selected.grade });
    setDraft({ ...draft, price: '', capacity: '0', days: selected.defaultDays, limit: String(selected.maxDays), loss: selected.dailyLossPercent,
      storage: selected.dailyStorageRate, storageFixed: '0', commission: selected.commissionPercent, marketFee: selected.marketFeePercent,
      transportFixed: selected.transportFixed, transportVariable: selected.transportVariable, handling: selected.handlingRate,
      conditions: selected.warehouse.facilityType, notes: `Farmer-entered buyer quote and costs at ${selected.market}`, acknowledged: false, example: false });
    setErrors({});
  };
  const field = (key: NumericKey, label: string, unit: string, hint?: string) => <div className="field">
    <label htmlFor={`advisor-${key}`}><span>{t(label)}</span></label><div className="input-wrap"><input id={`advisor-${key}`} inputMode="decimal" type="text" autoComplete="off"
      value={draft[key]} onChange={e => change(key, e.target.value)} aria-invalid={Boolean(errors[key])} aria-describedby={`hint-${key}`} /><span>{t(unit)}</span></div>
    <small id={`hint-${key}`} className={errors[key] ? 'field-error' : 'field-hint'}>{t(errors[key] || hint || '')}</small>
  </div>;
  const check = (current: number) => {
    const effective = getEffectiveAdvisorValues(draft, undefined, scope.commodity);
    const problems = validateAdvisor({ ...effective, price: mandiPrice, acknowledged: true }, scope.commodity);
    if (!mandiPrice) problems.price = latest.data?.stale ? 'Mandi price is too old. Refresh market data before calculating.' : 'Mandi price is unavailable. Try again after market data is loaded.';
    if (!(Number(draft.quantity) > 0)) problems.quantity = 'Enter a value greater than zero.';
    const first = ['quantity', 'price', 'cash'];
    const selected = Object.fromEntries(Object.entries(problems).filter(([key]) => current === 0 ? first.includes(key) : !first.includes(key)));
    setErrors(selected);
    if (Object.keys(selected).length) {
      const key = Object.keys(selected)[0];
      if (!['quantity', 'price', 'cash', 'capacity', 'storage', 'loss'].includes(key)) setAdvanced(true);
      focusField(key);
      return false;
    }
    return true;
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (step < 2) { if (check(step)) move(step + 1); return; }
    const effective = getEffectiveAdvisorValues({ ...draft, price: mandiPrice }, undefined, scope.commodity);
    const problems = validateAdvisor(effective, scope.commodity);
    setErrors(problems);
    if (Object.keys(problems).length) {
      const key = Object.keys(problems)[0];
      if (key !== 'acknowledged') { setAdvanced(true); move(['quantity', 'price', 'cash'].includes(key) ? 0 : 1); focusField(key); }
      return;
    }
    setBusy(true); setError(null);
    try {
      const request = buildRecommendation(effective, scope, (catalog.data?.data || await api.data()).historical_demo_date, availableHorizons);
      const response = await api.recommend({ ...request, use_mandi_price: true });
      setResult(response);
      if (!explorer) navigate('/results');
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return localize(<div className="simple-advisor">
    <PageHeading eyebrow={t(explorer ? 'SCENARIO EXPLORER' : 'SELLING ADVISOR')} title={t('Should I sell or wait?')}>
      {t('Tell us what you have and what you need. We will compare the options.')}
    </PageHeading>
    <nav aria-label={t('Farmer workflow')} className="simple-progress"><ol>{steps.map((title, index) => <li key={title} aria-current={index === step ? 'step' : undefined}><span>{index + 1}</span>{t(title)}</li>)}</ol></nav>
    <form onSubmit={submit} noValidate>
      <Card>
        <p className="eyebrow">{t('Step {current} of 3', { current: step + 1 })}</p>
        <h2 ref={heading} tabIndex={-1}>{t(steps[step])}</h2>
        {step === 0 && <>
          <fieldset className="crop-choice-group"><legend>{t('Choose your crop')}</legend><div className="crop-choice-row">{Object.values(CROP_SCOPES).map(c => <button type="button" key={c.id} aria-pressed={scope.commodity === c.commodity} className="crop-choice" onClick={() => chooseCrop(c.id)}><span aria-hidden="true" className="crop-emoji">{c.icon}</span><strong>{t(c.commodity)}</strong><small>{t(c.market)}</small></button>)}</div></fieldset>
          <div className="mandi-price-box" role="status"><span>{t('Mandi price used automatically')}</span><strong>{latest.loading ? t('Loading market price') : mandiPrice ? `${inr(mandiPrice)} / ${t('qtl')}` : t('Unavailable')}</strong><small>{observation?.report_date || ''} · {observation?.source || ''}</small><p>{t('This is a wholesale reference, not a confirmed buyer offer.')}</p></div>
          {!latest.loading && !mandiPrice && <Notice tone="amber">{t(latest.data?.stale ? 'Mandi price is too old. Refresh market data before calculating.' : 'Mandi price is unavailable. Try again after market data is loaded.')}</Notice>}
          <div className="form-grid">{field('quantity', 'Harvest quantity', 'qtl', '1 quintal = 100 kg')}{field('cash', 'Immediate net cash needed', 'INR', 'Enter zero if you do not need cash today.')}</div>
          <details><summary>{t('Need cash on a later date?')}</summary><label className="field" htmlFor="advisor-deadline">{t('When is this cash needed? (Cash deadline)')}<select id="advisor-deadline" value={draft.deadline || '0'} onChange={e => change('deadline', e.target.value)}>{[0, 3, 7, 14, 30].map(d => <option key={d} value={d}>{d === 0 ? t('Today') : t('Within {days} days', { days: d })}</option>)}</select></label></details>
        </>}
        {step === 1 && <>
          <fieldset className="simple-storage"><legend>{t('Can you safely store some of this crop?')}</legend><label><input type="radio" name="storageAvailable" checked={!hasStorage} onChange={() => change('capacity', '0')} />{t('No, I cannot store it')}</label><label><input type="radio" name="storageAvailable" checked={hasStorage} onChange={() => change('capacity', draft.quantity)} />{t('Yes, I have storage')}</label></fieldset>
          {hasStorage && <><div className="form-grid">{field('capacity', 'Available storage capacity', 'qtl')}<label className="field" htmlFor="advisor-days">{t('How many days can you safely store it?')}<select aria-label={t('How many days can you safely store it?')} id="advisor-days" value={draft.days} onChange={e => setDraft({ ...draft, days: e.target.value, limit: e.target.value, example: false })}>{holdingDates.map(d => <option key={d} value={d}>{t('{days} days', { days: d })}{catalog.loading ? ` · ${t('Checking forecast')}` : availableHorizons.includes(Number(d)) ? '' : ` · ${t('Scenario only')}`}</option>)}</select>{errors.days && <small role="alert">{t(errors.days)}</small>}</label>{field('storage', 'Daily storage charge', 'INR / qtl')}{field('loss', 'Assumed saleable loss per day', '%', 'Check this estimate for your crop and storage.')}</div><p className="simple-reference">{t('Loss and holding limits are estimates. Verify them locally.')} {t('Maximum holding time')}: {draft.limit} {t('days')}.</p></>}
          <div className="form-grid">{field('transportFixed', 'Fixed transport per trip', 'INR')}{field('commission', 'Commission', '% of gross')}</div>
          <p className="simple-reference">{t('Some costs use editable crop estimates. Check the details before you confirm.')}</p>
          <details className="simple-advanced" open={advanced} onToggle={e => setAdvanced(e.currentTarget.open)}><summary>{t('More options: costs and storage assumptions')}</summary>
            <div className="form-grid">{field('transportVariable', 'Transport per sold quintal', 'INR / qtl')}{field('marketFee', 'Market fee', '% of gross')}{field('handling', 'Handling per sold quintal', 'INR / qtl')}{field('fixedTransaction', 'Other fixed sale charge', 'INR')}{field('increment', 'Plan quantity increment', 'qtl')}{field('minimumLot', 'Minimum marketable lot', 'qtl')}{field('step', 'Market sale rounding step', 'qtl')}</div>
            {hasStorage && <><div className="form-grid">{field('limit', 'Maximum safe holding time', 'days', `Your locally verified limit; at most ${crop.maxDays} days`)}{field('storageFixed', 'Fixed storage charge', 'INR')}<label className="field">{t('When is storage paid?')}<select value={draft.payment} onChange={e => change('payment', e.target.value as AdvisorValues['payment'])}><option value="today">{t('Upfront today')}</option><option value="later">{t('At the later sale')}</option></select></label><label className="field" htmlFor="advisor-conditions">{t('Storage conditions & evidence')}<textarea id="advisor-conditions" value={draft.conditions} onChange={e => change('conditions', e.target.value)} /></label></div>
            <details><summary>{t('Price scenarios and weather settings')}</summary>
              <label className="checkbox-field"><input type="checkbox" checked={draft.conditionalAnalysis} onChange={e => change('conditionalAnalysis', e.target.checked)} />{t('Compare conditional sell-or-hold scenarios even when calibrated intervals are unavailable')}</label>
              <label className="checkbox-field"><input type="checkbox" checked={draft.compareDates} onChange={e => change('compareDates', e.target.checked)} />{t('Compare all saved forecast dates plus my selected date, within my holding limit')}</label>
              <label className="field" htmlFor="advisor-scenario-price">{t('Optional future buyer price assumption')}<input id="advisor-scenario-price" inputMode="decimal" value={draft.scenarioPrice || ''} onChange={e => change('scenarioPrice', e.target.value)} />{errors.scenarioPrice && <small role="alert">{t(errors.scenarioPrice)}</small>}</label>
              <p>{t('These percentages are your sensitivity assumptions, not model confidence bands. Review them using the evidence below.')}</p>
              <div className="form-grid">{field('downsidePercent', 'Lower-scenario price drop', '%')}{field('adversePercent', 'Adverse-scenario price drop', '%')}{field('upsidePercent', 'Upper-scenario price rise', '%')}{field('realization', 'Future buyer price / mandi forecast', '×')}{!draft.conditionalAnalysis && field('adverse', 'Adverse gross future price', 'INR / qtl')}</div>
              <label className="field">{t('Longer holding-date price basis')}<select value={draft.longReference} onChange={e => change('longReference', e.target.value as AdvisorValues['longReference'])}><option value="saved_forecast">{t('Use the saved forecast for this exact date; fail safely if unavailable')}</option><option value="require_user_price">{t('Require my future buyer quote')}</option><option value="flat_reference">{t('Use a flat dated price reference, not a trained forecast')}</option></select></label>
              <label className="field">{t('Storage exposure to rain')}<select value={draft.storageExposure} onChange={e => setDraft({ ...draft, storageExposure: e.target.value as AdvisorValues['storageExposure'], rainStop: false })}><option value="unknown">{t('Not verified')}</option><option value="protected">{t('Protected storage')}</option><option value="outdoor">{t('Outdoor or exposed storage')}</option></select></label>
              {draft.storageExposure === 'outdoor' && <><label className="checkbox-field"><input type="checkbox" checked={draft.rainStop} onChange={e => change('rainStop', e.target.checked)} />{t('Block holding if the rain threshold is reached or weather coverage is missing')}</label>{draft.rainStop && field('rainThreshold', 'Maximum allowed daily rain', 'mm')}</>}
            </details></>}
            <label className="field" htmlFor="advisor-notes">{t('Where did your quote and cost assumptions come from?')}<textarea id="advisor-notes" value={draft.notes} onChange={e => change('notes', e.target.value)} /></label>
          </details>
          <label className="field" htmlFor="advisor-risk">{t('Risk preference')}<select id="advisor-risk" value={draft.risk} onChange={e => change('risk', e.target.value as AdvisorValues['risk'])}><option value="conservative">{t('Conservative')}</option><option value="balanced">{t('Balanced')}</option><option value="aggressive">{t('Aggressive')}</option></select></label>
        </>}
        {step === 2 && <>
          <dl className="simple-review"><dt>{t('Crop')}</dt><dd>{t(scope.commodity)} · {t(scope.market)}</dd><dt>{t('Harvest quantity')}</dt><dd>{qty(draft.quantity)}</dd><dt>{t('Mandi reference price')}</dt><dd>{inr(draft.price)} / {t('qtl')}</dd><dt>{t('Immediate net cash needed')}</dt><dd>{inr(draft.cash || '0')}</dd><dt>{t('Available storage capacity')}</dt><dd>{qty(draft.capacity)}</dd>{hasStorage && <><dt>{t('Maximum holding time')}</dt><dd>{draft.limit} {t('days')}</dd><dt>{t('Assumed saleable loss per day')}</dt><dd>{draft.loss}%</dd><dt>{t('Daily storage charge')}</dt><dd>{inr(draft.storage)} / {t('qtl')}</dd></>}</dl>
          <details><summary>{t('Review all selling costs')}</summary><dl className="simple-review">{(['transportFixed', 'transportVariable', 'commission', 'marketFee', 'handling', 'fixedTransaction'] as const).map((key, i) => <div key={key}><dt>{t(['Fixed transport per trip', 'Transport per sold quintal', 'Commission', 'Market fee', 'Handling per sold quintal', 'Other fixed sale charge'][i])}</dt><dd>{['commission', 'marketFee'].includes(key) ? `${draft[key]}%` : inr(draft[key])}</dd></div>)}</dl></details>
          <Notice>{t('Future prices are uncertain. Holding may lead to a loss.')}</Notice>
          <label className="checkbox-field" htmlFor="advisor-acknowledged"><input id="advisor-acknowledged" type="checkbox" checked={draft.acknowledged} onChange={e => change('acknowledged', e.target.checked)} />{t('I have checked the prices, costs and storage estimates.')}</label>{errors.acknowledged && <p className="field-error" role="alert">{t(errors.acknowledged)}</p>}
          {hasStorage && <details><summary>{t('Weather and market context')}</summary><MarketContextPanel scope={scope} days={Math.max(7, Number(draft.days) || 7)} collapsed /></details>}
        </>}
        {Object.values(errors).some(Boolean) && <p role="alert" className="field-error">{t('Please correct the highlighted inputs before continuing.')}</p>}
        {Boolean(error) && <ErrorState error={error} />}
        <div className="simple-actions">{step > 0 && <button className="button button-secondary" type="button" disabled={busy} onClick={() => move(step - 1)}>{t('Back')}</button>}<button className="button button-primary" type="submit" disabled={busy}>{t(busy ? 'Calculating with the backend…' : step < 2 ? 'Continue' : explorer ? 'Recalculate with backend' : 'Calculate my sale plan')}</button></div>
      </Card>
    </form>
    {explorer && result && <Card><ResultSummary result={result} /></Card>}
  </div>);
}
