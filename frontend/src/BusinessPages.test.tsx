import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BusinessWorkspaceProvider, RoleSwitcher, type BusinessAccess } from './business-context';
import { BusinessPage } from './BusinessPages';
import { saleAPI, SaleAPIError } from './sale-api';
import { setLanguage } from './i18n';

vi.mock('./sale-api', async () => ({ ...await vi.importActual('./sale-api'), saleAPI: vi.fn() }));
vi.mock('./api', async () => ({ ...await vi.importActual('./api'), api: { commodities: async () => [{ id: 1, name: 'Tomato' }] } }));
let access: BusinessAccess;
let deny = false;
beforeEach(() => {
  setLanguage('en'); deny = false;
  access = { user_id: 1, roles: ['FARMER'], workspaces: [], active_workspace: { mode: 'FARMER', business_id: null, role: null } };
  vi.mocked(saleAPI).mockImplementation(async (path, body) => {
    if (path === '/business/roles') return structuredClone(access);
    if (path === '/business/active-role') {
      if (deny) throw new SaleAPIError(403, 'business_workspace_not_authorized');
      access.active_workspace = body as BusinessAccess['active_workspace'];
      return structuredClone(access);
    }
    if (path === '/business/profile') return [];
    if (path === '/admin/businesses/pending') return [];
    throw new SaleAPIError(401, 'authentication_required');
  });
});
function show(path = '/') { return render(<MemoryRouter initialEntries={[path]}><BusinessWorkspaceProvider><RoleSwitcher /><Routes><Route path="/business/register" element={<BusinessPage />} /><Route path="/business/admin" element={<BusinessPage />} /><Route path="/business/mandi/1" element={<h1>TEST_ONLY private mandi workspace</h1>} /><Route path="/business/buyer/2" element={<h1>TEST_ONLY private buyer workspace</h1>} /><Route path="*" element={<h1>Farmer workspace</h1>} /></Routes></BusinessWorkspaceProvider></MemoryRouter>); }
function authorize() {
  access.roles = ['FARMER', 'PRIVATE_MANDI_OWNER', 'PRIVATE_BUYER'];
  access.workspaces = [{ business_id: 1, business_type: 'PRIVATE_MANDI', name: 'TEST_ONLY private mandi', role: 'PRIVATE_MANDI_OWNER' }, { business_id: 2, business_type: 'PRIVATE_BUYER', name: 'TEST_ONLY private buyer', role: 'PRIVATE_BUYER' }];
}

describe('authorized private workspaces — TEST_ONLY fixtures', () => {
  it('keeps Business Mode disabled for a farmer-only account', async () => {
    show();
    expect(await screen.findByRole('button', { name: 'Business Mode' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Business Mode' }));
    expect(screen.getByRole('heading', { name: 'Farmer workspace' })).toBeInTheDocument();
    expect(vi.mocked(saleAPI).mock.calls.some(([path]) => path === '/business/active-role')).toBe(false);
  });
  it('switches between two authorized private business types and back to farming', async () => {
    authorize(); show();
    fireEvent.click(await screen.findByRole('button', { name: 'Business Mode' }));
    expect(await screen.findByRole('heading', { name: 'TEST_ONLY private mandi workspace' })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('combobox', { name: 'Authorized business workspace' }), { target: { value: '2:PRIVATE_BUYER' } });
    expect(await screen.findByRole('heading', { name: 'TEST_ONLY private buyer workspace' })).toBeInTheDocument();
    expect(access.active_workspace.business_id).toBe(2);
    fireEvent.click(screen.getByRole('button', { name: 'Farmer Mode' }));
    expect(await screen.findByRole('heading', { name: 'Farmer workspace' })).toBeInTheDocument();
    expect(access.active_workspace.mode).toBe('FARMER');
  });
  it('restores a server-persisted workspace on refresh', async () => {
    authorize(); access.active_workspace = { mode: 'BUSINESS', business_id: 2, role: 'PRIVATE_BUYER' };
    show('/');
    expect(await screen.findByRole('heading', { name: 'TEST_ONLY private buyer workspace' })).toBeInTheDocument();
  });
  it('does not navigate or grant a role when the backend rejects a switch', async () => {
    authorize(); deny = true; show();
    fireEvent.click(await screen.findByRole('button', { name: 'Business Mode' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('business_workspace_not_authorized');
    expect(screen.getByRole('heading', { name: 'Farmer workspace' })).toBeInTheDocument();
  });
  it('provides distinct registration flows without claiming automatic approval', async () => {
    show('/business/register');
    expect(await screen.findByLabelText('Registered private mandi name')).toBeInTheDocument();
    expect(screen.getByLabelText('Operating hours')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Private buyer/ }));
    expect(screen.getByLabelText('Buyer or business name')).toBeInTheDocument();
    expect(screen.getByLabelText('Buyer type')).toBeInTheDocument();
    expect(screen.queryByLabelText('Operating hours')).not.toBeInTheDocument();
    expect(screen.getByText('Selecting a business type submits an application; it does not grant a role.')).toBeInTheDocument();
    expect(screen.getByText('Private businesses are separate from government APMC markets.')).toBeInTheDocument();
  });
  it('does not render administrator controls for a farmer', async () => {
    show('/business/admin');
    expect(await screen.findByRole('alert')).toHaveTextContent('Administrator authorization required.');
    expect(screen.queryByRole('button', { name: 'Save verification decision' })).not.toBeInTheDocument();
  });
});
