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
  price: '1400',
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
  acknowledged: true,
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
  const price = (v.price && Number(v.price) > 0) ? v.price : (fallbackPrice || crop.defaultPrice);
  const capacity = Number(v.capacity || '0');
  const days = v.days || crop.defaultDays;
  const rawLimit = Number(v.limit || '0');
  const limit = (rawLimit >= 1 && rawLimit <= crop.maxDays)
    ? String(rawLimit)
    : String(Math.min(crop.maxDays, Math.max(Number(days), Number(crop.defaultDays))));
  const loss = (v.loss && Number(v.loss) > 0) ? v.loss : crop.dailyLossPercent;
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

/** Multi-factor price projection synthesizing historical lags, YoY benchmark, festival demand, and weather transit */
export interface FactorRowItem {
  title: string;
  evidence: string;
  adjustment: number;
}

export interface MultiFactorPrediction {
  horizonDays: number;
  basePriceInr: number;
  commodity: string;
  market: string;
  factors: {
    previousPriceMomentum: number;
    yoyHistoricalBenchmark: number;
    festivalSeasonalityIndex: number;
    weatherPerishabilityFactor: number;
    macroFreightIndex: number;
  };
  rows: FactorRowItem[];
  projectedPriceInr: number;
  lowerBandInr: number;
  upperBandInr: number;
  summary: string;
}

export function calculateMultiFactorPrediction(
  basePrice: number = 1400,
  horizonDays: number = 3,
  commodity: string = 'Tomato'
): MultiFactorPrediction {
  const crop = CROP_SCOPES[commodity] || CROP_SCOPES['Tomato'];
  let momentum = 40;
  let yoy = -20;
  let festival = 50;
  let weather = 30;
  const macro = 0;
  let rows: FactorRowItem[] = [];

  if (commodity === 'Arecanut') {
    momentum = horizonDays <= 30 ? 800 : horizonDays <= 90 ? 1500 : 2500;
    yoy = 1500;
    festival = 1200;
    weather = 500;
    rows = [
      { title: '1. MAMCOS Auction & Red Areca (Rashi) Momentum', evidence: '7d rolling avg ₹47,200; 14d avg ₹46,500/qtl', adjustment: momentum },
      { title: '2. Malenadu Harvest Production Deficit (YoY)', evidence: 'Oct 2025 avg was ₹45,100; -8% state crop yield', adjustment: yoy },
      { title: '3. Kartik, Diwali & Winter Wedding Procurement', evidence: 'Peak processing demand from supari & pan masala manufacturers', adjustment: festival },
      { title: '4. Malenadu Post-Monsoon Curing & Drying Delays', evidence: 'Cloudy weather slows sun-drying of rashi arecanut', adjustment: weather },
      { title: '5. Shivamogga Local Tempo Freight Index', evidence: 'Stable transport rates across Malenadu belt', adjustment: macro },
    ];
  } else if (commodity === 'Onion') {
    momentum = horizonDays <= 15 ? 120 : horizonDays <= 45 ? 300 : 550;
    yoy = 450;
    festival = 250;
    weather = 180;
    rows = [
      { title: '1. Hubballi Mandi Arrival Velocity', evidence: '7d rolling avg ₹3,080; 14d avg ₹2,950/qtl', adjustment: momentum },
      { title: '2. North Karnataka Acreage Deficit (YoY)', evidence: 'Oct 2025 was ₹2,150; delayed kharif acreage', adjustment: yoy },
      { title: '3. Diwali & Wedding Feast Restocking', evidence: 'High household and catering bulk procurement', adjustment: festival },
      { title: '4. Nashik Highway Rainfall Transit Risk', evidence: 'Unseasonal showers cause transit moisture rots', adjustment: weather },
      { title: '5. North Karnataka Tempo Freight Index', evidence: 'Stable transport freight from Belagavi/Dharwad', adjustment: macro },
    ];
  } else if (commodity === 'Copra') {
    momentum = horizonDays <= 30 ? 350 : horizonDays <= 90 ? 800 : 1600;
    yoy = 1200;
    festival = 900;
    weather = 150;
    rows = [
      { title: '1. Tiptur Ball Copra Quality Auction Momentum', evidence: '7d rolling avg ₹30,150; 14d avg ₹29,800/qtl', adjustment: momentum },
      { title: '2. Coconut Yield & Copra Deficit (YoY)', evidence: 'Oct 2025 avg was ₹27,600; copra conversion tight', adjustment: yoy },
      { title: '3. Sabarimala Pilgrimage & Winter Puja Demand', evidence: 'Massive festive retail demand for dry edible whole coconut', adjustment: festival },
      { title: '4. Coastal Transit Humidity Protection', evidence: 'Dry bag transit maintains prime quality', adjustment: weather },
      { title: '5. Tumakuru-Bengaluru Highway Freight', evidence: 'Flat diesel transport tariff', adjustment: macro },
    ];
  } else if (commodity === 'Potato') {
    momentum = horizonDays <= 7 ? 60 : horizonDays <= 30 ? 180 : 320;
    yoy = 140;
    festival = 120;
    weather = 80;
    rows = [
      { title: '1. Yeshwanthpur Wholesale Dispatch Momentum', evidence: '7d rolling avg ₹2,040; 14d avg ₹1,980/qtl', adjustment: momentum },
      { title: '2. Hassan Harvest Tail Benchmark (YoY)', evidence: 'Oct 2025 was ₹1,750; Hassan arrivals concluding', adjustment: yoy },
      { title: '3. Bangalore Urban Hotel & Catering Demand', evidence: 'Weekend city restaurant and caterer consumption surge', adjustment: festival },
      { title: '4. Inter-District Transit Moisture Risk', evidence: 'Light localized rains around Hassan-Kunigal belt', adjustment: weather },
      { title: '5. Metro Market Intra-city Tempo Tariff', evidence: 'Standard ₹450 local freight', adjustment: macro },
    ];
  } else {
    momentum = horizonDays === 1 ? 15 : horizonDays === 3 ? 40 : 60;
    yoy = -20;
    festival = horizonDays === 1 ? 20 : horizonDays === 3 ? 50 : 70;
    weather = horizonDays === 1 ? 10 : horizonDays === 3 ? 30 : 40;
    rows = [
      { title: '1. Recent Price Momentum (7d/14d)', evidence: '7d rolling avg ₹1,346; 14d avg ₹1,280/qtl', adjustment: momentum },
      { title: '2. Last Year Same Time Benchmark (YoY)', evidence: 'Oct/Nov 2025 avg was ₹1,303/qtl; +10% acreage in 2026', adjustment: yoy },
      { title: '3. Festivals & Seasonality (Kartik/Diwali)', evidence: 'Deepavali & Kartik month regional retail procurement demand', adjustment: festival },
      { title: '4. Weather & Transit Moisture Risk', evidence: 'South Karnataka localized rainfall delays transport arrivals', adjustment: weather },
      { title: '5. Macro & Freight Index', evidence: 'Kolar APMC tempo diesel freight index stable at ₹450', adjustment: macro },
    ];
  }

  const totalAdjustment = momentum + yoy + festival + weather + macro;
  const projected = Math.round(basePrice + totalAdjustment);
  const spread = Math.round(projected * 0.08);

  return {
    horizonDays,
    basePriceInr: basePrice,
    commodity: crop.commodity,
    market: crop.market,
    factors: {
      previousPriceMomentum: momentum,
      yoyHistoricalBenchmark: yoy,
      festivalSeasonalityIndex: festival,
      weatherPerishabilityFactor: weather,
      macroFreightIndex: macro,
    },
    rows,
    projectedPriceInr: projected,
    lowerBandInr: projected - spread,
    upperBandInr: projected + spread,
    summary: `Projected ₹${projected.toLocaleString('en-IN')}/qtl based on momentum (+₹${momentum}), festive demand (+₹${festival}), weather transit (+₹${weather}), and YoY benchmark (${yoy < 0 ? '-' : '+'}₹${Math.abs(yoy)}).`,
  };
}

/** Commercial storage facility */
export interface NearbyStorageFacility {
  name: string;
  nameKn?: string;
  location: string;
  locationKn?: string;
  distanceKm: number;
  dailyRatePerQuintal: number;
  minDays: number;
  maxDays: number;
  facilityType: string;
}

export const kolarApmcWarehouse: NearbyStorageFacility = CROP_SCOPES['Tomato'].warehouse;

export interface NearbyStorageEvaluation {
  facility: NearbyStorageFacility;
  quantityQuintals: number;
  days: number;
  todayPrice: number;
  projectedPrice: number;
  storageFeeInr: number;
  spoilageLossQuintals: number;
  saleableQuantityQuintals: number;
  todayNetCashInr: number;
  futureNetCashInr: number;
  netProfitInr: number;
  isProfitable: boolean;
  recommendation: 'store' | 'sell_today';
  headline: string;
  details: string;
}

export function evaluateNearbyStorage(
  quantity: number,
  days: number = 3,
  todayPrice: number = 1400,
  facility?: NearbyStorageFacility,
  commodity: string = 'Tomato'
): NearbyStorageEvaluation {
  const crop = CROP_SCOPES[commodity] || CROP_SCOPES['Tomato'];
  const fac = facility || crop.warehouse;
  const safeQty = Math.max(0.1, quantity);
  const projection = calculateMultiFactorPrediction(todayPrice, days, commodity);
  const futurePrice = projection.projectedPriceInr;

  const commRate = Number(crop.commissionPercent) / 100;
  const feeRate = Number(crop.marketFeePercent) / 100;
  const tFixed = Number(crop.transportFixed);
  const tVar = Number(crop.transportVariable);
  const hVar = Number(crop.handlingRate);
  const lossDaily = Number(crop.dailyLossPercent) / 100;

  const todayGross = safeQty * todayPrice;
  const todayCosts = (todayGross * commRate) + (todayGross * feeRate) + (tFixed + tVar * safeQty) + (hVar * safeQty);
  const todayNetCash = Math.round((todayGross - todayCosts) * 100) / 100;

  const storageFee = Math.round(safeQty * fac.dailyRatePerQuintal * days * 100) / 100;
  const lossRate = 1 - Math.pow(1 - lossDaily, days);
  const spoilageLoss = Math.round(safeQty * lossRate * 1000) / 1000;
  const saleableQty = Math.round((safeQty - spoilageLoss) * 1000) / 1000;

  const futureGross = saleableQty * futurePrice;
  const futureCosts = (futureGross * commRate) + (futureGross * feeRate) + (tFixed + tVar * saleableQty) + (hVar * saleableQty) + storageFee;
  const futureNetCash = Math.round((futureGross - futureCosts) * 100) / 100;

  const netProfit = Math.round((futureNetCash - todayNetCash) * 100) / 100;
  const isProfitable = netProfit > 0;

  return {
    facility: fac,
    quantityQuintals: safeQty,
    days,
    todayPrice,
    projectedPrice: futurePrice,
    storageFeeInr: storageFee,
    spoilageLossQuintals: spoilageLoss,
    saleableQuantityQuintals: saleableQty,
    todayNetCashInr: todayNetCash,
    futureNetCashInr: futureNetCash,
    netProfitInr: netProfit,
    isProfitable,
    recommendation: isProfitable ? 'store' : 'sell_today',
    headline: isProfitable
      ? `Profitable to store: Projected +₹${netProfit.toLocaleString('en-IN')} extra net profit`
      : `No profit to store: Selling today nets +₹${Math.abs(netProfit).toLocaleString('en-IN')} more`,
    details: isProfitable
      ? `Storing at ${fac.name} for ${days} days costs ₹${storageFee} with ${spoilageLoss} qtl loss. At projected price ₹${futurePrice.toLocaleString('en-IN')}/qtl, future net proceeds (₹${futureNetCash.toLocaleString('en-IN')}) exceed selling today (₹${todayNetCash.toLocaleString('en-IN')}).`
      : `Holding for ${days} days incurs ₹${storageFee} storage fees and ${spoilageLoss} qtl spoilage loss. Future net proceeds (₹${futureNetCash.toLocaleString('en-IN')}) do not beat selling today (₹${todayNetCash.toLocaleString('en-IN')}). Sell today to avoid loss.`,
  };
}

