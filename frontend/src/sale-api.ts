import { config } from './config';
import type { components } from './generated/api-schema';

export interface SaleUser { id: number; name: string; email: string; role: 'FARMER' | 'MANDI_OWNER' | 'MANDI_STAFF' | 'SYSTEM_ADMIN'; roles?: string[]; email_verified: boolean; phone_verified: boolean; token?: string }
export interface SaleMandi { id: number; name: string; online_requests_available: boolean; commodity_ids: number[]; can_save_request?: boolean; reason: string | null }
export type Offer = components['schemas']['OfferResponse'];
export type Sale = components['schemas']['SaleResponse'];
export interface SaleInput { mandi_id: number; crop_id: number; variety: string; grade: string; total_harvest_quantity: string; requested_quantity: string; expected_price_per_quintal?: string; use_mandi_price?: boolean; preferred_arrival_at: string; estimated_costs_inr: string; farmer_message: string; contact_sharing_consent: boolean }
export interface SaleNote { id: number; request_id: string; message: { en: string; kn: string }; read_at: string | null; created_at: string; deliveries: { channel: string; status: string; attempts: number; error_reason: string | null }[] }
export interface SaleEvent { id: number; to_status: string; from_status: string | null; created_at: string; details: Record<string, unknown> }
export interface Preferences { email: boolean; sms: boolean; whatsapp: boolean; channels: Record<string, string>; email_verified: boolean; phone_verified: boolean }
export interface StaffMember { user_id: number; market_id: number; name: string; role: string; can_transact: boolean }

export class SaleAPIError extends Error {
  constructor(public status: number, public code: string, public details?: Record<string, unknown>) { super(code); }
}

let savedToken: string | null = typeof window !== 'undefined' ? localStorage.getItem('samay_token') : null;

export function setStoredToken(token: string | null) {
  savedToken = token;
  if (typeof window !== 'undefined') {
    if (token) localStorage.setItem('samay_token', token);
    else localStorage.removeItem('samay_token');
  }
}

export function getStoredToken(): string | null {
  if (!savedToken && typeof window !== 'undefined') {
    savedToken = localStorage.getItem('samay_token');
  }
  return savedToken;
}

export async function saleAPI<T>(path: string, body?: unknown, key?: string, method?: 'POST' | 'PUT'): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-SAMAY-Action': '1',
    ...(key ? { 'Idempotency-Key': key } : {}),
    ...(token ? { 'X-SAMAY-Token': token, 'Authorization': `Bearer ${token}` } : {}),
  };

  let response = await fetch(`${config.apiBaseUrl}/api/v1${path}`, {
    method: body === undefined ? 'GET' : (method || 'POST'),
    credentials: 'include',
    cache: 'no-store',
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(20000),
  });

  // If unauthenticated on serverless cold-start or fresh instance, auto-recover with demo session and retry once
  if (response.status === 401 && !path.startsWith('/auth/')) {
    try {
      const demoRes = await fetch(`${config.apiBaseUrl}/api/v1/auth/demo-login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-SAMAY-Action': '1' },
      });
      if (demoRes.ok) {
        const demoData = await demoRes.json();
        if (demoData?.token) {
          setStoredToken(demoData.token);
          headers['X-SAMAY-Token'] = demoData.token;
          headers['Authorization'] = `Bearer ${demoData.token}`;
        }
        window.dispatchEvent(new Event('samay-auth-changed'));
        response = await fetch(`${config.apiBaseUrl}/api/v1${path}`, {
          method: body === undefined ? 'GET' : (method || 'POST'),
          credentials: 'include',
          cache: 'no-store',
          headers,
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
          signal: AbortSignal.timeout(20000),
        });
      }
    } catch {
      // Continue to handle response normally
    }
  }

  const text = await response.text();
  let data: any = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    if (!response.ok) {
      throw new SaleAPIError(response.status, text || `Server error (${response.status})`);
    }
  }

  if (!response.ok) {
    let msg = data?.error?.message || data?.detail || `Request failed (${response.status})`;
    if (data?.error?.details?.fields && Array.isArray(data.error.details.fields) && data.error.details.fields.length > 0) {
      const fieldMsgs = data.error.details.fields.map((f: { message?: string; type?: string }) => f.message || f.type).filter(Boolean);
      if (fieldMsgs.length > 0) {
        msg = fieldMsgs.join('. ');
      }
    }
    throw new SaleAPIError(response.status, msg, data?.error?.details);
  }

  if (data && typeof data === 'object' && 'token' in data && typeof (data as { token?: unknown }).token === 'string') {
    setStoredToken((data as { token: string }).token);
  }
  if (path === '/auth/logout') {
    setStoredToken(null);
  }
  if (/^\/auth\/(login|register|logout|demo-login)$/.test(path)) window.dispatchEvent(new Event('samay-auth-changed'));
  return data as T;
}
