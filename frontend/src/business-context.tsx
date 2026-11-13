import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { saleAPI, SaleAPIError } from './sale-api';
import { t } from './i18n';

export interface BusinessChoice { business_id: number; name: string; business_type: 'PRIVATE_MANDI' | 'PRIVATE_BUYER'; role: string }
export interface BusinessAccess { user_id: number; roles: string[]; workspaces: BusinessChoice[]; active_workspace: { mode: 'FARMER' | 'BUSINESS'; business_id: number | null; role: string | null } }
const workspaceURL = (w: BusinessChoice) => `/business/${w.business_type === 'PRIVATE_MANDI' ? 'mandi' : 'buyer'}/${w.business_id}`;
const Context = createContext<{ access: BusinessAccess | null; loading: boolean; error: string; refresh: () => Promise<void>; switchTo: (workspace?: BusinessChoice) => Promise<void> } | null>(null);

export function BusinessWorkspaceProvider({ children }: { children: ReactNode }) {
  const [access, setAccess] = useState<BusinessAccess | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const sequence = useRef(0);
  const location = useLocation();
  const navigate = useNavigate();
  const refresh = useCallback(async () => {
    const current = ++sequence.current;
    setLoading(true);
    try { const value = await saleAPI<BusinessAccess>('/business/roles'); if (current === sequence.current) { setAccess(value); setError(''); } }
    catch (e) { if (current === sequence.current) { setAccess(null); setError(e instanceof SaleAPIError && e.status === 401 ? '' : e instanceof Error ? e.message : 'Business service unavailable'); } }
    finally { if (current === sequence.current) setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh, location.pathname]);
  useEffect(() => { const listener = () => { void refresh(); }; window.addEventListener('samay-auth-changed', listener); return () => { window.removeEventListener('samay-auth-changed', listener); sequence.current++; }; }, [refresh]);
  const switchTo = async (workspace?: BusinessChoice) => {
    const value = await saleAPI<BusinessAccess>('/business/active-role', workspace ? { mode: 'BUSINESS', business_id: workspace.business_id, role: workspace.role } : { mode: 'FARMER' });
    setAccess(value);
    navigate(workspace ? workspaceURL(workspace) : '/advisor');
  };
  return <Context.Provider value={{ access, loading, error, refresh, switchTo }}>{children}</Context.Provider>;
}
export function useBusinessWorkspace() { const value = useContext(Context); if (!value) throw new Error('Business workspace context missing'); return value; }

export function RoleSwitcher() {
  const { access, loading, switchTo } = useBusinessWorkspace();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  // Restore only a server-authorized saved workspace, never a browser role selection.
  useEffect(() => {
    if (access?.active_workspace.mode === 'BUSINESS' && !location.pathname.startsWith('/business')) {
      const choice = access.workspaces.find(w => w.business_id === access.active_workspace.business_id && w.role === access.active_workspace.role);
      if (choice) navigate(workspaceURL(choice), { replace: true });
    }
  }, [access, location.pathname, navigate]);
  if (loading && !access) return null;
  if (!access) return <Link className="text-button" to="/business/register">{t('Register a private business')}</Link>;
  async function change(choice?: BusinessChoice) { setBusy(true); setError(''); try { await switchTo(choice); } catch (e) { setError(e instanceof Error ? e.message : 'Workspace switch failed'); } finally { setBusy(false); } }
  const business = access.active_workspace.mode === 'BUSINESS';
  return <div className="business-role-control">
    <div className="business-mode-buttons" role="group" aria-label={t('Account workspace')}>
      <button type="button" aria-pressed={!business} disabled={busy || !access.roles.includes('FARMER')} onClick={() => void change()}>{t('Farmer Mode')}</button>
      <button type="button" aria-pressed={business} disabled={busy || !access.workspaces.length} title={t('Only verified, assigned business accounts can enter Business Mode.')} onClick={() => void change(access.workspaces.find(w => w.business_id === access.active_workspace.business_id) || access.workspaces[0])}>{t('Business Mode')}</button>
    </div>
    {access.workspaces.length > 0 && <label className="business-workspace-select"><span className="sr-only">{t('Authorized business workspace')}</span><select aria-label={t('Authorized business workspace')} disabled={busy} value={business ? `${access.active_workspace.business_id}:${access.active_workspace.role}` : ''} onChange={e => { const selected = access.workspaces.find(w => `${w.business_id}:${w.role}` === e.target.value); if (selected) void change(selected); }}><option value="" disabled>{t('Choose business workspace')}</option>{access.workspaces.map(w => <option key={`${w.business_id}:${w.role}`} value={`${w.business_id}:${w.role}`}>{t(w.role === 'MANDI_STAFF' ? 'Mandi staff' : w.business_type === 'PRIVATE_MANDI' ? 'Private Mandi Owner' : 'Private Buyer')} · {w.name}</option>)}</select></label>}
    {error && <span role="alert">{t(error)}</span>}
  </div>;
}
