import { config } from './config';
import type { components } from './generated/api-schema';

export interface SaleUser { id: number; name: string; email: string; role: 'FARMER' | 'MANDI_OWNER' | 'MANDI_STAFF' | 'SYSTEM_ADMIN'; email_verified: boolean; phone_verified: boolean }
export interface SaleMandi { id: number; name: string; online_requests_available: boolean; commodity_ids: number[]; reason: string | null }
export type Offer = components['schemas']['OfferResponse'];
export type Sale = components['schemas']['SaleResponse'];
export interface SaleInput { mandi_id: number; crop_id: number; variety: string; grade: string; total_harvest_quantity: string; requested_quantity: string; expected_price_per_quintal: string; preferred_arrival_at: string; estimated_costs_inr: string; farmer_message: string; contact_sharing_consent: boolean }
export interface SaleNote { id: number; request_id: string; message: { en: string; kn: string }; read_at: string | null; created_at: string; deliveries: { channel: string; status: string; attempts: number; error_reason: string | null }[] }
export interface SaleEvent { id: number; to_status: string; from_status: string | null; created_at: string; details: Record<string, unknown> }
export interface Preferences { email: boolean; sms: boolean; whatsapp: boolean; channels: Record<string, string>; email_verified: boolean; phone_verified: boolean }
export interface StaffMember { user_id: number; market_id: number; name: string; role: string; can_transact: boolean }

export class SaleAPIError extends Error {
  constructor(public status: number, public code: string) { super(code); }
}
export async function saleAPI<T>(path: string, body?: unknown, key?: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}/api/v1${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-SAMAY-Action': '1', ...(key ? { 'Idempotency-Key': key } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(20000),
  });
  const data = await response.json();
  if (!response.ok) throw new SaleAPIError(response.status, data.error?.message || data.detail || 'Request failed');
  return data as T;
}
