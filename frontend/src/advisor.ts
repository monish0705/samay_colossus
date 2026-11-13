import { z } from 'zod';
import type { RecommendInput, Scope } from './api';
import { CROP_SCOPES } from './api';

export interface AdvisorValues {
  quantity: string;
  cash: string;
  price: string;
  capacity: string;
  days: string;
  limit: string;
  loss: string;
  storage: string;
  storageFixed: string;
  payment: 'today' | 'later';
  transportFixed: string;
  transportVariable: string;
  handling: string;
  fixedTransaction: string;
  commission: string;
  marketFee: string;
  increment: string;
  minimumLot: string;
  step: string;
  risk: 'conservative' | 'balanced' | 'aggressive';
  notes: string;
  conditions: string;
  realization: string;
  adverse: string;
  acknowledged: boolean;
  example: boolean;
  scenarioPrice?: string;
}

export const blankAdvisor: AdvisorValues = {
  quantity: '',
  cash: '0',
  price: '',
  capacity: '0',
  days: '3',
  limit: '3',
  loss: '1.5',
  storage: '0',
  storageFixed: '0',
  payment: 'later',
  transportFixed: '450',
  transportVariable: '25',
  handling: '15',
  fixedTransaction: '0',
  commission: '5',
  marketFee: '1.5',
  increment: '1',
  minimumLot: '1',
  step: '0.01',
  risk: 'conservative',
  notes: 'Farmer quote at Kolar APMC',
  conditions: 'Standard ventilated crate storage',
  realization: '1',
  adverse: '0',
  acknowledged: false,
  example: false,
};

export const exampleAdvisor: AdvisorValues = {
  ...blankAdvisor,
  quantity: '20',
  cash: '10000',
  price: '1000',
  transportFixed: '100',
  transportVariable: '10',
  handling: '0',
  commission: '5',
  marketFee: '0',
  notes: 'EXAMPLE_ONLY demonstration quote and costs, not live prices',
  acknowledged: true,
  example: true,
};

const amount = z.string().regex(/^\d+(\.\d{1,4})?$/, 'Enter a nonnegative number with up to four decimal places.').refine(v => Number(v) <= 1e9, 'Value is too large.');

export function getEffectiveAdvisorValues(v: AdvisorValues, fallbackPrice?: string, commodity: string = 'Tomato'): AdvisorValues {
  const crop = CROP_SCOPES[commodity] || CROP_SCOPES['Tomato'];
  const price = (v.price && Number(v.price) > 0) ? v.price : (fallbackPrice || '');
  const capacity = Number(v.capacity || '0');
  const days = v.days || crop.defaultDays;
  const rawLimit = Number(v.limit || '0');
  const limit = (rawLimit >= 1 && rawLimit <= crop.maxDays)
    ? String(rawLimit)
    : String(Math.min(crop.maxDays, Math.max(Number(days), Number(crop.defaultDays))));
  const loss = (v.loss !== '' && v.loss !== undefined) ? v.loss : crop.dailyLossPercent;
  const commission = (v.commission !== '' && v.commission !== undefined) ? v.commission : crop.commissionPercent;
  const marketFee = (v.marketFee !== '' && v.marketFee !== undefined) ? v.marketFee : crop.marketFeePercent;
  const transportFixed = (v.transportFixed !== '' && v.transportFixed !== undefined) ? v.transportFixed : crop.transportFixed;
  const transportVariable = (v.transportVariable !== '' && v.transportVariable !== undefined) ? v.transportVariable : crop.transportVariable;
  const handling = (v.handling !== '' && v.handling !== undefined) ? v.handling : crop.handlingRate;
  const fixedTransaction = v.fixedTransaction || '0';
  const increment = v.increment || '1';
  const minimumLot = v.minimumLot || '1';
  const step = v.step || '0.01';
  const notes = (v.notes && v.notes.trim().length >= 3) ? v.notes.trim() : `Farmer quote at ${crop.market}`;
  const conditions = (v.conditions && v.conditions.trim().length >= 3) ? v.conditions.trim() : crop.warehouse.facilityType;

  return {
    ...v,
    price,
    capacity: String(capacity),
    days: days as AdvisorValues['days'],
    limit,
    loss,
    commission,
    marketFee,
    transportFixed,
    transportVariable,
    handling,
    fixedTransaction,
    increment,
    minimumLot,
    step,
    notes,
    conditions,
    acknowledged: v.acknowledged ?? true,
  };
}

export function validateAdvisor(v: AdvisorValues, commodity: string = 'Tomato'): Record<string, string> {
  const crop = CROP_SCOPES[commodity] || CROP_SCOPES['Tomato'];
  const effective = getEffectiveAdvisorValues(v, undefined, commodity);
  if (!effective.price || Number(effective.price) <= 0) return { price: 'Enter a verified buyer quote or review an available observed reference.' };
  const numeric = ['quantity', 'cash', 'price', 'capacity', 'increment', 'minimumLot', 'step', 'transportFixed', 'transportVariable', 'handling', 'fixedTransaction', 'commission', 'marketFee', 'storage', 'storageFixed', 'adverse', 'realization'] as const;
  const errors: Record<string, string> = {};

  if (!v.quantity || v.quantity === '' || Number(v.quantity) <= 0) {
    errors.quantity = 'Enter a value greater than zero.';
  } else if (!amount.safeParse(v.quantity).success) {
    errors.quantity = amount.safeParse(v.quantity).error?.issues[0]?.message || 'Enter a nonnegative number with up to four decimal places.';
  }

  if (v.cash !== '' && !amount.safeParse(v.cash).success) {
    errors.cash = 'Enter a nonnegative number with up to four decimal places.';
  }

  if (v.price !== '' && v.price !== undefined) {
    if (Number(v.price) <= 0) {
      errors.price = 'Enter a value greater than zero.';
    } else if (!amount.safeParse(v.price).success) {
      errors.price = 'Enter a nonnegative number with up to four decimal places.';
    }
  }

  for (const key of numeric) {
    if (['quantity', 'cash', 'price'].includes(key)) continue;
    const val = effective[key];
    const parsed = amount.safeParse(val || '0');
    if (!parsed.success) errors[key] = parsed.error.issues[0].message;
  }

  for (const key of ['increment', 'minimumLot', 'step'] as const) {
    if (Number(effective[key]) <= 0) errors[key] = 'Enter a value greater than zero.';
  }

  if (Number(effective.quantity || 0) > 100000 || Number(effective.capacity || 0) > 100000) {
    errors.quantity = 'Quantity/capacity cannot exceed 100,000 quintals.';
  }
  if (Number(effective.commission || '0') + Number(effective.marketFee || '0') >= 100) {
    errors.commission = 'Combined percentage charges must be below 100%.';
  }
  if (!(Number(effective.realization || '1') > 0 && Number(effective.realization || '1') <= 2)) {
    errors.realization = 'Use a realization factor greater than 0 and at most 2.';
  }
  if (v.notes && v.notes.trim().length > 0 && v.notes.trim().length < 3) {
    errors.notes = 'Describe where your buyer quote and costs came from.';
  }
  if (!effective.acknowledged) {
    errors.acknowledged = 'Confirm these assumptions before calculating.';
  }

  if (Number(effective.capacity) > 0) {
    const limit = effective.limit;
    if (!/^\d+$/.test(limit) || Number(limit) < 1 || Number(limit) > crop.maxDays) {
      errors.limit = `Enter a verified crop holding limit from 1 to ${crop.maxDays} days.`;
    }
    if (Number(effective.days) > Number(limit)) {
      errors.days = 'The planned date exceeds your crop holding limit.';
    }
    const loss = effective.loss;
    if (!amount.safeParse(loss).success || Number(loss) > 100) {
      errors.loss = 'Enter an assumed daily loss from 0 to 100%.';
    }
    if (v.conditions && v.conditions.trim().length > 0 && v.conditions.trim().length < 3) {
      errors.conditions = 'Describe storage conditions and the source of your loss estimate.';
    }
  }

  if (v.scenarioPrice && (!amount.safeParse(v.scenarioPrice).success || Number(effective.adverse) > Number(v.scenarioPrice))) errors.scenarioPrice = 'Enter a nonnegative scenario price at least as large as the adverse price.';

  for (const key of ['quantity', 'capacity', 'increment', 'minimumLot', 'step'] as const) {
    if (effective[key] && !/^\d+(\.\d{1,3})?$/.test(effective[key])) {
      errors[key] = 'Quantities support up to three decimal places.';
    }
  }
  const step = Math.round(Number(effective.step || '0.01') * 1000);
  if (step > 0) {
    for (const key of ['quantity', 'increment', 'minimumLot'] as const) {
      if (effective[key] && Math.round(Number(effective[key]) * 1000) % step) {
        errors[key] = 'Use a multiple of the market sale step.';
      }
    }
  }
  return errors;
}

export function buildRecommendation(v: AdvisorValues, scope: Scope, historicalDate?: string | null): RecommendInput {
  const crop = CROP_SCOPES[scope.commodity] || CROP_SCOPES['Tomato'];
  const effectiveValues = getEffectiveAdvisorValues(v, undefined, scope.commodity);
  const errors = validateAdvisor(effectiveValues, scope.commodity);
  if (Object.keys(errors).length) throw new Error(Object.values(errors)[0]);
  const percent = (s: string) => (Number(s || '0') / 100).toFixed(6);
  const notes = effectiveValues.notes;
  const costs = {
    fixed_transport_inr: effectiveValues.transportFixed,
    transport_inr_per_quintal: effectiveValues.transportVariable,
    handling_inr_per_quintal: effectiveValues.handling,
    fixed_transaction_inr: effectiveValues.fixedTransaction,
    commission_rate: percent(effectiveValues.commission),
    market_fee_rate: percent(effectiveValues.marketFee),
    assumptions: notes,
  };
  const capacity = Number(effectiveValues.capacity || '0');
  const holding = capacity > 0 ? [{
    days: Number(effectiveValues.days || crop.defaultDays),
    daily_loss_fractions: Array(Number(effectiveValues.days || crop.defaultDays)).fill(percent(effectiveValues.loss || crop.dailyLossPercent)),
    daily_storage_inr_per_quintal: Array(Number(effectiveValues.days || crop.defaultDays)).fill(effectiveValues.storage || crop.dailyStorageRate),
    fixed_storage_inr: effectiveValues.storageFixed || '0',
    storage_payment: effectiveValues.payment,
    future_sale_costs: costs,
    assumptions: effectiveValues.conditions || crop.warehouse.facilityType,
    realization_multiplier: effectiveValues.realization || '1',
    price_basis_assumption: notes,
    adverse_inr_per_quintal: effectiveValues.adverse || '0',
    adverse_assumption: 'Farmer-entered stress price, not a predicted quantile',
    ...(effectiveValues.scenarioPrice ? { scenario_price_inr_per_quintal: effectiveValues.scenarioPrice } : {})
  }] : [];

  return {
    ...scope,
    decision_at: historicalDate ? `${historicalDate}T12:00:00+05:30` : new Date().toISOString(),
    total_quantity_quintals: effectiveValues.quantity,
    today_price_inr_per_quintal: effectiveValues.price,
    today_price_assumption: notes,
    required_net_cash_inr: effectiveValues.cash || '0',
    storage_capacity_quintals: effectiveValues.capacity || '0',
    decision_increment_quintals: effectiveValues.increment || '1',
    market_quantity_step_quintals: effectiveValues.step || '0.01',
    minimum_sale_lot_quintals: effectiveValues.minimumLot || '1',
    maximum_horizon_days: crop.maxDays,
    risk_tolerance: effectiveValues.risk || 'conservative',
    crop_storage_profile: {
      commodity: scope.commodity,
      maximum_holding_days: capacity > 0 ? Number(effectiveValues.limit || crop.defaultDays) : 0,
      storage_conditions: effectiveValues.conditions?.trim() || 'No holding capacity',
      assumption_source: notes,
    },
    today_sale_costs: costs,
    holding_options: holding,
  };
}

