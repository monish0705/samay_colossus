import type { Recommendation } from './api';
import { t, type Language } from './i18n';

const value = (input: unknown, unit = 'INR'): string => {
  if ((typeof input !== 'string' && typeof input !== 'number') || !Number.isFinite(Number(input))) throw new Error('Invalid backend calculation value');
  return unit === 'INR' ? `₹${String(input)}` : `${String(input)} ${unit}`;
};
/** Text templates only: every amount is read from the backend; no economic arithmetic. */
export function explainRecommendation(result: Recommendation, language: Language): string[] {
  const o = result.optimization, p = o.recommended_plan;
  const translate = (text: string, values: Record<string, string | number> = {}) => t(text, values, language);
  if (!p) return [translate('No plan meets the mandatory cash or physical constraints. No requirement was relaxed.'), translate('Selling everything today would net {net}.', { net: value(o.sell_all_now.sale.net_inr) })];
  const q = (v: string | number) => value(v, language === 'kn' ? 'ಕ್ವಿಂಟಾಲ್' : 'qtl');
  return [
    translate('Sell {sold} today and hold {held} for {days} calendar days.', { sold: q(p.sell_today_quintals), held: q(p.hold_initial_quintals), days: p.holding_days }),
    translate('{quantity} × {price} per quintal = {gross} gross proceeds.', { quantity: q(p.sell_today_quintals), price: value(o.request_and_assumptions.today_price_inr_per_quintal), gross: value(p.today_sale.gross_inr) }),
    translate('{gross} − {commission} commission − {fee} market fee − {transport} transport − {handling} handling − {fixed} fixed charges = {net} net sale proceeds.', { gross: value(p.today_sale.gross_inr), commission: value(p.today_sale.commission_inr), fee: value(p.today_sale.market_fee_inr), transport: value(p.today_sale.transport_inr), handling: value(p.today_sale.handling_inr), fixed: value(p.today_sale.fixed_transaction_inr), net: value(p.today_sale.net_inr) }),
    translate('{net} net sale proceeds − {storage} upfront storage = {cash} immediate net cash.', { net: value(p.today_sale.net_inr), storage: value(p.storage_paid_today_inr), cash: value(p.cash_today_inr) }),
    translate('Your required cash is {required}. The backend reports a cash surplus of {surplus}.', { required: value(o.request_and_assumptions.required_net_cash_inr), surplus: value(p.cash_surplus_inr) }),
    translate('{held} held − {loss} deterioration − {discard} rounding discard = {saleable} later saleable.', { held: q(p.hold_initial_quintals), loss: q(p.deterioration_loss_quintals), discard: q(p.rounding_discard_quintals), saleable: q(p.later_saleable_quintals) }),
    translate('Central total net: {central}. Adverse total net: {adverse}. Selling everything now: {baseline}.', { central: value(p.total_net_inr.central), adverse: value(p.total_net_inr.adverse), baseline: value(o.sell_all_now.sale.net_inr) }),
    translate('Official report date: {date}. Forecast model: {model}.', { date: result.market_data.report_date || translate('Not available'), model: result.predictions.map(x => x.model_version).join(', ') || translate('No forecast used') }),
    translate('Future prices are uncertain. You make the final decision.'),
  ];
}
export function explainChanges(previous: Recommendation | null, current: Recommendation, language: Language): string[] {
  if (!previous) return [];
  if (JSON.stringify(previous.optimization.scope) !== JSON.stringify(current.optimization.scope)) return [t('The selected series changed; these plans are not a like-for-like performance comparison.', {}, language)];
  const before = previous.optimization.request_and_assumptions, after = current.optimization.request_and_assumptions;
  const lines: string[] = [];
  for (const [key, title] of [['required_net_cash_inr', 'Required cash'], ['storage_capacity_quintals', 'Storage capacity'], ['today_price_inr_per_quintal', 'Buyer quote']] as const) if (String(before[key]) !== String(after[key])) lines.push(t('{field} changed from {before} to {after}.', { field: t(title, {}, language), before: String(before[key]), after: String(after[key]) }, language));
  if (JSON.stringify(before.today_sale_costs) !== JSON.stringify(after.today_sale_costs)) lines.push(t('Transaction costs changed. Net cash is recalculated after those charges.', {}, language));
  if (JSON.stringify(before.holding_options) !== JSON.stringify(after.holding_options)) lines.push(t('Storage, loss or future-sale assumptions changed. The backend rechecked saleable quantity and feasibility.', {}, language));
  if (String(before.risk_tolerance) !== String(after.risk_tolerance)) lines.push(t('Risk preference changed. The backend applied its documented adverse/central objective weights.', {}, language));
  if (lines.length) lines.push(t('The backend now selects {sold} sold and {held} held. Mandatory cash, storage and reliability constraints still apply.', { sold: String(current.optimization.recommended_plan?.sell_today_quintals ?? '—'), held: String(current.optimization.recommended_plan?.hold_initial_quintals ?? '—') }, language));
  return lines;
}
