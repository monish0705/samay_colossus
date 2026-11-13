import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SaleWorkspace } from './SalePages';
import { setLanguage } from './i18n';
import { saleAPI, SaleAPIError } from './sale-api';

vi.mock('./sale-api', async () => ({ ...await vi.importActual('./sale-api'), saleAPI: vi.fn() }));
vi.mock('./api', () => ({ api: { commodities: async () => [{ id: 2, name: 'Copra' }, { id: 1, name: 'Tomato' }] }, getDecisionPlan: () => null }));
vi.mock('./state', () => ({ useApp: () => ({ result: null, scope: { market: 'TEST_ONLY mandi', commodity: 'Tomato', variety: 'local', grade: 'faq' }, draft: { quantity: '20', price: '1000' } }) }));
const user = { id: 1, role: 'FARMER', name: 'TEST_ONLY farmer', email: 'farmer@example.test' };
const show = (path = '/sale-requests', owner = false) => render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/sale-requests/:requestId" element={<SaleWorkspace />} /><Route path="*" element={<SaleWorkspace owner={owner} />} /></Routes></MemoryRouter>);

beforeEach(() => { setLanguage('en'); vi.mocked(saleAPI).mockImplementation(async path => {
  if (path === '/auth/me') return user;
  if (path === '/notifications') return [];
  if (path === '/notifications/unread-count') return { count: 0 };
  if (path === '/sale-mandis') return [{ id: 1, name: 'TEST_ONLY mandi', online_requests_available: false, commodity_ids: [] }];
  if (path === '/notification-preferences') return { email: false, sms: false, whatsapp: false, channels: { email: 'not_configured', sms: 'not_configured', whatsapp: 'not_configured' }, email_verified: false, phone_verified: false };
  return [];
}); });

describe('sale workflow UI — TEST_ONLY fixtures', () => {
  it('disables submission for a mandi without an onboarded owner', async () => {
    show('/sale-requests/new');
    expect(await screen.findByText('This mandi has not activated online sale requests. No request can be delivered yet.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review request' })).toBeDisabled();
  });
  it('keeps the recommendation crop selected when the catalogue has other crops first', async () => {
    const original = vi.mocked(saleAPI).getMockImplementation()!;
    vi.mocked(saleAPI).mockImplementation((path, ...args) => path === '/sale-mandis'
      ? Promise.resolve([{ id: 1, name: 'TEST_ONLY mandi', online_requests_available: true, commodity_ids: [1] }])
      : original(path, ...args));
    show('/sale-requests/new');
    await waitFor(() => expect(screen.getByLabelText('Crop', { exact: true })).toHaveValue('1'));
    expect(screen.getByRole('button', { name: 'Review request' })).toBeEnabled();
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
    expect(await screen.findByText('This account cannot access this portal. Sign out and use the correct account.')).toBeInTheDocument();
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
