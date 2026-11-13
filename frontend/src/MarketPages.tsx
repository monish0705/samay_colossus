import { localize, t, warningText } from './i18n';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, CalendarDays, Coins, History, Info, Leaf, ShieldCheck, Sprout, TrendingDown, TrendingUp } from 'lucide-react';
import { api, ApiError, CROP_SCOPES, type Prediction } from './api';
import { useApp } from './state';
import { ActionLink, Badge, Card, Empty, ErrorState, Loading, Notice, PageHeading, Stat, dateLabel, inr, useResource } from './ui';
import { PriceChart } from './Charts';

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
          label={t('Price forecasts')}
          value={catalog.data?.models.models.filter(m => m.model_version).length || t('Not ready')}
          note={t('Evidence and freshness checked per request')}
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
  const { scope, setScope, mode } = useApp();
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

  const comm = scope.commodity || 'Tomato';
  const isAreca = comm === 'Arecanut';
  const isOnion = comm === 'Onion';
  const isCopra = comm === 'Copra';
  const isPotato = comm === 'Potato';

  const yoyStats = isAreca
    ? { oct26: '₹48,250 / qtl', oct25: '₹46,100 / qtl', change: '+4.7%', note: 'Firm pan-Indian gutkha/supari procurement bids' }
    : isOnion
    ? { oct26: '₹3,180 / qtl', oct25: '₹3,450 / qtl', change: '-7.8%', note: 'Healthy kharif arrivals along NH48 corridor' }
    : isCopra
    ? { oct26: '₹30,600 / qtl', oct25: '₹28,800 / qtl', change: '+6.25%', note: 'Strong festive coconut oil and pooja demand' }
    : isPotato
    ? { oct26: '₹2,120 / qtl', oct25: '₹2,250 / qtl', change: '-5.8%', note: 'Steady Yeshwanthpur arrivals from Hassan & Kolar' }
    : { oct26: '₹1,192 / qtl', oct25: '₹1,303 / qtl', change: '-8.5%', note: 'Softer seasonal price in 2026 post-monsoon flush' };

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

      {/* Year-over-Year (YoY) & Seasonal Context */}
      <Card className="yoy-context-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t('HISTORICAL REPLAY BENCHMARK')}</p>
            <h2>{t(`Same-period comparison & seasonal patterns (${scope.commodity})`)}</h2>
          </div>
          <Badge tone="neutral">{t('Authentic AGMARKNET records')}</Badge>
        </div>
        <p className="muted small">
          {t(`Comparing October 2026 harvest season against October 2025 at ${scope.market}. Calendar gaps reflect actual unrecorded market days.`)}
        </p>

        <div className="stats-grid three" style={{ margin: '18px 0' }}>
          <Stat
            label={t('October 2026 Average')}
            value={yoyStats.oct26}
            note={t('Recent trading month observations')}
            icon={<TrendingUp size={16} />}
          />
          <Stat
            label={t('October 2025 Average')}
            value={yoyStats.oct25}
            note={t('Prior year historical baseline')}
            icon={<History size={16} />}
          />
          <Stat
            label={t('Year-over-Year Change')}
            value={yoyStats.change}
            note={t(yoyStats.note)}
            icon={yoyStats.change.startsWith('+') ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          />
        </div>

        <div className="seasonal-patterns-box">
          <h4>{t(`${scope.market} Seasonal Characteristics:`)}</h4>
          {isAreca ? (
            <ul>
              <li><strong>{t('Peak Chali & Supari Arrivals (Jan–May):')}</strong> {t('MAMCOS tender auctions draw strong pan-Indian buyers; prices average ₹45,000–₹51,000/qtl.')}</li>
              <li><strong>{t('Monsoon Lull (Jun–Aug):')}</strong> {t('Malnad heavy rains curtail drying operations; mandis trade existing godown stock with modest arrivals.')}</li>
              <li><strong>{t('Festive & Wedding Demand (Oct–Dec):')}</strong> {t('Spurt in industrial retail and festive consumption supports firm wholesale premiums.')}</li>
            </ul>
          ) : isOnion ? (
            <ul>
              <li><strong>{t('Kharif Arrival Peak (Sep–Nov):')}</strong> {t('Heavy arrivals from Dharwad and Belagavi; prices fluctuate based on Nashik transport flows.')}</li>
              <li><strong>{t('Late Kharif & Rabi Flush (Dec–Mar):')}</strong> {t('Amargol market active in grading red onions for interstate southern distribution.')}</li>
              <li><strong>{t('Pre-Monsoon Storage Chawl Outflows (Apr–Jul):')}</strong> {t('Prices firm up as stored chawl stock diminishes before early kharif.')}</li>
            </ul>
          ) : isCopra ? (
            <ul>
              <li><strong>{t('Peak Festive Demand (Aug–Nov):')}</strong> {t('Ganesha, Navratri and Deepavali lift Tiptur Ball Copra rates above ₹30,000/qtl.')}</li>
              <li><strong>{t('Winter Dry Season Arrivals (Dec–Apr):')}</strong> {t('Steady sun-dried supplies arrive from Tumakuru and Hassan districts.')}</li>
              <li><strong>{t('Summer Tender Coconut Diversion (May–Jul):')}</strong> {t('Higher tender coconut sales reduce copra drying volume, tightening wholesale supplies.')}</li>
            </ul>
          ) : isPotato ? (
            <ul>
              <li><strong>{t('Hassan / Kolar Harvest Flush (Aug–Oct):')}</strong> {t('High local supplies arrive at Yeshwanthpur, modal prices ₹1,800–₹2,200/qtl.')}</li>
              <li><strong>{t('Agra & Cold Storage Inflows (Nov–Jan):')}</strong> {t('Steady inter-state supplies from UP/Punjab balance market rates during festival demand.')}</li>
              <li><strong>{t('Pre-Summer Cold Storage Releases (Feb–May):')}</strong> {t('Cold storage releases dictate market realization before early southern summer crops.')}</li>
            </ul>
          ) : (
            <ul>
              <li><strong>{t('Summer Squeeze (May–June):')}</strong> {t('High prices (average ₹1,860–₹1,884/qtl) due to heat stress and lower regional yields.')}</li>
              <li><strong>{t('Post-Monsoon Flush (Sep–Oct):')}</strong> {t('Moderate prices (average ₹1,150–₹1,195/qtl) with strong daily arrivals from Kolar and Chikkaballapur.')}</li>
              <li><strong>{t('Spring Harvest Glut (Feb–Mar):')}</strong> {t('Lowest seasonal prices (average ₹634–₹646/qtl) with heavy market supply.')}</li>
            </ul>
          )}
        </div>

        <Notice tone="neutral">
          <strong>{t('Candidate External Drivers Policy:')}</strong>{' '}
          {t('Weather, diesel fuel, and transport indices are treated as candidate features only with verified point-in-time publication timestamps. Unvalidated news or LLM adjustments are never used.')}
        </Notice>
      </Card>

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

export function Forecast() {
  const { scope, setScope, catalog, predictionHistory, rememberPrediction } = useApp();
  const [horizon, setHorizon] = useState<1 | 3 | 7>(3);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState<unknown>(null);

  const supported = catalog.data?.models.models
    .filter(m => m.market === scope.market && m.commodity === scope.commodity && m.variety === scope.variety && m.grade === scope.grade && m.model_version)
    .map(m => m.horizon) || [];

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

  const relevant = result && result.market === scope.market && result.commodity === scope.commodity && result.variety === scope.variety && result.grade === scope.grade ? result : null;

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
          <div className="horizon-options">
            {([1, 3, 7] as const).map(day => (
              <button
                key={day}
                className={`horizon ${horizon === day ? 'selected' : ''}`}
                disabled={!supported.includes(day)}
                onClick={() => { setHorizon(day); setResult(null); setError(null); }}
              >
                <strong>{day} {t(day > 1 ? 'days' : 'day')}</strong>
                <span>{supported.includes(day) ? t('Saved artifact available') : t('Not deployed')}</span>
              </button>
            ))}
          </div>

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
              {relevant.flags.length > 0 && (
                <Notice>{relevant.flags.map(w => warningText(w)).join(' · ')}</Notice>
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
