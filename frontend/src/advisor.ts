import { z } from 'zod';
import type { RecommendInput, Scope } from './api';
export interface AdvisorValues { quantity: string; cash: string; price: string; capacity: string; days: '1' | '3' | '7'; limit: string; loss: string; storage: string; storageFixed: string; payment: 'today' | 'later'; transportFixed: string; transportVariable: string; handling: string; fixedTransaction: string; commission: string; marketFee: string; increment: string; minimumLot: string; step: string; risk: 'conservative' | 'balanced' | 'aggressive'; notes: string; conditions: string; realization: string; adverse: string; acknowledged: boolean; example: boolean }
export const blankAdvisor: AdvisorValues = { quantity: '', cash: '', price: '', capacity: '0', days: '3', limit: '0', loss: '', storage: '0', storageFixed: '0', payment: 'later', transportFixed: '0', transportVariable: '0', handling: '0', fixedTransaction: '0', commission: '0', marketFee: '0', increment: '1', minimumLot: '1', step: '0.01', risk: 'conservative', notes: '', conditions: '', realization: '1', adverse: '0', acknowledged: false, example: false };
export const exampleAdvisor: AdvisorValues = { ...blankAdvisor, quantity: '20', cash: '10000', price: '1000', transportFixed: '100', transportVariable: '10', commission: '5', notes: 'EXAMPLE_ONLY demonstration quote and costs, not live prices', acknowledged: true, example: true };
const amount = z.string().regex(/^\d+(\.\d{1,4})?$/, 'Enter a nonnegative number with up to four decimal places.').refine(v => Number(v) <= 1e9, 'Value is too large.');
export function validateAdvisor(v: AdvisorValues): Record<string, string> {
  const numeric = ['quantity', 'cash', 'price', 'capacity', 'increment', 'minimumLot', 'step', 'transportFixed', 'transportVariable', 'handling', 'fixedTransaction', 'commission', 'marketFee', 'storage', 'storageFixed', 'adverse', 'realization'] as const;
  const errors: Record<string, string> = {};
  for (const key of numeric) { const parsed = amount.safeParse(v[key]); if (!parsed.success) errors[key] = parsed.error.issues[0].message; }
  for (const key of ['quantity', 'price', 'increment', 'minimumLot', 'step'] as const) if (Number(v[key]) <= 0) errors[key] = 'Enter a value greater than zero.';
  if (Number(v.quantity) > 100000 || Number(v.capacity) > 100000) errors.quantity = 'Quantity/capacity cannot exceed 100,000 quintals.';
  if (Number(v.commission) + Number(v.marketFee) >= 100) errors.commission = 'Combined percentage charges must be below 100%.';
  if (!(Number(v.realization) > 0 && Number(v.realization) <= 2)) errors.realization = 'Use a realization factor greater than 0 and at most 2.';
  if (v.notes.trim().length < 3) errors.notes = 'Describe where your buyer quote and costs came from.';
  if (!v.acknowledged) errors.acknowledged = 'Confirm these assumptions before calculating.';
  if (Number(v.capacity) > 0) {
    if (!/^\d+$/.test(v.limit) || Number(v.limit) < 1 || Number(v.limit) > 7) errors.limit = 'Enter a verified crop holding limit from 1 to 7 days.';
    if (Number(v.days) > Number(v.limit)) errors.days = 'The planned date exceeds your crop holding limit.';
    if (!amount.safeParse(v.loss).success || Number(v.loss) > 100) errors.loss = 'Enter an assumed daily loss from 0 to 100%.';
    if (v.conditions.trim().length < 3) errors.conditions = 'Describe storage conditions and the source of your loss estimate.';
  }
  for (const key of ['quantity', 'capacity', 'increment', 'minimumLot', 'step'] as const) if (!/^\d+(\.\d{1,3})?$/.test(v[key])) errors[key] = 'Quantities support up to three decimal places.';
  const step = Math.round(Number(v.step) * 1000);
  if (step > 0) for (const key of ['quantity', 'increment', 'minimumLot'] as const) if (Math.round(Number(v[key]) * 1000) % step) errors[key] = 'Use a multiple of the market sale step.';
  return errors;
}
export function buildRecommendation(v: AdvisorValues, scope: Scope, historicalDate?: string | null): RecommendInput {
  const errors = validateAdvisor(v);
  if (Object.keys(errors).length) throw new Error(Object.values(errors)[0]);
  const percent = (s: string) => (Number(s) / 100).toFixed(6);
  const costs = { fixed_transport_inr: v.transportFixed, transport_inr_per_quintal: v.transportVariable, handling_inr_per_quintal: v.handling, fixed_transaction_inr: v.fixedTransaction, commission_rate: percent(v.commission), market_fee_rate: percent(v.marketFee), assumptions: v.notes };
  return { ...scope, decision_at: historicalDate ? `${historicalDate}T12:00:00+05:30` : new Date().toISOString(), total_quantity_quintals: v.quantity, today_price_inr_per_quintal: v.price, today_price_assumption: v.notes, required_net_cash_inr: v.cash, storage_capacity_quintals: v.capacity, decision_increment_quintals: v.increment, market_quantity_step_quintals: v.step, minimum_sale_lot_quintals: v.minimumLot, maximum_horizon_days: 7, risk_tolerance: v.risk, crop_storage_profile: { commodity: scope.commodity, maximum_holding_days: Number(v.capacity) > 0 ? Number(v.limit) : 0, storage_conditions: v.conditions || 'No holding capacity', assumption_source: v.notes }, today_sale_costs: costs,
    holding_options: Number(v.capacity) > 0 ? [{ days: Number(v.days), daily_loss_fractions: Array(Number(v.days)).fill(percent(v.loss)), daily_storage_inr_per_quintal: Array(Number(v.days)).fill(v.storage), fixed_storage_inr: v.storageFixed, storage_payment: v.payment, future_sale_costs: costs, assumptions: v.conditions, realization_multiplier: v.realization, price_basis_assumption: v.notes, adverse_inr_per_quintal: v.adverse, adverse_assumption: 'Farmer-entered stress price, not a predicted quantile' }] : [] };
}
