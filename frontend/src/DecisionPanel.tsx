import { api, type Recommendation, type Schema, type Scope } from './api';
import { localize, t, warningText } from './i18n';
import { Badge, Card, Loading, Notice, Stat, dateLabel, inr, qty, useResource } from './ui';

export function CropDomainCard({ profile }: { profile: NonNullable<Schema<'MarketContext'>['domain_profile']> }) {
  const badgeTone = (impact: string): 'neutral' | 'green' | 'amber' | 'red' => {
    switch (impact) {
      case 'bullish': return 'green';
      case 'bearish': return 'red';
      case 'watch': return 'amber';
      default: return 'neutral';
    }
  };

  return localize(
    <div className="crop-domain-card" style={{ marginTop: '1.25rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">{t('CROP DOMAIN RESEARCH')}</p>
          <h4 style={{ margin: 0 }}>{t('Multi-factor market drivers')} ({profile.commodity} · {profile.market})</h4>
        </div>
        <Badge tone="green">{t('Karnataka Mandi Domain')}</Badge>
      </div>
      <div className="stats-grid two" style={{ margin: '0.75rem 0 1rem' }}>
        <Stat label={t('Optimal storage duration')} value={profile.optimal_storage_duration} note={t('Storage feasibility & godown requirements')} />
        <Stat label={t('Spoilage & storage risk')} value={profile.spoilage_risk} note={t('Shrinkage, decay & moisture factors')} />
      </div>
      <div className="driver-list" style={{ display: 'grid', gap: '0.75rem' }}>
        {profile.drivers.map(d => (
          <div key={d.title} style={{ padding: '0.85rem', background: 'var(--surface-sunken)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <strong>{d.title}</strong>
              <Badge tone={badgeTone(d.impact)}>{t(d.category)}</Badge>
            </div>
            <p className="small muted" style={{ margin: 0, lineHeight: 1.45 }}>{d.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

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
    {context.domain_profile && <CropDomainCard profile={context.domain_profile} />}
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
  const later = decision.best_holding_plan;
  const laterPrediction = result.predictions.find(p=>p.horizon_calendar_days===later?.holding_days);
  const selectedPrediction = result.predictions.find(p => p.horizon_calendar_days === plan?.holding_days);
  return localize(<Card className="decision-panel">
    <p className="eyebrow">{t('SELL OR HOLD DECISION')}</p>
    {String(result.optimization.request_and_assumptions.today_price_assumption || '').startsWith('EXAMPLE_ONLY') && <Badge tone="amber">{t('Illustrative inputs, not a live farmer buyer quote')}</Badge>}
    <div className="section-heading"><h2>{t(actionLabels[decision.action])}</h2><Badge tone="amber">{t(decision.conditional ? 'Conditional analysis, not validated advice' : 'Calculated from your constraints')}</Badge></div>
    <p>{t('The decision compares net proceeds after fees, transport, storage and quantity loss. Mandatory cash needs are never relaxed.')}</p>
    {decision.holding_economics && (
      <div
        className={`holding-verdict-card ${decision.holding_economics.is_profitable ? 'is-profitable' : 'is-loss'}`}
        style={{
          padding: '1.25rem',
          margin: '1.25rem 0',
          borderRadius: '10px',
          border: decision.holding_economics.is_profitable ? '2px solid #16a34a' : '2px solid #ea580c',
          background: decision.holding_economics.is_profitable ? 'rgba(22, 163, 74, 0.08)' : 'rgba(234, 88, 12, 0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h3 style={{ margin: 0, color: decision.holding_economics.is_profitable ? '#15803d' : '#c2410c', fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>{decision.holding_economics.is_profitable ? '✓' : '⚠'}</span>
            <span>{t(decision.holding_economics.verdict_title)}</span>
          </h3>
          <Badge tone={decision.holding_economics.is_profitable ? 'green' : 'amber'}>
            {decision.holding_economics.is_profitable ? t('Profit Opportunity') : t('Loss Avoidance')}
          </Badge>
        </div>
        <p style={{ margin: '0.5rem 0 1rem', fontSize: '0.95rem', lineHeight: 1.5 }}>
          {decision.holding_economics.verdict_reason}
        </p>
        <div className="stats-grid four">
          <Stat
            label={t('Immediate sale today')}
            value={inr(decision.holding_economics.today_net_sale_inr)}
            note={t('Net proceeds if sold today')}
          />
          <Stat
            label={t('Projected later proceeds')}
            value={inr(decision.holding_economics.later_central_net_inr)}
            note={`${decision.holding_economics.holding_days} ${t('days holding net after storage')}`}
          />
          <Stat
            label={decision.holding_economics.is_profitable ? t('Projected net profit gain') : t('Projected holding loss')}
            value={inr(decision.holding_economics.projected_diff_inr)}
            note={decision.holding_economics.is_profitable ? t('Net profit vs selling today') : t('Net loss vs selling today')}
          />
          <Stat
            label={t('Break-even price needed')}
            value={decision.holding_economics.break_even_price_inr_per_quintal ? inr(decision.holding_economics.break_even_price_inr_per_quintal) : '—'}
            note={t('Future mandi price to match today')}
          />
        </div>
      </div>
    )}
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
    {later ? <section aria-label={t('Sell-later comparison')}>
      <h3>{t(laterPrediction ? 'Model-based sell-later comparison' : 'Sell-later scenario comparison')}</h3>
      <p>{t('Hold initially')}: {qty(later.hold_initial_quintals)} · {t('Sell today')}: {qty(later.sell_today_quintals)} · {later.holding_days} {t('calendar days')}{laterPrediction && <> · {t('Target')}: {dateLabel(laterPrediction.target_date)} · {t('Predicted')}: {inr(laterPrediction.prediction_inr_per_quintal)} / {t('quintal')}</>}</p>
      <div className="stats-grid three">
        <Stat label={t('Projected later net proceeds')} value={inr(later.central_later_net_after_storage_inr)} note={t('After selling costs, storage and quantity loss')}/>
        <Stat label={t('Projected gain or loss versus selling now')} value={inr(later.difference_vs_sell_all_now_inr.central)} note={t('Forecast-based projection, not guaranteed profit')}/>
        <Stat label={t('Adverse gain or loss against selling now')} value={inr(later.difference_vs_sell_all_now_inr.adverse)} note={t('User-reviewed stress scenario, not a prediction interval')}/>
      </div>
      <Notice>{t('This is the feasible holding plan with the highest central net proceeds. Your risk preference can still select immediate sale. Production costs were not supplied, so this is a comparison with selling now, not total farm profit.')}</Notice>
    </section> : <Notice>{t('No feasible sell-later plan exists under these storage, cash or forecast inputs. Enter verified storage capacity to assess holding.')}</Notice>}
    <details><summary>{t('Review weather, festivals and news evidence')}</summary><ContextEvidence context={decision.context}/></details>
  </Card>);
}
