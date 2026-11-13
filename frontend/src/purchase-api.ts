import { saleAPI } from './sale-api';
import type { components } from './generated/api-schema';
export type PurchaseTerms = components['schemas']['OfferTerms'];
export interface PurchaseOffer { id: number; commodity_name: string; business_id: number; version: number; status: string; terms: PurchaseTerms; quantity_required: string; quantity_reserved: string; quantity_committed: string; quantity_remaining: string; price_updated_at: string; created_at: string; request_count: number; history?: {action: string; revision: number; created_at: string; snapshot: Record<string, unknown>}[]; price_history?: {price: string; kind: string; revision: number; created_at: string}[] }
export interface PurchaseResponse { id: number; kind: string; quantity: string; price: string; arrival_at: string; expires_at: string; terms: PurchaseTerms & {payment_terms: string; message?: string; confirmed_price?: string}; created_at: string }
export interface PrivateRequest { id: number; public_id: string; offer_id: number; farmer_name: string; farmer_phone: string | null; quantity: string; expected_price: string; arrival_at: string; created_at: string; status: string; version: number; details: {variety: string; grade: string; message: string}; responses: PurchaseResponse[]; history: {action: string; created_at: string; details: Record<string, unknown>}[] }
export interface PurchaseAnalytics { offer_count: number; requested_quantity: string; confirmed_quantity: string; reserved_quantity: string; remaining_quantity: string; average_offered_price: string | null; incoming_requests: number; accepted_requests: number; upcoming_arrivals: {request_id: number; arrival_at: string; quantity: string; price: string}[]; completed_purchases: number; completion_recording_available: boolean; appointment_booking_available: boolean }
export interface PurchaseNote { id: number; offer_id: number; request_id: number | null; message: {en: string; kn: string}; created_at: string; read_at: string | null }
export interface PrivateRateOffer {
  offer_id: number;
  version: number;
  business_id: number;
  business_name: string;
  business_type: 'PRIVATE_MANDI' | 'PRIVATE_BUYER';
  commodity_id: number;
  commodity_name: string;
  variety: string;
  grade: string;
  quality_standards: string;
  offered_price: string;
  price_kind: 'FIRM' | 'INDICATIVE' | 'NEGOTIABLE';
  price_basis: string;
  minimum_price: string | null;
  maximum_price: string | null;
  quantity_required: string;
  quantity_remaining: string;
  minimum_quantity: string;
  maximum_quantity: string;
  address: string;
  purchasing_centre: string;
  district: string;
  state: string;
  transport: string;
  pickup_charge: string | null;
  unloading_charge: string | null;
  charge_basis: string;
  known_deductions: string;
  has_unknown_costs: boolean;
  estimated_net_realization: string;
  apmc_reference_modal_price: number | null;
  price_updated_at: string;
  expires_at: string;
  price_valid_until: string;
  arrival_dates: string[];
  created_at: string;
}

export const purchaseAPI = {
  offers: (id: number, offset = 0) => saleAPI<PurchaseOffer[]>(`/business/offers?business_id=${id}&offset=${offset}`),
  offer: (id: number) => saleAPI<PurchaseOffer>(`/business/offers/${id}`),
  requests: (id: number, offset = 0) => saleAPI<PrivateRequest[]>(`/business/requests?business_id=${id}&offset=${offset}`),
  analytics: (id: number) => saleAPI<PurchaseAnalytics>(`/business/analytics?business_id=${id}`),
  notes: (id: number, offset = 0) => saleAPI<{unread: number; items: PurchaseNote[]}>(`/business/purchase-notifications?business_id=${id}&offset=${offset}`),
  privateRates: (params: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') query.set(k, String(v));
    }
    const qStr = query.toString();
    return saleAPI<PrivateRateOffer[]>(`/private-rates${qStr ? `?${qStr}` : ''}`);
  },
  submitFarmerRequest: (offerId: number, body: unknown, key: string) =>
    saleAPI<PrivateRequest>(`/private-purchases/offers/${offerId}/requests`, body, key),
  confirmFarmerRequest: (requestId: number, version: number) =>
    saleAPI<PrivateRequest>(`/private-purchases/requests/${requestId}/confirm`, { version }),
  rejectFarmerRequest: (requestId: number, version: number, reason: string) =>
    saleAPI<PrivateRequest>(`/private-purchases/requests/${requestId}/reject`, { version, reason }),
  recordArrival: (requestId: number, version: number, notes = '') =>
    saleAPI<PrivateRequest>(`/business/requests/${requestId}/arrive`, { version, notes }),
  completePurchase: (requestId: number, body: unknown) =>
    saleAPI<PrivateRequest>(`/business/requests/${requestId}/complete`, body),
};
