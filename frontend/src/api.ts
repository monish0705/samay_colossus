import createClient from 'openapi-fetch';
import type { paths, components } from './generated/api-schema';
import { config } from './config';
export type Schema<K extends keyof components['schemas']> = components['schemas'][K];
export type Prediction = Schema<'PredictionResponse'>;
export type Recommendation = Schema<'RecommendationResponse'>;
export type RecommendInput = Omit<Schema<'RecommendRequest'>, 'holding_options'> & { holding_options: Omit<Schema<'RecommendationHolding'>, 'scenarios'>[] };
export type Observation = Schema<'PriceResponse'>;
export type Scope = { market: string; commodity: string; variety: string; grade: string };
export const defaultScope: Scope = { market: 'Kolar APMC', commodity: 'Tomato', variety: 'tomato', grade: 'local' };
export const client = createClient<paths>({ baseUrl: config.apiBaseUrl, fetch: async request => {
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
  history: (scope: Scope, dates: { start_date?: string; end_date?: string } = {}, offset = 0, signal?: AbortSignal) => unwrap(client.GET('/api/v1/prices/history', { params: { query: { ...scope, ...dates, limit: 1000, offset } }, signal })),
  latest: (scope: Scope, signal?: AbortSignal) => unwrap(client.GET('/api/v1/prices/latest', { params: { query: scope }, signal })),
  predict: (scope: Scope, horizon: 1 | 3 | 7, signal?: AbortSignal) => unwrap(client.POST('/api/v1/predict', { body: { ...scope, horizon }, signal })),
  recommend: async (body: RecommendInput, signal?: AbortSignal): Promise<Recommendation> => {
    let result;
    try { result = await client.POST('/api/v1/recommend', { body, signal }); } catch { throw new ApiError('Cannot reach the backend. No plan has been calculated.'); }
    if (result.response.status === 409 && result.error && 'optimization' in result.error) return result.error;
    return unwrap(Promise.resolve(result));
  },
};
export const getHealth = api.health;
