import { api, type Recommendation, type Schema, type Scope } from './api';
import { localize, t, warningText } from './i18n';
import { Badge, Card, Loading, Notice, Stat, dateLabel, inr, qty, useResource } from './ui';

export function ContextEvidence({ context }: { context: Schema<'MarketContext'> }) {
  const weather = context.weather || [], events = context.events || [], news = context.news || [];
  return localize(<>
    <div className="section-heading"><h3>{t('Weather, events and news')}</h3><Badge tone={context.status === 'available' ? 'green' : 'amber'}>{t(context.status)}</Badge></div>
    <p className="small muted">{t('Dated evidence for review. No automatic festival or headline price multiplier is applied.')}</p>
    {context.location_label && <p className="small">{context.location_label}</p>}
    {weather.length ? <div className="table-scroll"><table><caption>{t('Weather forecast near the market city, not the farm')}</caption><thead><tr><th>{t('Date')}</th><th>{t('Maximum temperature')}</th><th>{t('Rain forecast')}</th><th>{t('Rain probability')}</th></tr></thead><tbody>
      {weather.slice(0,7).map(d => <tr key={d.date}><td>{dateLabel(d.date)}</td><td>{d.max_temperature_c ?? '—'} °C</td><td>{d.precipitation_mm ?? '—'} mm</td><td>{d.precipitation_probability_percent ?? '—'}%</td></tr>)}
    </tbody></table></div> : <Notice>{t('No usable weather forecast was captured for this decision time.')}</Notice>}
    {events.length ? <><h4>{t('Upcoming calendar events')}</h4><ul>{events.slice(0,6).map(e => <li key={`${e.date}-${e.name}`}><a href={e.source_url} target="_blank" rel="noreferrer">{e.name}</a> · {dateLabel(e.date)}</li>)}</ul><p className="small muted">{t('An office holiday calendar does not confirm mandi closure or a crop price increase.')}</p></> : <p className="small muted">{t('No verified calendar event is available in this period.')}</p>}
    <h4>{t('Recent sourced headlines')}</h4>
    {news.length ? <ul>{news.map(n => <li key={n.url}><a href={n.url} target="_blank" rel="noreferrer">{n.title}</a><p className="small muted">{n.source} · {dateLabel(n.published_at)} · {t(n.topics?.includes('general_agriculture') ? 'General agriculture; crop-specific price effect unverified' : 'Crop-related headline; price effect unverified')}</p></li>)}</ul> : <p className="small muted">{t('No matching recent headline was found in the collected feeds. This does not mean there is no relevant news.')}</p>}
    {!!context.warnings?.length && <Notice>{context.warnings.map(w => warningText(w)).join(' · ')}</Notice>}
    <details><summary>{t('Evidence sources and capture times')}</summary><ul>{(context.sources || []).map(s => <li key={`${s.url}-${s.fetched_at}`}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> · {t(s.status)} · {new Intl.DateTimeFormat('en-IN',{ dateStyle: 'medium',timeStyle: 'short',timeZone: 'Asia/Kolkata' }).format(new Date(s.fetched_at))} IST</li>)}</ul></details>
  </>);
}

export function MarketContextPanel({ scope, days = 7, collapsed = false }: { scope: Scope; days?: number; collapsed?: boolean }) {
  const resource = useResource(signal => api.context(scope,Math.max(1,Math.min(days,730)),signal),JSON.stringify({ scope, days }));
  const evidence = resource.loading ? <Loading label={t('Loading captured weather and news…')}/> : resource.data ? <ContextEvidence context={resource.data}/> : <Notice>{t('External context is disconnected. No weather or news data is being invented.')}</Notice>;
  return <Card>{collapsed ? <details><summary>{t('Review weather, festivals and news evidence')}</summary>{evidence}</details> : evidence}</Card>;
}

const actionLabels = {
  hold: 'Conditional hold', partial_sell_and_hold: 'Sell some now; conditionally hold the rest',
  sell_now: 'Sell now under these assumptions', infeasible: 'The cash requirement cannot be met',
  insufficient_evidence: 'A future-price scenario is still needed',
} as const;

export function DecisionPanel({ result }: { result: Recommendation }) {
  const decision = result.decision_support;
  if (!decision) return null;
  const plan = decision.plan;
  const safe = decision.safe_fallback_plan;
  const selectedPrediction = result.predictions.find(p => p.horizon_calendar_days === plan?.holding_days);
  return localize(<Card className="decision-panel">
    <p className="eyebrow">{t('SELL OR HOLD DECISION')}</p>
    {String(result.optimization.request_and_assumptions.today_price_assumption || '').startsWith('EXAMPLE_ONLY') && <Badge tone="amber">{t('Illustrative inputs, not a live farmer buyer quote')}</Badge>}
    <div className="section-heading"><h2>{t(actionLabels[decision.action])}</h2><Badge tone="amber">{t(decision.conditional ? 'Conditional analysis, not validated advice' : 'Calculated from your constraints')}</Badge></div>
    <p>{t('The decision compares net proceeds after fees, transport, storage and quantity loss. Mandatory cash needs are never relaxed.')}</p>
    {plan ? <>
      <div className="stats-grid four">
        <Stat label={t('Sell today')} value={qty(plan.sell_today_quintals)} note={t('Quantity sold under cash and storage constraints')}/>
        <Stat label={t('Hold initially')} value={qty(plan.hold_initial_quintals)} note={`${plan.holding_days} ${t('calendar days')}`}/>
        <Stat label={t('Immediate net cash')} value={inr(plan.cash_today_inr)} note={t('After fees and upfront storage')}/>
        <Stat label={t('Break-even future price')} value={inr(plan.break_even_future_price_inr_per_quintal)} note={t('INR/quintal needed to match selling everything now')}/>
      </div>
      {plan.holding_days > 0 && <Notice tone="amber">{t('Holding is conditional on the displayed price and storage assumptions. The adverse outcome may be worse than selling now.')}</Notice>}
      <div className="stats-grid three">
        <Stat label={t('Central gain against selling now')} value={inr(plan.difference_vs_sell_all_now_inr.central)} note={t('Planning scenario, not guaranteed profit')}/>
        <Stat label={t('Adverse gain or loss against selling now')} value={inr(plan.difference_vs_sell_all_now_inr.adverse)} note={t('User-reviewed stress scenario, not a prediction interval')}/>
        <Stat label={t('Total storage cost')} value={inr(plan.storage_cost_inr)} note={`${t('Saleable after storage')}: ${qty(plan.later_saleable_quintals)}`}/>
      </div>
      <details><summary>{t('Why this sell-or-hold decision?')}</summary>
        <ul>{decision.reasons.map(reason => <li key={reason}>{warningText(reason)}</li>)}</ul>
        <dl className="definition-list">
          <div><dt>{t('Today gross proceeds')}</dt><dd>{inr(plan.today_sale.gross_inr)}</dd></div>
          <div><dt>{t('Commission')}</dt><dd>{inr(plan.today_sale.commission_inr)}</dd></div>
          <div><dt>{t('Market fee')}</dt><dd>{inr(plan.today_sale.market_fee_inr)}</dd></div>
          <div><dt>{t('Transport')}</dt><dd>{inr(plan.today_sale.transport_inr)}</dd></div>
          <div><dt>{t('Handling')}</dt><dd>{inr(plan.today_sale.handling_inr)}</dd></div>
          <div><dt>{t('Lost or deteriorated quantity')}</dt><dd>{qty(plan.deterioration_loss_quintals)}</dd></div>
        </dl>
        <p>{t('Market data date')}: {dateLabel(result.market_data.report_date)} · {t('Model')}: {selectedPrediction?.model_version || t('User scenario or flat reference; no long-horizon trained model')}</p>
      </details>
    </> : <Notice tone="amber">{decision.reasons.map(r => warningText(r)).join(' · ')}</Notice>}
    {!!decision.horizon_comparisons.length && <div className="table-scroll"><table><caption>{t('Best feasible plan at each evaluated holding date')}</caption><thead><tr><th>{t('Days held')}</th><th>{t('Sell today')}</th><th>{t('Hold initially')}</th><th>{t('Central total net')}</th><th>{t('Adverse total net')}</th><th>{t('Break-even price')}</th></tr></thead><tbody>{decision.horizon_comparisons.map(p => <tr key={p.holding_days}><td>{p.holding_days}</td><td>{qty(p.sell_today_quintals)}</td><td>{qty(p.hold_initial_quintals)}</td><td>{inr(p.total_net_inr.central)}</td><td>{inr(p.total_net_inr.adverse)}</td><td>{inr(p.break_even_future_price_inr_per_quintal)}</td></tr>)}</tbody></table></div>}
    {decision.conditional && safe && <p className="small muted">{t('Safe fallback kept separately')}: {t('Sell today')} {qty(safe.sell_today_quintals)} · {inr(safe.cash_today_inr)} {t('net cash today')}.</p>}
    <details><summary>{t('Review weather, festivals and news evidence')}</summary><ContextEvidence context={decision.context}/></details>
  </Card>);
}
