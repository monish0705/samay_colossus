import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SaleWorkspace } from './SalePages';
import { setLanguage } from './i18n';
import { saleAPI, SaleAPIError } from './sale-api';

vi.mock('./sale-api', async () => ({ ...await vi.importActual('./sale-api'), saleAPI: vi.fn() }));
vi.mock('./api', async () => ({ ...await vi.importActual('./api'), api: { commodities: async () => [{ id: 2, name: 'Copra' }, { id: 1, name: 'Tomato' }], latest: async () => ({ observation: { modal_price_inr_per_quintal: '1000', report_date: '2026-11-12' }, stale: false }) }, getDecisionPlan: () => null }));
vi.mock('./state', () => ({ useApp: () => ({ result: null, scope: { market: 'Kolar APMC', commodity: 'Tomato', variety: 'local', grade: 'faq' }, draft: { quantity: '20', price: '1000' } }) }));
const user = { id: 1, role: 'FARMER', name: 'TEST_ONLY farmer', email: 'farmer@example.test' };
const show = (path = '/sale-requests', owner = false) => render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/sale-requests/:requestId" element={<SaleWorkspace />} /><Route path="*" element={<SaleWorkspace owner={owner} />} /></Routes></MemoryRouter>);

beforeEach(() => { setLanguage('en'); vi.mocked(saleAPI).mockImplementation(async path => {
  if (path === '/auth/me') return user;
  if (path === '/notifications') return [];
  if (path === '/notifications/unread-count') return { count: 0 };
  if (path === '/sale-mandis') return [{ id: 1, name: 'Kolar APMC', online_requests_available: false, commodity_ids: [] }];
  if (path === '/notification-preferences') return { email: false, sms: false, whatsapp: false, channels: { email: 'not_configured', sms: 'not_configured', whatsapp: 'not_configured' }, email_verified: false, phone_verified: false };
  return [];
}); });

describe('sale workflow UI — TEST_ONLY fixtures', () => {
  it('allows a farmer to save a pending request without inventing an onboarded owner', async () => {
    show('/sale-requests/new');
    expect(await screen.findByText('You can save this request now. The mandi will receive it after an approved operator activates the portal.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review request' })).toBeEnabled();
    expect(screen.queryByLabelText('Expected selling price (INR/quintal)')).not.toBeInTheDocument();
  });
  it('shows horizontal emoji crop choices with the current crop selected', async () => {
    show('/sale-requests/new');
    await waitFor(() => expect(screen.getByRole('button', { name: /Tomato.*Kolar/ })).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.queryByRole('combobox', { name: 'Crop' })).not.toBeInTheDocument();
  });
  it('requires an authenticated account and handles login failure', async () => {
    vi.mocked(saleAPI).mockRejectedValue(new SaleAPIError(401, 'invalid_credentials'));
    show();
    fireEvent.change(await screen.findByLabelText('Email'), { target: { value: 'farmer@example.test' } });
    fireEvent.change(screen.getByLabelText('Password (at least 12 characters)'), { target: { value: 'TEST_ONLY-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect((await screen.findAllByText('invalid_credentials')).length).toBeGreaterThan(0);
  });
  it('prevents a farmer account from opening owner requests', async () => {
    show('/mandi', true);
    expect(await screen.findByText('You are signed in as a farmer. Your farmer account cannot manage mandi requests.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in with an operator account' })).toBeInTheDocument();
  });
  it('switches the farmer workflow between English and Kannada', async () => {
    show();
    expect(await screen.findByRole('heading', { name: 'My Sale Requests' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByRole('heading', { name: 'ನನ್ನ ಮಾರಾಟ ವಿನಂತಿಗಳು' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('heading', { name: 'My Sale Requests' })).toBeInTheDocument();
  });
  it('shows unconfigured channels and blocks consent before verification', async () => {
    show('/sale-requests/settings');
    expect((await screen.findAllByText(/not_configured/)).length).toBe(3);
    for (const box of screen.getAllByRole('checkbox')) expect(box).toBeDisabled();
  });
  it('shows empty history without fabricated requests', async () => {
    show();
    expect(await screen.findByText('No sale requests in this view')).toBeInTheDocument();
    expect(screen.queryByText(/SAMAY-SALE-/)).not.toBeInTheDocument();
  });
});
