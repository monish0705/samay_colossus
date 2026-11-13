import createClient from 'openapi-fetch';
import type { paths, components } from './generated/api-schema';
import { config } from './config';
export type Schema<K extends keyof components['schemas']> = components['schemas'][K];
export type Prediction = Schema<'PredictionResponse'>;
export type Recommendation = Schema<'RecommendationResponse'>;
export const getDecisionPlan = (result: Recommendation) => result.decision_support?.plan ?? result.optimization.recommended_plan;
export type RecommendInput = Omit<Schema<'RecommendRequest'>, 'holding_options'> & { holding_options: (Omit<Schema<'RecommendationHolding'>, 'scenarios'> & { scenario_price_inr_per_quintal?: string })[] };
export type Observation = Schema<'PriceResponse'>;
export type Scope = { market: string; commodity: string; variety: string; grade: string };
export const defaultScope: Scope = { market: 'Kolar APMC', commodity: 'Tomato', variety: 'tomato', grade: 'local' };

export interface CropScopeConfig {
  id: string;
  commodity: string;
  market: string;
  variety: string;
  grade: string;
  titleEn: string;
  titleKn: string;
  marketNameKn: string;
  cropNameKn: string;
  icon: string;
  tag: string;
  defaultQuantity: string;
  defaultCash: string;
  durabilityTextEn: string;
  durabilityTextKn: string;
  holdingOptions: string[];
  maxDays: number;
  defaultDays: string;
  dailyLossPercent: string;
  dailyStorageRate: string;
  commissionPercent: string;
  marketFeePercent: string;
  transportFixed: string;
  transportVariable: string;
  handlingRate: string;
  warehouse: {
    facilityType: string;
  };
}

export const CROP_SCOPES: Record<string, CropScopeConfig> = {
  'Tomato': {
    id: 'Tomato',
    maxDays: 7,
    commodity: 'Tomato',
    market: 'Kolar APMC',
    variety: 'tomato',
    grade: 'local',
    titleEn: 'Tomato · Kolar APMC',
    titleKn: 'ಟೊಮೇಟೊ · ಕೋಲಾರ ಎಪಿಎಂಸಿ',
    marketNameKn: 'ಕೋಲಾರ ಎಪಿಎಂಸಿ',
    cropNameKn: 'ಟೊಮೇಟೊ',
    icon: '🍅',
    tag: 'Perishable · 1-7 Days',
    defaultQuantity: '30',
    defaultCash: '10000',
    durabilityTextEn: 'Perishable: 1 to 7 days shelf holding',
    durabilityTextKn: 'ಬೇಗನೆ ಹಾಳಾಗುವ ಬೆಳೆ: 1 ರಿಂದ 7 ದಿನಗಳ ದಾಸ್ತಾನು',
    holdingOptions: ['1', '3', '7'],
    defaultDays: '3',
    dailyLossPercent: '1.5',
    dailyStorageRate: '5.0',
    commissionPercent: '5',
    marketFeePercent: '1.5',
    transportFixed: '450',
    transportVariable: '25',
    handlingRate: '15',
    warehouse: {
      facilityType: 'Ventilated crated produce storage',
    },
  },
  'Arecanut': {
    id: 'Arecanut',
    maxDays: 730,
    commodity: 'Arecanut',
    market: 'Shivamogga Mandi',
    variety: 'rashi',
    grade: 'local',
    titleEn: 'Arecanut (Betel Nut) · Shivamogga APMC',
    titleKn: 'ಅಡಿಕೆ (ರಾಶಿ) · ಶಿವಮೊಗ್ಗ ಎಪಿಎಂಸಿ',
    marketNameKn: 'ಶಿವಮೊಗ್ಗ ಎಪಿಎಂಸಿ',
    cropNameKn: 'ಅಡಿಕೆ',
    icon: '🌴',
    tag: 'Very Durable · 2 Months - 2 Years',
    defaultQuantity: '10',
    defaultCash: '100000',
    durabilityTextEn: 'Highly durable dried cash crop: 2 months to 2 years (60 to 730 days)',
    durabilityTextKn: 'ಅತ್ಯಂತ ಬಾಳಿಕೆ ಬರುವ ಒಣ ಬೆಳೆ: 2 ತಿಂಗಳಿಂದ 2 ವರ್ಷಗಳವರೆಗೆ (60 ರಿಂದ 730 ದಿನಗಳು)',
    holdingOptions: ['1', '3', '7', '30', '60', '90', '180', '365', '730'],
    defaultDays: '3',
    dailyLossPercent: '0.02',
    dailyStorageRate: '1.2',
    commissionPercent: '2',
    marketFeePercent: '1.5',
    transportFixed: '800',
    transportVariable: '40',
    handlingRate: '25',
    warehouse: {
      facilityType: 'Dry ventilated gunny godown with humidity control',
    },
  },
  'Onion': {
    id: 'Onion',
    maxDays: 120,
    commodity: 'Onion',
    market: 'Hubballi APMC',
    variety: 'puna',
    grade: 'local',
    titleEn: 'Onion · Hubballi APMC (Amargol)',
    titleKn: 'ಈರುಳ್ಳಿ · ಹುಬ್ಬಳ್ಳಿ ಎಪಿಎಂಸಿ (ಅಮರಗೋಳ)',
    marketNameKn: 'ಹುಬ್ಬಳ್ಳಿ ಎಪಿಎಂಸಿ (ಅಮರಗೋಳ)',
    cropNameKn: 'ಈರುಳ್ಳಿ',
    icon: '🧅',
    tag: 'Medium Holding · 1-4 Months',
    defaultQuantity: '50',
    defaultCash: '35000',
    durabilityTextEn: 'Medium storability: 1 to 4 months (30 to 120 days) in ventilated chawls',
    durabilityTextKn: 'ಮಧ್ಯಮ ದಾಸ್ತಾನು: ಗಾಳಿಯಾಡುವ ಚawಲ್‌ನಲ್ಲಿ 1 ರಿಂದ 4 ತಿಂಗಳು (30 ರಿಂದ 120 ದಿನಗಳು)',
    holdingOptions: ['1', '3', '7', '15', '30', '60', '90', '120'],
    defaultDays: '3',
    dailyLossPercent: '0.25',
    dailyStorageRate: '0.6',
    commissionPercent: '5',
    marketFeePercent: '1.5',
    transportFixed: '500',
    transportVariable: '20',
    handlingRate: '15',
    warehouse: {
      facilityType: 'Bamboo mesh ventilated onion storage',
    },
  },
  'Copra': {
    id: 'Copra',
    maxDays: 365,
    commodity: 'Copra',
    market: 'Tiptur APMC',
    variety: 'other',
    grade: 'local',
    titleEn: 'Copra (Ball Kobbari) · Tiptur APMC',
    titleKn: 'ಕೊಬ್ಬರಿ (ಉಂಡೆ ಕೊಬ್ಬರಿ) · ತಿಪಟೂರು ಎಪಿಎಂಸಿ',
    marketNameKn: 'ತಿಪಟೂರು ಎಪಿಎಂಸಿ',
    cropNameKn: 'ಕೊಬ್ಬರಿ',
    icon: '🥥',
    tag: 'High Storability · 3-12 Months',
    defaultQuantity: '15',
    defaultCash: '100000',
    durabilityTextEn: 'High durability: 3 to 12 months (90 to 365 days) whole dried coconut',
    durabilityTextKn: 'ಹೆಚ್ಚು ಬಾಳಿಕೆ ಬರುವ ಬೆಳೆ: 3 ರಿಂದ 12 ತಿಂಗಳು (90 ರಿಂದ 365 ದಿನಗಳು)',
    holdingOptions: ['1', '3', '7', '30', '60', '90', '180', '270', '365'],
    defaultDays: '3',
    dailyLossPercent: '0.03',
    dailyStorageRate: '1.5',
    commissionPercent: '2',
    marketFeePercent: '1.5',
    transportFixed: '600',
    transportVariable: '30',
    handlingRate: '20',
    warehouse: {
      facilityType: 'Dry ventilated ball copra warehouse',
    },
  },
  'Potato': {
    id: 'Potato',
    maxDays: 180,
    commodity: 'Potato',
    market: 'Bengaluru APMC',
    variety: 'local',
    grade: 'medium',
    titleEn: 'Potato · Bengaluru APMC (Yeshwanthpur)',
    titleKn: 'ಆಲೂಗಡ್ಡೆ · ಬೆಂಗಳೂರು ಎಪಿಎಂಸಿ (ಯಶವಂತಪುರ)',
    marketNameKn: 'ಬೆಂಗಳೂರು ಎಪಿಎಂಸಿ (ಯಶವಂತಪುರ)',
    cropNameKn: 'ಆಲೂಗಡ್ಡೆ',
    icon: '🥔',
    tag: 'Ambient 30d · Cold Storage 3-6 Months',
    defaultQuantity: '40',
    defaultCash: '25000',
    durabilityTextEn: 'Ambient 15 to 30 days; cold storage 3 to 6 months (90 to 180 days)',
    durabilityTextKn: 'ಸಾಮಾನ್ಯ ದಾಸ್ತಾನು 15-30 ದಿನ; ಕೋಲ್ಡ್ ಸ್ಟೋರೇಜ್ 3 ರಿಂದ 6 ತಿಂಗಳು (90-180 ದಿನ)',
    holdingOptions: ['1', '3', '7', '15', '30', '60', '90', '180'],
    defaultDays: '3',
    dailyLossPercent: '0.15',
    dailyStorageRate: '1.8',
    commissionPercent: '5',
    marketFeePercent: '1.5',
    transportFixed: '450',
    transportVariable: '25',
    handlingRate: '15',
    warehouse: {
      facilityType: 'Temperature & humidity controlled cold storage (2°C - 4°C)',
    },
  },
};
const resolvedBaseUrl = config.apiBaseUrl.startsWith('http')
  ? config.apiBaseUrl
  : typeof window !== 'undefined' && window.location?.origin && window.location.origin !== 'null'
    ? `${window.location.origin}${config.apiBaseUrl}`
    : `http://127.0.0.1:8010${config.apiBaseUrl}`;

export const client = createClient<paths>({ baseUrl: resolvedBaseUrl, fetch: async request => {
  const controller = new AbortController();
  const abort = () => controller.abort();
  request.signal.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, 20000);
  try { return await globalThis.fetch(request, { signal: controller.signal }); }
  finally { clearTimeout(timer); request.signal.removeEventListener('abort', abort); }
} });
export class ApiError extends Error { constructor(message: string, public status = 0, public code = 'disconnected', public requestId?: string) { super(message); } }
async function unwrap<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result;
  try { result = await request; } catch (error) { if (error instanceof Error && error.name === 'AbortError') throw error; throw new ApiError('Cannot reach the SAMAY backend. Check the connection and try again.'); }
  if (result.data !== undefined) return result.data;
  const problem = result.error as Partial<Schema<'ErrorEnvelope'>> | undefined;
  throw new ApiError(problem?.error?.message || `Request failed (${result.response.status})`, result.response.status, problem?.error?.code || 'request_failed', problem?.error?.request_id || result.response.headers.get('X-Request-ID') || undefined);
}
export const api = {
  health: (signal?: AbortSignal) => unwrap(client.GET('/api/health', { signal })),
  markets: () => unwrap(client.GET('/api/v1/markets')),
  commodities: () => unwrap(client.GET('/api/v1/commodities')),
  data: () => unwrap(client.GET('/api/v1/data/status')),
  models: () => unwrap(client.GET('/api/v1/models/status')),
  evaluation: (scope: Scope, horizon: number, signal?: AbortSignal) => unwrap(client.GET('/api/v1/models/evaluation', { params: { query: { ...scope, horizon } }, signal })),
  horizons: (scope: Scope, horizon?: number, signal?: AbortSignal) => unwrap(client.GET('/api/v1/models/horizons', { params: { query: { ...scope, horizon } }, signal })),
  history: (scope: Scope, dates: { start_date?: string; end_date?: string } = {}, offset = 0, signal?: AbortSignal) => unwrap(client.GET('/api/v1/prices/history', { params: { query: { ...scope, ...dates, limit: 1000, offset } }, signal })),
  latest: (scope: Scope, signal?: AbortSignal) => unwrap(client.GET('/api/v1/prices/latest', { params: { query: scope }, signal })),
  context: (scope: Scope, days = 7, signal?: AbortSignal) => unwrap(client.GET('/api/v1/context', { params: { query: { market: scope.market, commodity: scope.commodity, days } }, signal })),
  predict: (scope: Scope, horizon: number, signal?: AbortSignal) => unwrap(client.POST('/api/v1/predict', { body: { ...scope, horizon }, signal })),
  recommend: async (body: RecommendInput, signal?: AbortSignal): Promise<Recommendation> => {
    let result;
    try { result = await client.POST('/api/v1/recommend', { body, signal }); } catch { throw new ApiError('Cannot reach the backend. No plan has been calculated.'); }
    if (result.response.status === 409 && result.error && 'optimization' in result.error) return result.error;
    return unwrap(Promise.resolve(result));
  },
};
export const getHealth = api.health;
