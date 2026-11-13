import { localize, t } from './i18n';
import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Calculator, Coins, SlidersHorizontal } from 'lucide-react';
import { api, CROP_SCOPES, type CropScopeConfig } from './api';
import { useApp } from './state';
import {
  buildRecommendation,
  exampleAdvisor,
  getEffectiveAdvisorValues,
  holdingDates,
  validateAdvisor,
  type AdvisorValues,
} from './advisor';
import { Badge, Card, ErrorState, Notice, PageHeading, useResource } from './ui';
import { ResultSummary } from './Results';
import { MarketContextPanel } from './DecisionPanel';

type NumericField = Exclude<keyof AdvisorValues, 'risk' | 'days' | 'payment' | 'notes' | 'conditions' | 'acknowledged' | 'example' | 'scenarioPrice' | 'conditionalAnalysis' | 'compareDates' | 'longReference' | 'storageExposure' | 'rainStop'>;

export function AdvisorPage({ explorer = false }: { explorer?: boolean }) {
  const { mode, scope, setScope, draft, setDraft, setResult, result, catalog } = useApp();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [dirty, setDirty] = useState(false);
  const [hasStorage, setHasStorage] = useState(Number(draft.capacity) > 0);
  const [overrideQuote, setOverrideQuote] = useState(Boolean(draft.price));

  const activeCrop: CropScopeConfig = CROP_SCOPES[scope.commodity] || CROP_SCOPES['Tomato'];

  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const latest = useResource(signal => api.latest(scope, signal), JSON.stringify(scope));
  const referencePrice = latest.data?.observation?.modal_price_inr_per_quintal || '';
  const latestPrice = latest.data?.stale ? '' : referencePrice;
  const effectiveDraft = getEffectiveAdvisorValues(draft, latestPrice, scope.commodity);
  const latestDate = latest.data?.observation?.report_date || '';
  const appliedPrice = draft.price || latestPrice;
  const estimatedGross = Math.round(Number(draft.quantity || 0) * Number(appliedPrice));

  const selectCrop = (cropKey: string) => {
    const nextCrop = CROP_SCOPES[cropKey];
    if (!nextCrop) return;
    setScope({
      market: nextCrop.market,
      commodity: nextCrop.commodity,
      variety: nextCrop.variety,
      grade: nextCrop.grade,
    });
    setDraft({
      ...draft,
      quantity: nextCrop.defaultQuantity,
      price: '',
      cash: nextCrop.defaultCash,
      capacity: hasStorage ? nextCrop.defaultQuantity : '0',
      days: nextCrop.defaultDays,
      limit: String(nextCrop.maxDays),
      loss: nextCrop.dailyLossPercent,
      storage: nextCrop.dailyStorageRate,
      storageFixed: '0',
      commission: nextCrop.commissionPercent,
      marketFee: nextCrop.marketFeePercent,
      transportFixed: nextCrop.transportFixed,
      transportVariable: nextCrop.transportVariable,
      handling: nextCrop.handlingRate,
      notes: `Farmer quote at ${nextCrop.market}`,
      conditions: nextCrop.warehouse.facilityType,
      example: false,
    });
    setOverrideQuote(false);
    setErrors({});
    setDirty(true);
  };

  useEffect(() => {
    if (draft.example && !explorer) setStep(4);
  }, [draft.example, explorer]);

  useEffect(() => {
    setHasStorage(Number(draft.capacity) > 0);
  }, [draft.capacity]);

  const stages = [
    'Market and crop',
    'Harvest and quote',
    'Required cash',
    'Storage and costs',
    'Review and calculate',
  ];

  const advance = () => {
    const issues: Record<string, string> = {};
    if (step === 1) {
      if (!draft.quantity || draft.quantity.trim() === '' || Number(draft.quantity) <= 0) {
        issues.quantity = 'Enter a value greater than zero.';
      }
      if (!(Number(draft.price || latestPrice) > 0)) {
        issues.price = 'Enter a value greater than zero.';
      }
    } else if (step === 2) {
      if (draft.cash && !/^\d+(\.\d{1,4})?$/.test(draft.cash)) {
        issues.cash = 'Enter a nonnegative number with up to four decimal places.';
      }
    }
    setErrors(issues);
    if (Object.keys(issues).length) {
      document.getElementById(`advisor-${Object.keys(issues)[0]}`)?.focus();
      return;
    }
    setStep(Math.min(4, step + 1));
  };

  const change = <K extends keyof AdvisorValues>(key: K, value: AdvisorValues[K]) => {
    if (key === 'price' && value) setOverrideQuote(true);
    setDraft({ ...draft, [key]: value, ...(key === 'storageExposure' ? { rainStop: false } : {}), example: false });
    setDirty(true);
    setErrors(old => ({ ...old, [key]: '' }));
  };

  const toggleStorage = (enable: boolean) => {
    setHasStorage(enable);
    if (!enable) {
      setDraft({ ...draft, capacity: '0', example: false });
    } else if (draft.capacity === '0' || !draft.capacity) {
      setDraft({
        ...draft,
        capacity: draft.quantity || activeCrop.defaultQuantity,
        days: activeCrop.defaultDays,
        limit: String(activeCrop.maxDays),
        loss: activeCrop.dailyLossPercent,
        storage: activeCrop.dailyStorageRate,
        example: false,
      });
    }
    setDirty(true);
  };

  const field = (key: NumericField, label: string, unit: string, hint?: string) => (
    <label className={`field field-${key}`} key={key} htmlFor={`advisor-${key}`}>
      <span>{t(label)}</span>
      <div className="input-wrap">
        <input
          id={`advisor-${key}`}
          type="text"
          inputMode="decimal"
          value={draft[key]}
          onChange={e => change(key, e.target.value)}
          aria-invalid={Boolean(errors[key])}
          aria-describedby={`hint-${key}`}
          autoComplete="off"
        />
        <span>{t(unit)}</span>
      </div>
      <small id={`hint-${key}`} className={errors[key] ? 'field-error' : 'field-hint'}>
        {errors[key] ? t(errors[key]) : hint ? t(hint) : ''}
      </small>
    </label>
  );




  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!explorer && step < 4) {
      advance();
      return;
    }
    const currentEffective = getEffectiveAdvisorValues(draft, latestPrice, scope.commodity);
    const currentProblems = validateAdvisor(currentEffective, scope.commodity);
    if (!draft.quantity || Number(draft.quantity) <= 0) {
      currentProblems.quantity = 'Enter a value greater than zero.';
    }
    if (!draft.acknowledged) {
      currentProblems.acknowledged = 'Confirm these assumptions before calculating.';
    }
    setErrors(currentProblems);
    if (Object.keys(currentProblems).length) {
      if (currentProblems.quantity && !explorer) {
        setStep(1);
        setTimeout(() => document.getElementById('advisor-quantity')?.focus(), 50);
      } else {
        const firstKey = Object.keys(currentProblems)[0];
        document.getElementById(`advisor-${firstKey}`)?.focus();
      }
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.recommend(
        buildRecommendation(currentEffective, scope, (catalog.data?.data || await api.data()).historical_demo_date, availableHorizons)
      );
      setResult(response);
      setDirty(false);
      if (!explorer) navigate('/results');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const deployed = catalog.data?.models.models.some(
    m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade && m.model_version
  );
  const researchAvailable = catalog.data?.models.research_models?.some(m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade && m.model_version);
  const availableHorizons = [...(catalog.data?.models.models || []),...(catalog.data?.models.research_models || [])].filter(m=>m.market===scope.market && m.commodity===scope.commodity && m.variety===scope.variety && m.grade===scope.grade && m.model_version).map(m=>m.horizon);

  return localize(
    <>
      <PageHeading
        eyebrow={explorer ? t('SCENARIO EXPLORER') : t('SELLING ADVISOR')}
        title={explorer ? t('Change an assumption. See the trade-off.') : t('A sale plan that starts with your needs.')}
        action={
          <button
            className="button button-secondary"
            onClick={() => {
              setDraft({ ...exampleAdvisor });
              setErrors({});
              setDirty(true);
              if (!explorer) setStep(4);
            }}
          >
            {t('Load labeled example')}
          </button>
        }
      >
        {explorer
          ? t('Recalculate through the real backend. Changing a slider never invents a new recommendation.')
          : t('Bring your buyer quote and actual costs. We’ll compare what you can sell today with what is safe to hold.')}
      </PageHeading>

      {draft.example && (
        <Notice>
          {t('EXAMPLE INPUTS: 20 quintals and ₹10,000 cash need. The ₹1,000 quote and costs are illustrative, not live prices or a fixed recommendation.')}
        </Notice>
      )}

      {!explorer && (
        <nav className="journey-nav" aria-label="Farmer workflow">
          <ol>
            {stages.map((title, index) => (
              <li key={title}>
                <button
                  type="button"
                  aria-current={step === index ? 'step' : undefined}
                  onClick={() => setStep(index)}
                >
                  <span>{index + 1}</span>
                  {t(title)}
                </button>
              </li>
            ))}
          </ol>
        </nav>
      )}

      <div className="advisor-layout">
        <form onSubmit={submit} noValidate className={`advisor-form ${explorer ? '' : `journey-view step-${step}`}`}>

          {Boolean(latest.error) && <Notice tone="amber">{t('Verified observations could not be loaded. Enter a buyer quote; no government rate is substituted.')}</Notice>}
          {latest.data?.stale && <Notice tone="amber">{t('Historical price only. Enter a current buyer quote; a stale observation is never used as today’s price.')}</Notice>}
          {/* STEP 0: Market & Crop Scope */}
          {!explorer && (
            <Card className="journey-market" hidden={step !== 0}>
              <p className="eyebrow">{t('STEP 1')}</p>
              <h2>{t('Select Karnataka Market & Crop')}</h2>
              <p className="muted small">
                {t('Select a crop. Historical observations and model availability are checked separately; storage and costs are user assumptions.')}
              </p>

              <div className="crop-selector-grid">
                {Object.values(CROP_SCOPES).map(c => {
                  const isSelected = scope.commodity === c.commodity;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      className={`crop-card ${isSelected ? 'is-selected' : ''}`}
                      onClick={() => selectCrop(c.id)}
                    >
                      <div className="crop-card-top">
                        <span className="crop-card-icon">{c.icon}</span>
                        <span className="crop-card-tag">{t(c.tag)}</span>
                      </div>
                      <strong className="crop-card-name">{t(c.commodity)}</strong>
                      <span className="crop-card-market">{t(c.market)}</span>
                      <div className="crop-card-footer">
                        <span>{t('Variety')} / {t('Grade')}</span>
                        <strong>{c.variety} / {c.grade}</strong>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Selected Crop Detail Banner */}
              <div className="selected-crop-banner">
                <Badge tone="green">{t('Active Scope: Karnataka Verified')}</Badge>
                <h3>{activeCrop.icon} {t(activeCrop.titleEn)}</h3>
                <p className="small muted">
                  {t(activeCrop.durabilityTextEn)}
                </p>
                <Notice tone="amber">{t('Storage profiles and costs are illustrative assumptions. Verify them locally before calculating.')}</Notice>
                <div className="crop-detail-meta">
                  <span><strong>{t('Scenario holding dates:')}</strong> {activeCrop.holdingOptions.join(', ')} {t('days')} (max {activeCrop.maxDays}d)</span>
                  <span><strong>{t('Illustrative daily loss assumption:')}</strong> ~{activeCrop.dailyLossPercent}%/{t('day')}</span>
                </div>
                <div className="reference-price-pill" style={{ marginTop: '12px' }}>
                  <Coins size={16} />
                  <span>
                    {t('Observed wholesale reference:')} <strong>{referencePrice ? `₹${referencePrice} / ${t('qtl')}` : t('Unavailable')}</strong> {latestDate && `(${latestDate})`}
                  </span>
                </div>
              </div>

              {mode === 'judge' && (
                <div className="form-grid" style={{ marginTop: '15px' }}>
                  <label className="field">Market
                    <select value={scope.market} onChange={e => {
                      const matched = Object.values(CROP_SCOPES).find(c => c.market === e.target.value);
                      if (matched) selectCrop(matched.id);
                    }}>
                      {Object.values(CROP_SCOPES).map(c => (
                        <option value={c.market} key={c.market}>{c.market}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">Commodity
                    <select value={scope.commodity} onChange={e => selectCrop(e.target.value)}>
                      {Object.values(CROP_SCOPES).map(c => (
                        <option value={c.commodity} key={c.commodity}>{c.commodity}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">Variety
                    <input value={scope.variety} onChange={e => setScope({ ...scope, variety: e.target.value.toLowerCase() })} />
                  </label>
                  <label className="field">Grade
                    <input value={scope.grade} onChange={e => setScope({ ...scope, grade: e.target.value.toLowerCase() })} />
                  </label>
                </div>
              )}
            </Card>
          )}

          {/* STEP 1 & 2: Harvest & Cash Needs */}
          <Card className="journey-harvest" hidden={!explorer && step !== 1 && step !== 2}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">01 · {t('YOUR HARVEST')}</p>
                <h2>{step === 2 && !explorer ? t('How much cash do you need today?') : t('Enter your harvest quantity')}</h2>
              </div>
              <Badge>{t('Farmer assumptions')}</Badge>
            </div>

            <div className="form-grid">
              {field('quantity', 'Harvest quantity', 'qtl', '1 quintal = 100 kg')}
              {field('cash', 'Immediate net cash needed', 'INR', 'After today’s costs and upfront storage')}
            </div>

            {/* Live Auto-Priced Projection Card */}
            {step === 1 && !explorer && (
              <div className="auto-gross-value-box">
                <div className="projection-main-row">
                  <div>
                    <span className="small muted">{t('Assumed gross price today:')}</span>
                    <strong className="rate-badge">₹{appliedPrice} / {t('qtl')}</strong>
                    <small className="muted"> ({scope.market} · {latestDate})</small>
                  </div>
                  <div className="projected-total">
                    <span className="small muted">{t('Estimated Gross Harvest Value:')}</span>
                    <strong className="gross-highlight">₹{estimatedGross.toLocaleString('en-IN')}</strong>
                    <small className="muted">{draft.quantity || '0'} {t('qtl')} × ₹{appliedPrice}</small>
                  </div>
                </div>

                {/* Override quote toggle */}
                {!overrideQuote && appliedPrice ? (
                  <button
                    type="button"
                    className="text-button override-toggle-btn"
                    onClick={() => setOverrideQuote(true)}
                  >
                    + {t('Have your own buyer quote? (Tap to override)')}
                  </button>
                ) : (
                  <div className="custom-quote-area">
                    <p className="small muted">{t('Your custom gross buyer quote overrides the government reference:')}</p>
                    {field('price', 'Expected buyer price today', 'INR / qtl', 'Your gross quote, not the mandi modal price')}
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => {
                        change('price', '');
                        setOverrideQuote(false);
                      }}
                    >
                      {latestPrice ? `${t('Use observed wholesale reference')} (₹${latestPrice})` : t('No observed reference available')}
                    </button>
                  </div>
                )}
              </div>
            )}

            {explorer && field('price', 'Expected buyer price today', 'INR / qtl', 'Your gross quote, not the mandi modal price')}
            {explorer && (
              <div className="scenario-sliders">
                <label>
                  {t('Adjust cash requirement')}{' '}
                  <input
                    type="range"
                    min="0"
                    max="500000"
                    step="500"
                    value={Math.min(Number(draft.cash) || 0, 500000)}
                    onChange={e => change('cash', e.target.value)}
                  />
                </label>
                <label>
                  {t('Adjust storage capacity')}{' '}
                  <input
                    type="range"
                    min="0"
                    max={Math.max(Number(draft.quantity) || 50, 1)}
                    step="0.5"
                    value={Math.min(Number(draft.capacity) || 0, Number(draft.quantity) || 50)}
                    onChange={e => change('capacity', e.target.value)}
                  />
                </label>
              </div>
            )}
          </Card>

          {/* STEP 3: Storage & Costs */}
          <Card className="journey-conditions" hidden={!explorer && step !== 3}>
            <p className="eyebrow">02 · {t('HOLDING CONDITIONS')}</p>
            <h2>{t('Storage is a real constraint.')}</h2>

            <div className="storage-toggle-row">
              <span>{t('Do you have safe storage available on your farm?')}</span>
              <div className="toggle-group" role="radiogroup" aria-label="Storage availability">
                <button
                  type="button"
                  aria-pressed={!hasStorage}
                  className={`button ${!hasStorage ? 'button-primary' : 'button-secondary'}`}
                  onClick={() => toggleStorage(false)}
                >
                  {t('No (Sell today)')}
                </button>
                <button
                  type="button"
                  aria-pressed={hasStorage}
                  className={`button ${hasStorage ? 'button-primary' : 'button-secondary'}`}
                  onClick={() => toggleStorage(true)}
                >
                  {t('Yes (Can hold)')}
                </button>
              </div>
            </div>

            {/* When farmer has NO on-farm storage: Show Nearby Storage Evaluation */}
            {!hasStorage ? (
              <Notice>{t('No verified storage facility or tariff is configured. Enter your actual storage quote and loss assumptions to compare plans.')}</Notice>
            ) : (
              <>
                <div className="form-grid">
                  {field('capacity', 'Available storage capacity', 'qtl', 'Use zero when holding is not possible')}
                  <label className="field">
                    <span>{t('Planned holding duration')}</span>
                    <select
                      value={draft.days}
                      onChange={e => change('days', e.target.value as AdvisorValues['days'])}
                    >
                      {[...new Set([...activeCrop.holdingOptions,...availableHorizons.map(String)])].sort((a,b)=>Number(a)-Number(b)).map(d => (
                        <option value={d} key={d}>{d} {t('calendar days · planning date')} · {t(availableHorizons.includes(Number(d)) ? 'Saved forecast' : 'Scenario only')}</option>
                      ))}
                    </select>
                    <small className="field-error">{errors.days ? t(errors.days) : ''}</small>
                  </label>
                  {field('limit', 'Verified crop holding limit', 'days', `Your locally verified limit; at most ${activeCrop.maxDays} days`)}
                  {field('loss', 'Assumed saleable loss per day', '%', 'Compounds daily; no universal spoilage rate')}
                  {field('storage', 'Daily storage charge', 'INR / qtl', 'Charged on each day’s opening quantity')}
                  {field('storageFixed', 'Fixed storage charge', 'INR')}
                  <label className="field">
                    <span>{t('When is storage paid?')}</span>
                    <select
                      value={draft.payment}
                      onChange={e => change('payment', e.target.value as AdvisorValues['payment'])}
                    >
                      <option value="today">{t('Upfront today')}</option>
                      <option value="later">{t('At the later sale')}</option>
                    </select>
                  </label>
                </div>

                <label className="field" htmlFor="advisor-conditions">
                  <span>{t('Storage conditions & evidence')}</span>
                  <textarea
                    id="advisor-conditions"
                    value={draft.conditions}
                    onChange={e => change('conditions', e.target.value)}
                    placeholder="Storage type, ripeness and source of loss/holding assumptions"
                    aria-invalid={Boolean(errors.conditions)}
                  />
                  <small className="field-error">{errors.conditions ? t(errors.conditions) : ''}</small>
                </label>

                {!deployed && (
                  <Notice>
                    {t(researchAvailable ? 'Saved forecasts are limited-evidence research. Review the selected horizon and assumptions; holding is conditional.' : 'No operational forecast is deployed for this series. Entering storage assumptions cannot enable a confident hold recommendation.')}
                    <p>{t('Saved horizons')}: {availableHorizons.length} · {t('Maximum saved horizon')}: {availableHorizons.length ? Math.max(...availableHorizons) : '—'} {t('days')}</p>
                    {Number(draft.capacity)>0 && !availableHorizons.includes(Number(draft.days)) && <p>{t('Insufficient evidence for this date. No future price will be invented.')}</p>}
                  </Notice>
                )}
              </>
            )}

            {hasStorage && (
              <div className="form-grid">
                <label className="checkbox-field"><input type="checkbox" checked={draft.conditionalAnalysis} onChange={e => change('conditionalAnalysis',e.target.checked)}/><span>{t('Compare conditional sell-or-hold scenarios even when calibrated intervals are unavailable')}</span></label>
                <label className="checkbox-field"><input type="checkbox" checked={draft.compareDates} onChange={e => change('compareDates',e.target.checked)}/><span>{t('Compare all saved forecast dates plus my selected date, within my holding limit')}</span></label>
                <label className="field" htmlFor="advisor-scenario-price">
                  <span>{t('Optional future buyer price assumption')}</span>
                  <input id="advisor-scenario-price" inputMode="decimal" value={draft.scenarioPrice || ''} onChange={e => change('scenarioPrice', e.target.value)} />
                  <small>{t(Number(draft.days) > 7 ? 'For longer dates, provide your future buyer quote or explicitly choose a flat-reference scenario.' : 'Leave blank to request the saved forecast. Entering a price creates scenario-only analysis.')}</small>
                  {errors.scenarioPrice && <small role="alert">{t(errors.scenarioPrice)}</small>}
                </label>
                {draft.conditionalAnalysis ? <>
                  <Notice tone="amber">{t('These percentages are your sensitivity assumptions, not model confidence bands. Review them using the evidence below.')}</Notice>
                  {field('downsidePercent','Lower-scenario price drop','%')}
                  {field('adversePercent','Adverse-scenario price drop','%')}
                  {field('upsidePercent','Upper-scenario price rise','%')}
                  {field('realization','Future buyer price / mandi forecast','×','Use your historical buyer realization. A factor of 1 assumes no discount to the mandi forecast.')}
                  {Number(draft.days) > 7 && <label className="field"><span>{t('Longer holding-date price basis')}</span><select value={draft.longReference} onChange={e => change('longReference',e.target.value as AdvisorValues['longReference'])}><option value="saved_forecast">{t('Use the saved forecast for this exact date; fail safely if unavailable')}</option><option value="require_user_price">{t('Require my future buyer quote')}</option><option value="flat_reference">{t('Use a flat dated price reference, not a trained forecast')}</option></select><small>{t('Extended forecasts are research only. Beyond saved evidence, enter your own scenario. Weather coverage is limited to its source dates.')}</small></label>}
                  <label className="field"><span>{t('Storage exposure to rain')}</span><select value={draft.storageExposure} onChange={e => change('storageExposure',e.target.value as AdvisorValues['storageExposure'])}><option value="unknown">{t('Not verified')}</option><option value="protected">{t('Protected storage')}</option><option value="outdoor">{t('Outdoor or exposed storage')}</option></select></label>
                  {draft.storageExposure === 'outdoor' && <><label className="checkbox-field"><input type="checkbox" checked={draft.rainStop} onChange={e => change('rainStop',e.target.checked)}/><span>{t('Block holding if the rain threshold is reached or weather coverage is missing')}</span></label>{draft.rainStop && field('rainThreshold','Maximum allowed daily rain','mm','Your storage constraint; not an automatic crop-loss estimate')}</>}
                </> : field('adverse', 'Adverse gross future price', 'INR / qtl', 'User-entered downside assumption')}
              </div>
            )}

            <details className="more-details">
              <summary>
                <strong>{t(`More details · Transport, commission & mandi charges (${activeCrop.market} defaults)`)}</strong>
              </summary>
              <p className="muted small" style={{ marginTop: '8px' }}>
                {t('Fixed charges apply per nonzero sale. The same entered quotation is used for each future trip; adjust it to your actual expected terms.')}
              </p>
              <div className="form-grid">
                {field('transportFixed', 'Fixed transport per trip', 'INR')}
                {field('transportVariable', 'Transport per sold quintal', 'INR / qtl')}
                {field('commission', 'Commission', '% of gross')}
                {field('marketFee', 'Market fee', '% of gross')}
                {field('handling', 'Handling per sold quintal', 'INR / qtl')}
                {field('fixedTransaction', 'Other fixed sale charge', 'INR')}
                {field('increment', 'Plan quantity increment', 'qtl')}
                {field('minimumLot', 'Minimum marketable lot', 'qtl')}
                {field('step', 'Market sale rounding step', 'qtl')}
              </div>

            </details>

            {(
              <div style={{ marginTop: '18px' }}>
                <p className="eyebrow">{t('RISK TOLERANCE')}</p>
                <fieldset className="risk-options">
                  <legend className="sr-only">{t('Risk tolerance')}</legend>
                  {([
                    { value: 'conservative', title: 'Conservative', text: 'Prioritize the adverse outcome' },
                    { value: 'balanced', title: 'Balanced', text: 'Equal central and adverse weight' },
                    { value: 'aggressive', title: 'Aggressive', text: 'More central weight; downside still shown' },
                  ] as const).map(r => (
                    <label className={draft.risk === r.value ? 'selected' : ''} key={r.value}>
                      <input
                        type="radio"
                        name="risk"
                        value={r.value}
                        checked={draft.risk === r.value}
                        onChange={() => change('risk', r.value)}
                      />
                      <strong>{t(r.title)}</strong>
                      <span>{t(r.text)}</span>
                    </label>
                  ))}
                </fieldset>
              </div>
            )}

            <label className="field" htmlFor="advisor-notes" style={{ marginTop: '16px' }}>
              <span>{t('Where did your quote and cost assumptions come from?')}</span>
              <textarea
                id="advisor-notes"
                value={draft.notes}
                onChange={e => change('notes', e.target.value)}
                placeholder="For example: today’s buyer quotation and transport quote; no personal details needed"
                aria-invalid={Boolean(errors.notes)}
              />
              <small className="field-error">{errors.notes ? t(errors.notes) : ''}</small>
            </label>

            <label className="checkbox-field" style={{ marginTop: '14px' }}>
              <input
                id="advisor-acknowledged-details"
                type="checkbox"
                checked={draft.acknowledged}
                onChange={e => change('acknowledged', e.target.checked)}
              />
              <span>{t('I understand these are my inputs and assumptions, not guaranteed future prices.')}</span>
            </label>
            {errors.acknowledged && <p className="field-error" role="alert">{t(errors.acknowledged)}</p>}

            {Object.values(errors).filter(Boolean).length > 0 && (
              <p role="alert" className="field-error">
                {t('Please correct the highlighted inputs before continuing.')}
              </p>
            )}

            <button
              className="button button-primary full-width form-submit"
              hidden={!explorer}
              type="submit"
              disabled={busy}
            >
              {busy ? t('Calculating with the backend…') : explorer ? t('Recalculate with backend') : t('Calculate my sale plan')}
              {!busy && <ArrowRight size={18} />}
            </button>
          </Card>

          {(explorer || step === 3 || step === 4) && <MarketContextPanel scope={scope} days={Math.max(7,Number(draft.days) || 7)} collapsed/>}

          {/* STEP 4: Review & Calculate */}
          {!explorer && (
            <Card className="journey-review" hidden={step !== 4}>
              <p className="eyebrow">{t('STEP 5')}</p>
              <h2>{t('Review your assumptions')}</h2>

              <dl className="review-grid">
                <div>
                  <dt>{t('Harvest quantity')}</dt>
                  <dd>{draft.quantity || '0'} {t('qtl')}</dd>
                </div>
                <div>
                  <dt>{t('Applied buyer price assumption')}</dt>
                  <dd>₹{appliedPrice} / {t('qtl')}</dd>
                </div>
                <div>
                  <dt>{t('Immediate net cash needed')}</dt>
                  <dd>₹{draft.cash || '0'}</dd>
                </div>
                <div>
                  <dt>{t('Available storage capacity')}</dt>
                  <dd>{Number(draft.capacity) > 0 ? `${draft.capacity} ${t('qtl')} (${draft.days} ${t('days')})` : t('No holding capacity')}</dd>
                </div>
              </dl>

              {Number(draft.capacity)>0 && <Notice>{t('Compared holding dates')}: {holdingDates(effectiveDraft,scope.commodity,availableHorizons).join(', ')} {t('days')} · {t('Risk tolerance')}: {t(draft.risk)} · {t('Lower / adverse drop / upper rise')}: {draft.downsidePercent}% / {draft.adversePercent}% / {draft.upsidePercent}% · {t('Future buyer price / mandi forecast')}: {draft.realization}×</Notice>}

              <div className="review-cost-summary">
                <h4>{t('User assumptions: verify costs and storage conditions')}</h4>
                <div className="cost-tags">
                  <span>{t('Commission')}: {effectiveDraft.commission}%</span>
                  <span>{t('Market fee')}: {effectiveDraft.marketFee}%</span>
                  <span>{t('Transport')}: ₹{effectiveDraft.transportFixed} + ₹{effectiveDraft.transportVariable}/qtl</span>
                  <span>{t('Handling')}: ₹{effectiveDraft.handling}/qtl</span>
                  {Number(effectiveDraft.capacity) > 0 && (
                    <span>{t('Assumed loss')}: {effectiveDraft.loss}%/day</span>
                  )}
                </div>
              </div>

              <Notice>{t('Future prices are uncertain. You make the final decision.')}</Notice>
              <p className="small muted">
                {t('Your notes are shown as entered. Financial values are calculated only by the backend.')}
              </p>

              <label className="checkbox-field" style={{ margin: '14px 0' }}>
                <input
                  id="advisor-acknowledged"
                  type="checkbox"
                  checked={draft.acknowledged}
                  onChange={e => change('acknowledged', e.target.checked)}
                />
                <span>{t('I understand these are my inputs and assumptions, not guaranteed future prices.')}</span>
              </label>
              {errors.acknowledged && <p className="field-error" role="alert">{t(errors.acknowledged)}</p>}

              <button
                className="button button-primary full-width"
                disabled={busy}
                type="submit"
              >
                {busy ? t('Calculating with the backend…') : t('Calculate my sale plan')}
                <ArrowRight size={17} />
              </button>

              {(!draft.quantity || Number(draft.quantity) <= 0) && (
                <p className="field-hint" style={{ textAlign: 'center', marginTop: '8px' }}>
                  {t('Enter your harvest quantity to run calculation.')}
                </p>
              )}

              {Object.keys(errors).length > 0 && (
                <p role="alert" className="field-error">
                  {t('Please correct the highlighted inputs before continuing.')}
                </p>
              )}
            </Card>
          )}

          {Boolean(error) && <ErrorState error={error} />}

          {!explorer && (
            <div className="journey-actions">
              <button
                className="button button-secondary"
                type="button"
                disabled={step === 0}
                onClick={() => setStep(Math.max(0, step - 1))}
              >
                {t('Back')}
              </button>
              {step < 4 && (
                <button className="button button-primary" type="button" onClick={advance}>
                  {t('Continue')}
                  <ArrowRight size={16} />
                </button>
              )}
            </div>
          )}
        </form>

        <aside className="advisor-side">
          <Card>
            <span className="icon-tile">{explorer ? <SlidersHorizontal /> : <Calculator />}</span>
            <h2>{t('Net cash comes first.')}</h2>
            <p>{t('A higher future price does not always mean a better outcome.')}</p>
            <div className="definition-list">
              <div>
                <strong>{t('First, meet today’s cash need')}</strong>
                <p>{t('Only net proceeds after costs can pay today’s bills.')}</p>
              </div>
              <div>
                <strong>{t('Then, respect physical limits')}</strong>
                <p>{t('Storage, deterioration, market lots and crop holding limits remain mandatory.')}</p>
              </div>
              <div>
                <strong>{t('Finally, compare the downside')}</strong>
                <p>{t('Every plan is compared against selling all produce now.')}</p>
              </div>
            </div>
            <Link to="/transparency" className="text-button">
              {t('Read the evidence policy')}<ArrowRight size={16} />
            </Link>
          </Card>

          {explorer && result && (
            <Card>
              {dirty ? (
                <Notice>{t('Inputs changed. Recalculate before treating any prior result as current.')}</Notice>
              ) : (
                <>
                  <Badge tone="green">{t('Backend result')}</Badge>
                  <ResultSummary result={result} />
                  <Link to="/results" className="button button-secondary">
                    {t('Open full comparison')}
                  </Link>
                </>
              )}
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
