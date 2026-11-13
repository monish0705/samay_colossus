import { localize, t, warningText } from './i18n';
import { explainRecommendation, explainChanges } from './explanations';
import { ReadAloud } from './Speech';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowRight, CheckCircle2, Download, RefreshCw, Scale, Sparkles } from 'lucide-react';
import { api, getDecisionPlan, type Recommendation } from './api';
import { useApp } from './state';
import { Badge, Card, Empty, Notice, PageHeading, Stat, dateLabel, inr, qty } from './ui';
import { ScenarioChart } from './Charts';
import { buildRecommendation } from './advisor';
import { DecisionPanel } from './DecisionPanel';

export function ResultSummary({ result }: { result: Recommendation }) {
  const plan = getDecisionPlan(result);
  return localize(
    <div className="compact-result">
      <h3>{result.decision_support?.conditional && `${t('Conditional')}: `}{plan ? `${qty(plan.sell_today_quintals)} today` : 'No feasible selected plan'}</h3>
      <p>{plan ? `${qty(plan.hold_initial_quintals)} held · ${inr(plan.cash_today_inr)} net cash today` : 'Review cash requirements and physical constraints.'}</p>
    </div>
  );
}

export function Results() {
  const { result, priorResult, language, mode, draft, scope, setResult, catalog } = useApp();
  const [showAll, setShowAll] = useState(false);
  const [scenario, setScenario] = useState<'lower' | 'central' | 'adverse'>('central');
  const [customPrice, setCustomPrice] = useState(draft.price || String(result?.optimization.request_and_assumptions.today_price_inr_per_quintal || ''));
  const [simBusy, setSimBusy] = useState(false);
  const [simDirty, setSimDirty] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  if (!result) {
    return localize(
      <>
        <PageHeading eyebrow={t('RECOMMENDATION RESULTS')} title={t('Your plan will appear here.')}>
          {t('Results come from the backend, after your inputs and constraints are checked.')}
        </PageHeading>
        <Card>
          <Empty
            title={t('No calculated plan in this session')}
            action={
              <Link className="button button-primary" to="/advisor">
                {t('Open selling advisor')}<ArrowRight size={16} />
              </Link>
            }
          >
            {t('Calculate a plan first. We do not restore private financial inputs from browser storage.')}
          </Empty>
        </Card>
      </>
    );
  }

  const output = result.optimization;
  const plan = getDecisionPlan(result);
  const conditionalPlan = Boolean(result.decision_support?.conditional);
  const sellAll = output.sell_all_now;
  const originalQuantity = String(output.request_and_assumptions.total_quantity_quintals || '0');
  const originalPrice = String(output.request_and_assumptions.today_price_inr_per_quintal || '0');
  const originalCash = String(output.request_and_assumptions.required_net_cash_inr || '0');
  const lines = explainRecommendation(result, language);
  const changes = explainChanges(priorResult, result, language);

  const download = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `samay-plan-${result.history_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRecalculateScenario = async () => {
    setSimBusy(true);
    setSimError(null);
    try {
      const updatedDraft = { ...draft, price: draft.price || originalPrice, quantity: originalQuantity, cash: originalCash, scenarioPrice: customPrice };
      const req = buildRecommendation(
        updatedDraft,
        scope,
        (catalog.data?.data || await api.data()).historical_demo_date
      );
      const response = await api.recommend(req);
      setResult(response);
      setSimDirty(false);
    } catch (e: unknown) {
      setSimError(e instanceof Error ? e.message : 'Calculation error');
    } finally {
      setSimBusy(false);
    }
  };

  // Find alternative feasible split plan if available
  const altPlan = output.feasible_plans.find(
    p => p.holding_days > 0 && p.sell_today_quintals !== plan?.sell_today_quintals
  );

  return localize(
    <>
      <PageHeading
        eyebrow={t('YOUR BACKEND-CALCULATED PLAN')}
        title={
          conditionalPlan ? t('Conditional sell-or-hold analysis') : plan
            ? plan.holding_days
              ? t('A balanced view of selling and holding.')
              : t('Keep today’s cash needs covered.')
            : t('These constraints need another look.')
        }
        action={
          <button className="button button-secondary" onClick={download}>
            <Download size={16} />{t('Export this plan')}
          </button>
        }
      >
        {output.scope.market} · {output.scope.commodity} · {output.scope.variety} / {output.scope.grade} · {t('decision')} {dateLabel(output.decision_at)}
      </PageHeading>

      <DecisionPanel result={result}/>
      {result.decision_support && <h2>{t('Full calculation audit for the displayed plan')}</h2>}

      {/* Main Status Banner */}
      <div className={`result-banner ${conditionalPlan ? 'is-conditional' : plan ? 'is-feasible' : 'is-infeasible'}`}>
        {plan ? <CheckCircle2 size={24} /> : <AlertCircle size={24} />}
        <div>
          <strong>{t(conditionalPlan ? 'Conditional analysis, not validated advice' : output.recommendation_basis.replaceAll('_', ' '))}</strong>
          <p>
            {conditionalPlan ? t('Holding is conditional on the displayed price and storage assumptions. The adverse outcome may be worse than selling now.') : plan
              ? plan.holding_days
                ? t('Holding is eligible under the supplied constraints and service evidence. The adverse outcome still matters.')
                : t('A full immediate sale is the selected feasible plan under these inputs.')
              : t('No mandatory cash, market-lot or physical constraint has been relaxed.')}
          </p>
        </div>
        <Badge tone={plan && !conditionalPlan ? 'green' : 'amber'}>
          {conditionalPlan ? t('Scenario only') : plan ? t('Calculated') : t('Infeasible')}
        </Badge>
      </div>

      {result.reliability_warnings.length > 0 && (
        <Notice tone="amber">
          <strong>{t('Reliability limitations')}</strong>
          <ul>
            {[...new Set(result.reliability_warnings.map(w => w.replace(/^\d+d:/,'')))].map(w => (
              <li key={w}>{warningText(w)}</li>
            ))}
          </ul>
        </Notice>
      )}

      {/* Explicit Infeasible Breakdown State */}
      {!plan && (
        <Card className="infeasible-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t('SHORTFALL BREAKDOWN')}</p>
              <h2>{t('Immediate cash need exceeds possible proceeds')}</h2>
            </div>
            <Badge tone="amber">{t('Infeasible Cash Need')}</Badge>
          </div>
          <p>
            {t('Selling 100% of your harvest today cannot generate the net cash you requested.')}
          </p>
          <div className="stats-grid three" style={{ margin: '15px 0' }}>
            <Stat
              label={t('Harvest gross value')}
              value={inr(sellAll.sale.gross_inr)}
              note={`${originalQuantity} qtl @ ₹${originalPrice}/qtl`}
            />
            <Stat
              label={t('Max net cash from 100% sale')}
              value={inr(sellAll?.sale.net_inr || '0')}
              note={t('After transport, commission & mandi fees')}
            />
            <Stat
              label={t('Your cash requirement')}
              value={inr(originalCash)}
              note={t('Immediate net cash needed today')}
            />
          </div>
          <Notice tone="neutral">
            <strong>{t('How to resolve this:')}</strong>{' '}
            {t('Lower your immediate cash requirement to')} <strong>{inr(sellAll?.sale.net_inr || '0')}</strong> {t('or less, or negotiate a higher buyer quote.')}
          </Notice>
          <div style={{ marginTop: '15px' }}>
            <Link to="/advisor" className="button button-primary">
              {t('Edit cash requirement or price')}
            </Link>
          </div>
        </Card>
      )}

      {/* Core Result Stats */}
      <div className="stats-grid four">
        <Stat
          label={t('Sell today')}
          value={qty(plan?.sell_today_quintals)}
          note={t('Marketable quantity sold now')}
        />
        <Stat
          label={t('Hold initially')}
          value={qty(plan?.hold_initial_quintals)}
          note={plan?.holding_days ? `${plan.holding_days} ${t('calendar days; loss still applies')}` : t('No future sale assumed')}
        />
        <Stat
          label={t('Immediate net cash')}
          value={inr(plan?.cash_today_inr)}
          note={t('After transaction and upfront storage costs')}
        />
        <Stat
          label={t('Break-even future price')}
          value={inr(plan?.break_even_future_price_inr_per_quintal)}
          note={t('INR/quintal · not a price forecast')}
        />
      </div>

      {!result.decision_support && output.best_scenario_only_or_validated_plan && !output.best_scenario_only_or_validated_plan.recommendation_eligible && output.best_scenario_only_or_validated_plan.holding_days > 0 && (
        <Card>
          <h2>{t('Best scenario-only plan: not validated advice')}</h2>
          <Notice tone="amber">{t('This comparison uses uncertain prices or user assumptions. The operational safe fallback remains separate.')}</Notice>
          <p>{t('Sell today')}: {qty(output.best_scenario_only_or_validated_plan.sell_today_quintals)} | {t('Hold initially')}: {qty(output.best_scenario_only_or_validated_plan.hold_initial_quintals)}</p>
          <p>{t('Immediate net cash')}: {inr(output.best_scenario_only_or_validated_plan.cash_today_inr)}</p>
          <p>{t('Central total net')}: {inr(output.best_scenario_only_or_validated_plan.total_net_inr.central)} | {t('Adverse total net')}: {inr(output.best_scenario_only_or_validated_plan.total_net_inr.adverse)}</p>
        </Card>
      )}

      {/* Side-by-Side Comparison of Feasible Plans */}
      {plan && (
        <Card className="plans-comparison">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{t('PLAN COMPARISON')}</p>
              <h2>{t('Compare your options')}</h2>
            </div>
            <Badge tone="green">{output.feasible_plans.length} {t('feasible options')}</Badge>
          </div>

          <div className="options-grid">
            {/* Option 1: Sell All Today */}
            <div className={`option-card ${plan.holding_days === 0 ? 'is-selected' : ''}`}>
              <div className="option-header">
                <span className="option-tag">{t('Immediate Sale')}</span>
                {plan.holding_days === 0 && <Badge tone="green">{t('Recommended Plan')}</Badge>}
              </div>
              <h3>{t('Sell 100% Today')}</h3>
              <p className="option-desc">{t('Meet cash needs immediately with zero storage risk.')}</p>
              <dl className="option-metrics">
                <div>
                  <dt>{t('Sell today')}</dt>
                  <dd><strong>{qty(originalQuantity)}</strong></dd>
                </div>
                <div>
                  <dt>{t('Net cash today')}</dt>
                  <dd><strong>{inr(sellAll?.sale.net_inr)}</strong></dd>
                </div>
                <div>
                  <dt>{t('Held produce')}</dt>
                  <dd>0 qtl</dd>
                </div>
                <div>
                  <dt>{t('Holding / spoilage risk')}</dt>
                  <dd>{t('Zero risk')}</dd>
                </div>
              </dl>
            </div>

            {/* Option 2: Cash-First Split (if holding eligible) */}
            {plan.holding_days > 0 && (
              <div className="option-card is-selected">
                <div className="option-header">
                  <span className="option-tag">{t('Cash-First Split')}</span>
                  <Badge tone={conditionalPlan ? 'amber' : 'green'}>{t(conditionalPlan ? 'Conditional plan' : 'Recommended Plan')}</Badge>
                </div>
                <h3>{t('Sell Now + Hold Rest')}</h3>
                <p className="option-desc">{t('Meets today’s cash need; holds remainder for potential upside.')}</p>
                <dl className="option-metrics">
                  <div>
                    <dt>{t('Sell today')}</dt>
                    <dd><strong>{qty(plan.sell_today_quintals)}</strong></dd>
                  </div>
                  <div>
                    <dt>{t('Net cash today')}</dt>
                    <dd><strong>{inr(plan.cash_today_inr)}</strong></dd>
                  </div>
                  <div>
                    <dt>{t('Hold initially')}</dt>
                    <dd><strong>{qty(plan.hold_initial_quintals)}</strong> ({plan.holding_days}d)</dd>
                  </div>
                  <div>
                    <dt>{t('Break-even price')}</dt>
                    <dd><strong>{inr(plan.break_even_future_price_inr_per_quintal)}/qtl</strong></dd>
                  </div>
                </dl>
              </div>
            )}

            {/* Option 3: Alternative Plan if available */}
            {altPlan && (
              <div className="option-card">
                <div className="option-header">
                  <span className="option-tag">{t('Alternative Split')}</span>
                  <Badge tone="neutral">{t('Compared Feasible')}</Badge>
                </div>
                <h3>{qty(altPlan.sell_today_quintals)} {t('Today')} + {qty(altPlan.hold_initial_quintals)} {t('Held')}</h3>
                <p className="option-desc">{t('Alternative plan meeting all mandatory constraints.')}</p>
                <dl className="option-metrics">
                  <div>
                    <dt>{t('Sell today')}</dt>
                    <dd><strong>{qty(altPlan.sell_today_quintals)}</strong></dd>
                  </div>
                  <div>
                    <dt>{t('Net cash today')}</dt>
                    <dd><strong>{inr(altPlan.cash_today_inr)}</strong></dd>
                  </div>
                  <div>
                    <dt>{t('Central total net')}</dt>
                    <dd><strong>{inr(altPlan.total_net_inr.central)}</strong></dd>
                  </div>
                  <div>
                    <dt>{t('Adverse total net')}</dt>
                    <dd><strong>{inr(altPlan.total_net_inr.adverse)}</strong></dd>
                  </div>
                </dl>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Explicit user scenario; calculations are performed by the backend. */}
      {(() => {
        const quickChips = ['1000', '1400', '2000', '5000', '30000', '50000'];
        return (<>
            {/* Scenario Explorer / Simulator */}
            <Card className="simulator-card">
              <div className="section-heading">
                <div>
                  <Badge tone="amber"><Sparkles size={13} />{t('Interactive What-If')}</Badge>
                  <h2>{t('Scenario-Only Simulator (Not a Forecast)')}</h2>
                </div>
                <span className="source-note">{t('Evaluated through real backend optimizer')}</span>
              </div>
              <p className="small muted">
                {t('User-entered future prices are assumptions. Recalculate through the backend to compare proceeds after deterioration, costs and mandatory cash constraints.')}
              </p>

              <div className="simulator-controls">
                <label className="field">
                  <span>{t('Simulated future buyer price (INR/quintal)')}</span>
                  <div className="input-wrap">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={customPrice}
                      onChange={e => {
                        setCustomPrice(e.target.value);
                        setSimDirty(true);
                      }}
                    />
                    <span>INR / qtl</span>
                  </div>
                </label>

                <div className="quick-price-chips">
                  {quickChips.map(p => (
                    <button
                      key={p}
                      type="button"
                      className={`chip ${customPrice === p ? 'is-active' : ''}`}
                      onClick={() => {
                        setCustomPrice(p);
                        setSimDirty(true);
                      }}
                    >
                      ₹{Number(p).toLocaleString('en-IN')}
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  className="button button-primary"
                  disabled={simBusy}
                  onClick={handleRecalculateScenario}
                >
                  {simBusy ? <RefreshCw size={15} className="spin" /> : <RefreshCw size={15} />}
                  {simBusy ? t('Recalculating with backend…') : t('Recalculate with backend')}
                </button>
              </div>

              {simDirty && (
                <Notice tone="amber">
                  {t('Inputs changed. Recalculate before treating any prior result as current.')}
                </Notice>
              )}
              {simError && <p className="field-error" role="alert">{simError}</p>}
            </Card>
          </>
        );
      })()}

      {/* What Scenarios Mean Card */}
      <div className="content-grid">
        <Card>
          <div className="section-heading">
            <h2>{t('What the scenarios mean')}</h2>
            <Badge>{t('Backend calculations')}</Badge>
          </div>
          {plan ? (
            <>
              <div className="scenario-tabs" role="group" aria-label="Future price scenario">
                {([
                  { key: 'lower', title: 'Conservative scenario' },
                  { key: 'central', title: 'Central scenario' },
                  { key: 'adverse', title: 'Adverse scenario' },
                ] as const).map(item => (
                  <button
                    className="button button-secondary"
                    key={item.key}
                    aria-pressed={scenario === item.key}
                    onClick={() => setScenario(item.key)}
                  >
                    {t(item.title)}
                  </button>
                ))}
              </div>

              <div className="scenario-selected" aria-live="polite">
                <span>{t(scenario === 'lower' ? 'Conservative scenario' : scenario === 'central' ? 'Central scenario' : 'Adverse scenario')}</span>
                <strong>{inr(plan.total_net_inr[scenario])}</strong>
                <p>{t('Scenario preview only. The backend-selected plan does not change unless you recalculate.')}</p>
                {plan.holding_days === 0 && <p>{t('No produce is held; no future price is assumed.')}</p>}
              </div>

              <ScenarioChart values={Object.entries(plan.total_net_inr).map(([label, value]) => ({ label, value: Number(value) }))} />

              <div className="result-detail">
                <span>{t('Adverse total net')}</span>
                <strong>{inr(plan.downside_total_net_inr)}</strong>
              </div>
              <div className="result-detail">
                <span>{t('Adverse difference vs sell-all-now')}</span>
                <strong>{inr(plan.difference_vs_sell_all_now_inr.adverse)}</strong>
              </div>
              <p className="small muted">
                {t('Central proceeds are a scenario, not a probability-weighted expected return. If nothing is held, all totals equal the immediate-sale proceeds.')}
              </p>
            </>
          ) : (
            <Empty title={t('No selected scenario')}>
              {t('See rejection reasons below. A negative or infeasible result is never replaced with a success message.')}
            </Empty>
          )}
        </Card>

        {/* Costs, Provenance & Break-Even Callout */}
        <Card>
          <h2>{t('Costs, quantity and provenance')}</h2>
          <div className="result-detail">
            <span>{t('Net sale proceeds')}</span>
            <strong>{inr(plan?.today_sale.net_inr)}</strong>
          </div>
          <div className="result-detail">
            <span>{t('Total storage charge')}</span>
            <strong>{inr(plan?.storage_cost_inr)}</strong>
          </div>
          <div className="result-detail">
            <span>{t('Later saleable quantity')}</span>
            <strong>{qty(plan?.later_saleable_quintals)}</strong>
          </div>
          <div className="result-detail">
            <span>{t('Physical loss / rounding discard')}</span>
            <strong>{qty(plan?.deterioration_loss_quintals)} / {qty(plan?.rounding_discard_quintals)}</strong>
          </div>
          <div className="result-detail">
            <span>{t('Central later proceeds after storage')}</span>
            <strong>{inr(plan?.central_later_net_after_storage_inr)}</strong>
          </div>

          {plan?.break_even_future_price_inr_per_quintal && (
            <div className="break-even-callout">
              <Scale size={18} />
              <div>
                <strong>{t('Break-even price: ')}{inr(plan.break_even_future_price_inr_per_quintal)} / {t('qtl')}</strong>
                <p className="small">
                  {t('Future price must reach this level after storage costs, commission, transport and spoilage to match selling everything today.')}
                </p>
              </div>
            </div>
          )}

          <p className="small" style={{ marginTop: '15px' }}>
            {t('Source report:')} {dateLabel(result.market_data.report_date)}<br />
            {t('Source:')} {result.market_data.source || t('No official observation; farmer-entered quote used')}<br />
            {t('Models:')} {result.predictions.map(p => p.model_version).join(', ') || t('No forecast used')}
          </p>
        </Card>
      </div>

      {/* Settlement Ledger Table (In Judge Mode or Expandable) */}
      {plan && (
        <Card>
          <div className="section-heading">
            <h2>{t('Sale settlement ledger')}</h2>
            <Badge tone="neutral">{t('Paise-exact arithmetic')}</Badge>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('Cost or proceeds')}</th>
                  <th>{t('Today')}</th>
                  <th>{t('Central later sale')}</th>
                </tr>
              </thead>
              <tbody>
                {([
                  { key: 'gross_inr', label: 'Gross proceeds' },
                  { key: 'commission_inr', label: 'Commission' },
                  { key: 'market_fee_inr', label: 'Market fee' },
                  { key: 'transport_inr', label: 'Transport' },
                  { key: 'handling_inr', label: 'Handling' },
                  { key: 'fixed_transaction_inr', label: 'Other fixed costs' },
                  { key: 'net_inr', label: 'Net sale proceeds' },
                ] as const).map(line => (
                  <tr key={line.key}>
                    <td>{t(line.label)}</td>
                    <td>{inr(plan.today_sale[line.key])}</td>
                    <td>{inr(plan.later_sales.central[line.key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Compared Feasible Plans */}
      <Card>
        <div className="section-heading">
          <h2>{t('Compared feasible plans')}</h2>
          <Badge>{output.feasible_plans.length} {t('plans')}</Badge>
        </div>
        <p className="small muted">
          {t('Sell-all-now net: ')}{inr(output.sell_all_now.sale.net_inr)}. {t('. Every listed plan meets cash, storage and lot constraints; only eligible plans can be selected.')}
        </p>

        {output.feasible_plans.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('Sell now')}</th>
                  <th>{t('Hold / days')}</th>
                  <th>{t('Cash today')}</th>
                  <th>{t('Central total')}</th>
                  <th>{t('Adverse total')}</th>
                  <th>{t('Eligibility')}</th>
                </tr>
              </thead>
              <tbody>
                {(showAll ? output.feasible_plans : output.feasible_plans.slice(0, 12)).map((p, i) => (
                  <tr key={i}>
                    <td>{qty(p.sell_today_quintals)}</td>
                    <td>{qty(p.hold_initial_quintals)} / {p.holding_days}d</td>
                    <td>{inr(p.cash_today_inr)}</td>
                    <td>{inr(p.total_net_inr.central)}</td>
                    <td>{inr(p.total_net_inr.adverse)}</td>
                    <td>
                      <Badge tone={p.recommendation_eligible ? 'green' : 'amber'}>
                        {p.recommendation_eligible ? t('Eligible') : t('Scenario only')}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Notice>
            {t('No feasible plans.')}{' '}
            {Object.entries(output.rejected_counts)
              .map(([reason, count]) => `${reason.replaceAll('_', ' ')} (${count})`)
              .join(' · ')}
          </Notice>
        )}

        {output.feasible_plans.length > 12 && (
          <button className="text-button" onClick={() => setShowAll(!showAll)}>
            {showAll ? t('Show fewer') : t('Show all compared plans')}
          </button>
        )}
      </Card>

      {/* Explanations & Transparency */}
      <Card>
        <h2>{t('Assumptions and explanation')}</h2>
        {changes.length > 0 && (
          <div className="change-explanation">
            <h3>{t('Why did the plan change?')}</h3>
            <ul>
              {changes.map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ul>
          </div>
        )}

        <ReadAloud lines={lines} />

        <details className="why-panel">
          <summary>{t('Why this recommendation?')}</summary>
          <p className="small muted">
            {t('Exact backend calculations. Language changes never change these values.')}
          </p>
          <ol className="explanation-list">
            {lines.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ol>
          <p className="small">
            {t('Source report:')} {dateLabel(result.market_data.report_date)} · {t('Fetched')} {dateLabel(result.market_data.fetched_at)}
          </p>
          <p className="small">
            {t('Model')} {result.predictions.map(p => p.model_version).join(', ') || t('No forecast used')}
          </p>
        </details>

        {mode === 'judge' && (
          <details className="judge-assumptions-panel" style={{ marginTop: '12px' }}>
            <summary>{t('Inspect the exact submitted assumptions')}</summary>
            <pre className="json-view">{JSON.stringify(output.request_and_assumptions, null, 2)}</pre>
          </details>
        )}

        <p className="source-note">
          {t('Local history #')}{result.history_id} · {t('request ')}{result.request_id}
        </p>
      </Card>

      <div className="page-actions">
        <Link to="/advisor" className="button button-secondary">
          {t('Edit inputs')}
        </Link>
        <Link to="/explorer" className="button button-primary">
          {t('Explore a different scenario')}<ArrowRight size={16} />
        </Link>
      </div>
    </>
  );
}
