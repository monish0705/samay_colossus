import { localize, t, warningText } from './i18n';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, CalendarDays, Coins, Leaf, ShieldCheck, Sprout, TrendingUp } from 'lucide-react';
import { api, ApiError, CROP_SCOPES, type Prediction, type Scope } from './api';
import { useApp } from './state';
import { ActionLink, Badge, Card, Empty, ErrorState, Loading, Notice, PageHeading, Stat, dateLabel, inr, useResource } from './ui';
import { PriceChart, EvaluationChart } from './Charts';
import { MarketContextPanel, PredictionAttributionCard } from './DecisionPanel';

export function Dashboard() {
  const { scope, setScope, catalog } = useApp();
  const latest = useResource(signal => api.latest(scope, signal), JSON.stringify(scope));
  const history = useResource(signal => api.history(scope, {}, 0, signal), JSON.stringify(scope));
  const obs = latest.data?.observation;
  const noObservation = latest.error instanceof ApiError && latest.error.status === 404;

  return localize(
    <>
      <PageHeading eyebrow={t('YOUR MARKET, IN PERSPECTIVE')} title={t('A better day to decide.')}>
        {t('Make room for certainty where it matters. Know your market, your costs, and your next step.')}
      </PageHeading>

      {/* Commodity Switcher Bar */}
      <div className="commodity-tabs" role="tablist" aria-label="Commodity selector">
        {Object.values(CROP_SCOPES).map(c => (
          <button
            key={c.id}
            type="button"
            className={`commodity-tab ${scope.commodity === c.commodity ? 'is-active' : ''}`}
            onClick={() => setScope({ market: c.market, commodity: c.commodity, variety: c.variety, grade: c.grade })}
          >
            <span>{c.icon}</span>
            <span>{t(c.commodity)} · {t(c.market)}</span>
          </button>
        ))}
      </div>

      <div className="hero-grid">
        <section className="hero">
          <div className="hero-copy">
            <Badge tone="green"><Leaf size={13} />{t('Built around your harvest')}</Badge>
            <h2>{t('Your harvest.')}<br />{t('Your timing.')}</h2>
            <p>{t('Meet today’s cash needs.')}<br />{t('Understand the trade-offs of holding.')}</p>
            <Link className="button button-dark" to="/advisor">
              {t('Plan my sale')}<ArrowRight size={17} />
            </Link>
            <span className="hero-caption">{t('Clear assumptions. Transparent calculations.')}</span>
          </div>
          <div className="field-art" aria-hidden="true">
            <div className="sun" />
            <div className="field-hill hill-back" />
            <div className="field-hill hill-front" />
            <div className="field-lines" />
            <Sprout className="plant plant-one" />
            <Sprout className="plant plant-two" />
            <Leaf className="plant plant-three" />
          </div>
        </section>

        <Card className="readiness">
          <span className="icon-tile"><ShieldCheck size={24} /></span>
          <h3>{t('Trust starts with the source.')}</h3>
          <p>{t('Every observation carries its report date. Every forecast carries its limitations.')}</p>
          <div className="readiness-row">
            <span>{t('Official observations')}</span>
            <strong>{catalog.data?.data.official_observations ?? '—'}</strong>
          </div>
          <div className="readiness-row">
            <span>{t('Model deployment')}</span>
            <Badge tone={catalog.data?.models.models.some(m => m.model_version) ? 'green' : 'amber'}>
              {catalog.data?.models.models.some(m => m.model_version) ? t('Artifacts available') : t('Not available')}
            </Badge>
          </div>
          <ActionLink to="/transparency">{t('See what powers SAMAY')}</ActionLink>
        </Card>
      </div>

      <div className="stats-grid">
        <Stat
          label={t('Latest observed modal price')}
          value={obs ? inr(obs.modal_price_inr_per_quintal) : '—'}
          note={obs ? `${t('INR/quintal')} · ${dateLabel(obs.report_date)}` : t('Awaiting official observations')}
          icon={<Coins size={18} />}
        />
        <Stat
          label={t('Market reporting')}
          value={obs ? (latest.data?.stale ? t('Stale') : t('Recent')) : t('No report')}
          note={obs ? `${latest.data?.age_calendar_days} ${t('calendar days since report')}` : t('No price is substituted from demo data')}
          icon={<CalendarDays size={18} />}
        />
        <Stat
          label={t('Saved forecast artifacts')}
          value={((catalog.data?.models.models.filter(m => m.model_version).length || 0) + (catalog.data?.models.research_models?.length || 0)) || t('Not ready')}
          note={t('Research artifacts are not validated live models; freshness is checked per request.')}
          icon={<TrendingUp size={18} />}
        />
      </div>

      <div className="content-grid">
        <Card>
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t('OBSERVED, NOT PREDICTED')}</p>
              <h2>{t('How your market is moving')}</h2>
            </div>
            <ActionLink to="/insights">{t('Explore history')}</ActionLink>
          </div>
          {history.loading ? (
            <Loading />
          ) : history.error ? (
            <ErrorState error={history.error} retry={history.retry} />
          ) : (
            <PriceChart
              points={(history.data?.items || []).map(p => ({
                date: p.report_date,
                value: Number(p.modal_price_inr_per_quintal),
              }))}
            />
          )}
          <div className="source-strip">
            {scope.market} · {scope.commodity} · {scope.variety} / {scope.grade}
            <span>{t('Official records only')}</span>
          </div>
        </Card>

        <Card>
          <p className="eyebrow">{t('ONE STEP AT A TIME')}</p>
          <h2>{t('Your next decision')}</h2>
          <div className="steps-list">
            <Link to="/insights">
              <span>01</span>
              <div>
                <strong>{t('Read the market')}</strong>
                <p>{t('History, reporting gaps and sources')}</p>
              </div>
              <ArrowUpRight size={18} />
            </Link>
            <Link to="/forecast">
              <span>02</span>
              <div>
                <strong>{t('Understand the range')}</strong>
                <p>{t('Forecasts with empirical uncertainty')}</p>
              </div>
              <ArrowUpRight size={18} />
            </Link>
            <Link to="/advisor">
              <span>03</span>
              <div>
                <strong>{t('Make cash needs count')}</strong>
                <p>{t('Compare net proceeds, not gross price')}</p>
              </div>
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <Notice tone="neutral">
            {t('A mandi modal price is a wholesale statistic. Your buyer’s quote can be different.')}
          </Notice>
        </Card>
      </div>

      {latest.loading ? null : latest.error && !noObservation ? (
        <ErrorState error={latest.error} retry={latest.retry} />
      ) : obs ? (
        <p className="source-note">
          {t('Source:')} {obs.source} · {t('fetched')} {dateLabel(obs.fetched_at)}{' '}
          {obs.source_url && (
            <a href={obs.source_url} target="_blank" rel="noreferrer">
              {t('View source ↗')}
            </a>
          )}
        </p>
      ) : (
        <Notice>
          {t('No verified price observation is available for this series. You can still compare a sale using your own buyer quote.')}
        </Notice>
      )}
    </>
  );
}

export function Insights() {
  const { scope, setScope } = useApp();
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [offset, setOffset] = useState(0);

  const invalidDates = start && end && start > end;
  const history = useResource(
    signal =>
      invalidDates
        ? Promise.reject(new Error('Start date must be before the end date.'))
        : api.history(scope, { start_date: start || undefined, end_date: end || undefined }, offset, signal),
    JSON.stringify({ scope, start, end, offset })
  );

  const items = history.data?.items || [];
  const values = items.map(p => Number(p.modal_price_inr_per_quintal));
  const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

  return localize(
    <>
      <PageHeading
        eyebrow={t('MARKET INSIGHTS')}
        title={t('See the story behind the price.')}
      >
        {t('Observed wholesale prices for one consistent market, variety and grade. Missing dates are never filled.')}
      </PageHeading>

      {/* Commodity Switcher Bar */}
      <div className="commodity-tabs" role="tablist" aria-label="Commodity selector">
        {Object.values(CROP_SCOPES).map(c => (
          <button
            key={c.id}
            type="button"
            className={`commodity-tab ${scope.commodity === c.commodity ? 'is-active' : ''}`}
            onClick={() => {
              setScope({ market: c.market, commodity: c.commodity, variety: c.variety, grade: c.grade });
              setOffset(0);
            }}
          >
            <span>{c.icon}</span>
            <span>{t(c.commodity)} · {t(c.market)}</span>
          </button>
        ))}
      </div>

      <Card>
        <div className="section-heading">
          <div>
            <Badge tone="green">{t('Observed prices')}</Badge>
            <h2>{scope.commodity} at {scope.market}</h2>
          </div>
          <div className="date-controls">
            <label>
              {t('From')}
              <input type="date" value={start} onChange={e => { setStart(e.target.value); setOffset(0); }} />
            </label>
            <label>
              {t('To')}
              <input type="date" value={end} onChange={e => { setEnd(e.target.value); setOffset(0); }} />
            </label>
          </div>
        </div>
        {history.loading ? (
          <Loading />
        ) : history.error ? (
          <ErrorState error={history.error} retry={history.retry} />
        ) : (
          <PriceChart points={items.map(p => ({ date: p.report_date, value: Number(p.modal_price_inr_per_quintal) }))} />
        )}
      </Card>

      <div className="stats-grid">
        <Stat
          label={t('Observations on this page')}
          value={items.length}
          note={t('At most 1,000 per page; reporting is not guaranteed daily')}
        />
        <Stat
          label={t('Mean observed modal price')}
          value={inr(mean)}
          note={t('Descriptive average, not a forecast · INR/quintal')}
        />
        <Stat
          label={t('Latest report on this page')}
          value={dateLabel(items.at(-1)?.report_date)}
          note={`${scope.variety} · ${scope.grade}`}
        />
      </div>

      {/* Actual dated external evidence; no invented seasonal price claims. */}
      <MarketContextPanel scope={scope} days={7}/>

      <Card>
        <div className="section-heading">
          <h2>{t('Source records')}</h2>
          <Badge>INR / quintal</Badge>
        </div>
        {!items.length ? (
          <Empty title={t('No history for this selection')}>
            {t('Try another date range or import authentic government observations for the selected variety.')}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <caption className="sr-only">{t('Observed market records with source dates')}</caption>
              <thead>
                <tr>
                  <th>{t('Report date')}</th>
                  <th>{t('Modal')}</th>
                  <th>{t('Observed minimum')}</th>
                  <th>{t('Observed maximum')}</th>
                  <th>{t('Source')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map(row => (
                  <tr key={row.id}>
                    <td>{dateLabel(row.report_date)}</td>
                    <td><strong>{inr(row.modal_price_inr_per_quintal)}</strong></td>
                    <td>{inr(row.min_price_inr_per_quintal)}</td>
                    <td>{inr(row.max_price_inr_per_quintal)}</td>
                    <td>
                      {row.source_url ? (
                        <a href={row.source_url} target="_blank" rel="noreferrer">
                          {row.source} ↗
                        </a>
                      ) : (
                        row.source
                      )}
                      <small>{t('Fetched')} {dateLabel(row.fetched_at)} · {row.data_kind}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <button
            className="button button-secondary"
            disabled={offset === 0 || history.loading}
            onClick={() => setOffset(Math.max(0, offset - 1000))}
          >
            {t('Previous')}
          </button>
          <span>{t('Page')} {offset / 1000 + 1}</span>
          <button
            className="button button-secondary"
            disabled={history.data?.next_offset == null || history.loading}
            onClick={() => setOffset(history.data!.next_offset!)}
          >
            {t('Next')}
          </button>
        </div>
      </Card>

      <Notice tone="neutral">
        {t('Observed minimum and maximum prices are not prediction intervals. Calendar gaps may reflect unreported market activity.')}
      </Notice>
    </>
  );
}

export function HistoricalEvaluationCard({ scope, horizon }: { scope: Scope; horizon: number }) {
  const evaluation = useResource(signal => api.evaluation(scope,horizon,signal), JSON.stringify({scope,horizon}));
  const data = evaluation.data;
  return <Card>
    <h2>{t('Historical evaluation: actual versus predicted')}</h2>
    <Notice>{t('These are frozen historical test predictions, not a current forecast or guaranteed selling prices.')}</Notice>
    {evaluation.loading ? <Loading/> : evaluation.error ? <Notice>{t('No historical evaluation is available for this exact series.')}</Notice> : data ? <>
      <p>{data.scope.market} · {data.scope.commodity} · {data.scope.variety} / {data.scope.grade}</p>
      <Badge tone="amber">{t(data.source_kind === 'verified' ? 'Official OGD history with verified secondary backfill' : data.source_kind === 'secondary' ? 'Secondary mirror: India Data Portal' : 'Official government export')}</Badge>
      <p>{t('Final test')}: {dateLabel(data.test_start)} – {dateLabel(data.test_end)} · {data.final_n} {t('observed targets')} · {data.selected_model}</p>
      {data.metrics ? <div className="stats-grid three">
        <Stat label={t('MAE / quintal')} value={inr(data.metrics.mae_inr_per_quintal)} note={t('Frozen final test; lower error is better')}/>
        <Stat label={t('Naive MAE / quintal')} value={inr(data.naive_metrics?.mae_inr_per_quintal)} note={t('Identical target dates')}/>
        <Stat label={t('WAPE')} value={data.metrics.wape_pct == null ? '—' : `${Number(data.metrics.wape_pct).toFixed(2)}%`} note={t('Percentage error, not accuracy')}/>
      </div> : <Notice tone="amber">{t('Insufficient final test observations: no reliable final accuracy metric is reported.')}</Notice>}
      {data.scope.grade === 'unspecified' && <Notice>{t('The older source does not report grade. It has not been inferred or merged with graded records.')}</Notice>}
      <EvaluationChart points={data.points}/>
      {data.points.length > 0 && <details><summary>{t('Inspect dated predictions and actual observations')}</summary><div className="table-scroll"><table>
        <thead><tr><th>{t('Decision date')}</th><th>{t('Target date')}</th><th>{t('Actual / quintal')}</th><th>{t('Predicted / quintal')}</th><th>{t('Absolute error / quintal')}</th></tr></thead>
        <tbody>{data.points.slice(-20).map(p => <tr key={p.target_date}><td>{dateLabel(p.origin_date)}</td><td>{dateLabel(p.target_date)}</td><td>{inr(p.actual_inr_per_quintal)}</td><td>{inr(p.prediction_inr_per_quintal)}</td><td>{inr(p.absolute_error_inr_per_quintal)}</td></tr>)}</tbody>
      </table></div></details>}
    </> : null}
  </Card>;
}

export function Forecast() {
  const { scope, setScope, catalog, predictionHistory, rememberPrediction } = useApp();
  const [horizon, setHorizon] = useState<number>(3);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState<unknown>(null);
  const coverage = useResource(signal => api.horizons(scope,horizon,signal),JSON.stringify({scope,horizon}));
  const crop = CROP_SCOPES[scope.commodity] || CROP_SCOPES.Tomato;

  const supported = catalog.data?.models.models
    .filter(m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade && m.model_version)
    .map(m => m.horizon) || [];
  const researchSupported = (catalog.data?.models.research_models || []).filter(m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade).map(m => m.horizon).filter(h => !supported.includes(h));
  for (const h of researchSupported) if (!supported.includes(h)) supported.push(h);
  for (const h of coverage.data?.saved_horizons || []) if (!supported.includes(h)) supported.push(h);

  const request = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const p = await api.predict(scope, horizon);
      setResult(p);
      rememberPrediction(p);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const relevant = result && result.market === scope.market && result.commodity === scope.commodity && result.variety === scope.variety && result.grade === scope.grade && result.horizon_calendar_days === horizon ? result : null;
  const evidence = catalog.data?.models.research_models?.find(m=>m.market===scope.market && m.commodity===scope.commodity && m.variety===scope.variety && m.grade===scope.grade && m.horizon===relevant?.horizon_calendar_days);
  const evidenceMetrics = evidence?.validation_metrics || evidence?.retrospective_benchmark_metrics;

  return localize(
    <>
      <PageHeading eyebrow={t('PRICE FORECAST')} title={t('A view ahead, with the uncertainty visible.')}>
        {t('Horizon-specific predictions from saved models. Empirical bands describe mandi modal prices, not your guaranteed selling price.')}
      </PageHeading>

      {/* Commodity Switcher Bar */}
      <div className="commodity-tabs" role="tablist" aria-label="Commodity selector">
        {Object.values(CROP_SCOPES).map(c => (
          <button
            key={c.id}
            type="button"
            className={`commodity-tab ${scope.commodity === c.commodity ? 'is-active' : ''}`}
            onClick={() => {
              setScope({ market: c.market, commodity: c.commodity, variety: c.variety, grade: c.grade });
              setResult(null);
              setError(null);
              setHorizon(3);
            }}
          >
            <span>{c.icon}</span>
            <span>{t(c.commodity)} · {t(c.market)}</span>
          </button>
        ))}
      </div>

      <div className="content-grid">
        <Card>
          <div className="section-heading">
            <h2>{t('Choose a forecast horizon')}</h2>
            <Badge>{t('Future prediction')}</Badge>
          </div>
          <p className="small muted">{t('Forecast series')}: {t(scope.market)} · {t('Variety')}: {scope.variety} · {t('Grade')}: {scope.grade}</p>
          {scope.variety === 'other' && <Notice tone="amber">{t('The source reports this variety as Other. Confirm that it matches your produce before using the forecast.')}</Notice>}
          <div className="horizon-options">
            {[...new Set([1,3,7,14,30,60,90,180,365,730,...crop.holdingOptions.map(Number)])].filter(day => day<=crop.maxDays).sort((a,b)=>a-b).map(day => (
              <button
                key={day}
                className={`horizon ${horizon === day ? 'selected' : ''}`}
                disabled={!supported.includes(day)}
                onClick={() => { setHorizon(day); setResult(null); setError(null); }}
              >
                <strong>{day} {t(day > 1 ? 'days' : 'day')}</strong>
                <span>{supported.includes(day) ? t(researchSupported.includes(day) ? 'Research only · limited evidence' : 'Saved artifact available') : t('Not deployed')}</span>
              </button>
            ))}
          </div>
          <div className="field"><label htmlFor="forecast-horizon">{t('Exact forecast horizon (calendar days)')}</label><input id="forecast-horizon" aria-describedby="forecast-horizon-hint" type="number" min="1" max={crop.maxDays} step="1" value={horizon} onChange={e=>{ const value=Number(e.target.value); if(Number.isInteger(value) && value>=1 && value<=crop.maxDays){setHorizon(value);setResult(null);setError(null);} }}/><small id="forecast-horizon-hint">{t('Each date needs its own saved evidence. Longer dates are not interpolated from a short forecast.')}</small></div>
          <p className="small">{t('Saved horizons')}: {supported.length} · {t('Maximum saved horizon')}: {supported.length ? Math.max(...supported) : '—'} {t('days')}</p>
          {!supported.includes(horizon) && coverage.data && <Notice tone="amber">{t('Insufficient evidence for this date. No future price will be invented.')}{coverage.data.reasons.length ? ` ${coverage.data.reasons.map(reason=>warningText(reason)).join(' · ')}` : ''}</Notice>}
          <Notice>{t('Extended horizons have development-only evidence or a predeclared persistence baseline. These are not newly validated final-test forecasts.')}</Notice>

          {!supported.length && (
            <Notice>
              {t('No operational horizon is deployed for this series. An availability check can confirm the backend status; it does not produce a demo forecast.')}
            </Notice>
          )}

          <button className="button button-primary" disabled={busy} onClick={request}>
            {busy ? t('Checking the saved service…') : supported.includes(horizon) ? t('Get forecast') : t('Check service availability')}
            <ArrowRight size={16} />
          </button>

          {busy && <Loading label={t('Checking historical inputs and reliability…')} />}

          {error ? (
            <ErrorState error={error} retry={request} />
          ) : relevant ? (
            <div className="forecast-output">
              <Badge tone={relevant.reliability_status === 'validated' ? 'green' : 'amber'}>
                {t(relevant.reliability_status)}
              </Badge>
              <span className="forecast-price">
                {inr(relevant.prediction_inr_per_quintal)}
                <small>/ {t('quintal')}</small>
              </span>
              <p>
                {t('Target')} {dateLabel(relevant.target_date)} · {t('latest observation')} {dateLabel(relevant.latest_report_date)}
              </p>
              {relevant.intervals?.length ? (
                relevant.intervals.map((i, index) => (
                  <div className="interval-row" key={index}>
                    <span>{Number(i.nominal_level) * 100}% {t('nominal empirical band')}</span>
                    <strong>{inr(i.lower_inr_per_quintal)} – {inr(i.upper_inr_per_quintal)}</strong>
                  </div>
                ))
              ) : (
                <Notice>{t('No sufficiently calibrated interval is available.')}</Notice>
              )}
              <p className="small muted">
                {t('Model')} {relevant.model_version} · {t('request')} {relevant.request_id}
              </p>
              {evidence?.evidence_status && <Notice><strong>{t(evidence.evidence_status==='baseline_only' ? 'Predeclared last-price baseline; not trained ML' : 'Development-selected model; no new final test')}</strong><p>{t('Model')}: {evidence.model_name}</p>{evidenceMetrics && <p>{t(evidence.validation_metrics ? 'Selection validation MAE' : 'Retrospective baseline MAE')}: {inr(evidenceMetrics.mae_inr_per_quintal)} / {t('quintal')} · n={evidenceMetrics.n} · {t('Not final-test accuracy')}</p>}</Notice>}
              {relevant.flags.length > 0 && (
                <Notice>{relevant.flags.map(w => warningText(w)).join(' · ')}</Notice>
              )}
              {relevant.attribution && (
                <PredictionAttributionCard
                  attribution={relevant.attribution}
                  commodity={scope.commodity}
                  horizon={relevant.horizon_calendar_days}
                />
              )}
            </div>
          ) : (
            <Empty title={t('Evidence before a number')}>
              {t('A forecast appears here only after a successful backend response. No model performance is assumed.')}
            </Empty>
          )}
        </Card>

        <Card>
          <span className="icon-tile"><ShieldCheck /></span>
          <h2>{t('Read a range responsibly')}</h2>
          <div className="definition-list">
            <div>
              <strong>{t('Observed')}</strong>
              <p>{t('A reported wholesale market statistic from a past date.')}</p>
            </div>
            <div>
              <strong>{t('Predicted')}</strong>
              <p>{t('An uncertain future modal price for a specific calendar date.')}</p>
            </div>
            <div>
              <strong>{t('Your realization')}</strong>
              <p>{t('Your grade, quality, fees, transport and buyer terms affect the price you receive.')}</p>
            </div>
          </div>
          <ActionLink to="/transparency">{t('Inspect model evidence')}</ActionLink>
        </Card>
      </div>

      <HistoricalEvaluationCard scope={scope} horizon={horizon}/>
      <Card>
        <h2>{t('Prediction history')}</h2>
        <p className="muted small">
          {t('Successful requests in this browser session only. Cleared when the app reloads.')}
        </p>
        {predictionHistory.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('Series')}</th>
                  <th>{t('Target date')}</th>
                  <th>{t('Horizon')}</th>
                  <th>{t('Prediction / qtl')}</th>
                  <th>{t('Reliability')}</th>
                </tr>
              </thead>
              <tbody>
                {predictionHistory.map(p => (
                  <tr key={p.request_id}>
                    <td>{p.commodity} · {p.variety}</td>
                    <td>{dateLabel(p.target_date)}</td>
                    <td>{p.horizon_calendar_days} {t('days')}</td>
                    <td>{inr(p.prediction_inr_per_quintal)}</td>
                    <td>{p.reliability_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title={t('No successful forecasts yet')}>
            {t('Unavailable requests are never stored as successful predictions.')}
          </Empty>
        )}
      </Card>
    </>
  );
}

export function Transparency() {
  const { catalog } = useApp();
  const data = catalog.data?.data;
  const models = catalog.data?.models.models || [];

  return localize(
    <>
      <PageHeading
        eyebrow={t('DATA & MODEL TRANSPARENCY')}
        title={t('Every number should earn your trust.')}
      >
        {t('What is available, what is measured, and where the evidence stops.')}
      </PageHeading>

      {catalog.loading ? (
        <Loading />
      ) : catalog.error ? (
        <ErrorState error={catalog.error} retry={catalog.retry} />
      ) : (
        <>
          <div className="stats-grid">
            <Stat
              label={t('Official observations')}
              value={data?.official_observations ?? '—'}
              note={t('Operator-attested government provenance')}
            />
            <Stat label={t('Secondary mirror observations')} value={data?.secondary_observations ?? 0} note={t('India Data Portal / ISB; upstream AGMARKNET; ODC Attribution')}/>
            <Stat
              label={t('Latest official report')}
              value={dateLabel(data?.latest_official_report_date)}
              note={`${t('Fetched')} ${dateLabel(data?.latest_official_fetched_at)}`}
            />
            <Stat
              label={t('Excluded development records')}
              value={(data?.fixture_observations || 0) + (data?.demo_observations || 0)}
              note={t('Never substituted into default market prices')}
            />
          </div>

          <div className="content-grid">
            <Card>
              <div className="section-heading">
                <h2>{t('Deployed model evidence')}</h2>
                <Badge>{catalog.data?.models.status.replaceAll('_', ' ')}</Badge>
              </div>
              {models.length ? (
                models.map(m => (
                  <div className="model-item" key={`${m.market}-${m.variety}-${m.horizon}`}>
                    <strong>{m.horizon}-day · {m.commodity} / {m.variety} / {m.grade}</strong>
                    <p>{m.model_version || t('No saved champion')}</p>
                    <p className="muted small">
                      {t('Training cutoff')} {dateLabel(m.trained_before)} · {t('empirical evidence')}{' '}
                      {m.reliability_evidence_configured ? t('configured; checked per request') : t('not configured')}
                    </p>
                    {m.final_holdout_metrics ? (
                      <div className="metrics-row">
                        <span>{t('Final held-out MAE')}<strong>{inr(m.final_holdout_metrics.mae_inr_per_quintal)}</strong></span>
                        <span>{t('Observed test examples')}<strong>{m.final_holdout_metrics.n}</strong></span>
                      </div>
                    ) : (
                      <Notice tone="neutral">{t('No actual final held-out metrics supplied for this artifact.')}</Notice>
                    )}
                    {m.validation_metrics && (
                      <p className="small">
                        {t('Selection validation MAE:')} {inr(m.validation_metrics.mae_inr_per_quintal)} / qtl.{' '}
                        {t('This period was used for model selection, not an unbiased final test.')}
                      </p>
                    )}
                    <small className="hash">{t('Source fingerprint:')} {m.dataset_fingerprint || 'unavailable'}</small>
                  </div>
                ))
              ) : (
                <Empty title={t('No saved model is deployed')}>
                  {t('No accuracy percentage, champion or final evaluation is inferred from a missing artifact.')}
                </Empty>
              )}
            </Card>

            <Card>
              <h2>{t('Limits worth knowing')}</h2>
              <div className="definition-list">
                <div>
                  <strong>{t('Provenance is disclosed')}</strong>
                  <p>{data?.note}</p>
                </div>
                <div>
                  <strong>{t('Calendar gaps remain gaps')}</strong>
                  <p>{t('No artificial daily prices or target observations are created.')}</p>
                </div>
                <div>
                  <strong>{t('Intervals are empirical')}</strong>
                  <p>{t('Residuals can be dependent and market regimes can change. Future coverage is not guaranteed.')}</p>
                </div>
                <div>
                  <strong>{t('Holding has physical risk')}</strong>
                  <p>{t('Loss rates and crop holding limits must match real local conditions.')}</p>
                </div>
              </div>
            </Card>
          </div>
        </>
      )}

      {(catalog.data?.models.research_studies || []).map(study => (
        <Card key={study.version}>
          <div className="section-heading">
            <h2>{t('Retrospective research results')}</h2>
            <Badge tone="amber">{t('Research only · not deployed')}</Badge>
          </div>
          <p>{study.commodity} / {study.variety} / {study.grade}</p>
          <p className="small muted">
            {t('Training:')} {dateLabel(study.train_start)} – {dateLabel(study.train_end)} · {t('Validation ends:')} {dateLabel(study.validation_end)} · {t('Final test ends:')} {dateLabel(study.test_end)}
          </p>
          <Notice>
            {t('Current-snapshot research assumes next-day publication. Original revision history is unverified. These metrics do not establish live forecasting accuracy.')}
          </Notice>

          <div className="table-scroll">
            <table>
              <caption className="sr-only">{t('Retrospective final holdout metrics')}</caption>
              <thead>
                <tr>
                  <th>{t('Horizon')}</th>
                  <th>{t('Selected baseline or model')}</th>
                  <th>{t('Final samples')}</th>
                  <th>{t('MAE / qtl')}</th>
                  <th>{t('Naive MAE / qtl')}</th>
                  <th>{t('WAPE')}</th>
                </tr>
              </thead>
              <tbody>
                {study.horizons.map(row => (
                  <tr key={row.horizon}>
                    <td>{row.horizon} d</td>
                    <td>
                      {({
                        naive: 'Last observed price',
                        mean_14: 'Rolling mean (14 observations)',
                        median_14: 'Rolling median (14 observations)',
                      } as Record<string, string>)[row.selected_model || ''] || row.selected_model || 'Unavailable'}
                    </td>
                    <td>{row.final_n}</td>
                    <td>{inr(row.final_metrics?.mae_inr_per_quintal)}</td>
                    <td>{inr(row.naive_metrics?.mae_inr_per_quintal)}</td>
                    <td>{typeof row.final_metrics?.wape_pct === 'number' ? `${row.final_metrics.wape_pct.toFixed(2)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            {t('Lower MAE and WAPE are better. WAPE is an error percentage, not an accuracy score.')}
          </p>
        </Card>
      ))}

      <Notice>
        {t('Nothing here guarantees a farmer-grade transaction price, profit, or that holding produce will be safe.')}
      </Notice>
    </>
  );
}
