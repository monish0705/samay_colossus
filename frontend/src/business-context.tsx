import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { saleAPI, SaleAPIError } from './sale-api';
import { t } from './i18n';

export interface BusinessChoice { business_id: number; name: string; business_type: 'PRIVATE_MANDI' | 'PRIVATE_BUYER' | 'APMC_MANDI'; role: string }
export interface BusinessAccess { user_id: number; roles: string[]; workspaces: BusinessChoice[]; active_workspace: { mode: 'FARMER' | 'BUSINESS'; business_id: number | null; role: string | null } }
export const workspaceURL = (w: BusinessChoice) => `/business/${w.business_type === 'APMC_MANDI' ? 'apmc' : w.business_type === 'PRIVATE_MANDI' ? 'mandi' : 'buyer'}/${w.business_id}`;
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
    navigate(workspace ? workspaceURL(workspace) : '/');
  };
  return <Context.Provider value={{ access, loading, error, refresh, switchTo }}>{children}</Context.Provider>;
}
export function useBusinessWorkspace() {
  const value = useContext(Context);
  return value || { access: null, loading: false, error: '', refresh: async () => {}, switchTo: async () => {} };
}

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

  const isBusinessRoute = location.pathname.startsWith('/business');
  const isBusinessMode = access?.active_workspace.mode === 'BUSINESS' || isBusinessRoute;

  async function handleFarmerClick() {
    setBusy(true);
    setError('');
    try {
      if (access && access.active_workspace.mode === 'BUSINESS') {
        await switchTo();
      } else {
        navigate('/');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Workspace switch failed');
      navigate('/');
    } finally {
      setBusy(false);
    }
  }

  async function handleBusinessClick() {
    setBusy(true);
    setError('');
    try {
      if (access && access.workspaces && access.workspaces.length > 0) {
        const choice = access.workspaces.find(w => w.business_id === access.active_workspace.business_id && w.role === access.active_workspace.role) || access.workspaces[0];
        await switchTo(choice);
      } else {
        navigate('/business');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Workspace switch failed');
    } finally {
      setBusy(false);
    }
  }

  async function changeWorkspace(choice: BusinessChoice) {
    setBusy(true);
    setError('');
    try {
      await switchTo(choice);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Workspace switch failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="business-role-control">
      <div className="business-mode-buttons" role="group" aria-label={t('Account workspace')}>
        <button
          type="button"
          aria-pressed={!isBusinessMode}
          disabled={busy}
          onClick={() => void handleFarmerClick()}
        >
          {t('Farmer Mode')}
        </button>
        <button
          type="button"
          aria-pressed={isBusinessMode}
          disabled={busy}
          title={t('Business Mode — manage private mandi or private buyer workspace')}
          onClick={() => void handleBusinessClick()}
        >
          {t('Business Mode')}
        </button>
      </div>
      {access && access.workspaces.length > 0 && isBusinessMode && (
        <label className="business-workspace-select">
          <span className="sr-only">{t('Authorized business workspace')}</span>
          <select
            aria-label={t('Authorized business workspace')}
            disabled={busy}
            value={access.active_workspace.business_id ? `${access.active_workspace.business_id}:${access.active_workspace.role}` : ''}
            onChange={e => {
              const selected = access.workspaces.find(w => `${w.business_id}:${w.role}` === e.target.value);
              if (selected) void changeWorkspace(selected);
            }}
          >
            <option value="" disabled>{t('Choose business workspace')}</option>
            {access.workspaces.map(w => (
              <option key={`${w.business_id}:${w.role}`} value={`${w.business_id}:${w.role}`}>
                {w.business_type === 'APMC_MANDI' ? '🏛️ APMC Mandi' : w.business_type === 'PRIVATE_MANDI' ? '🏬 Private Mandi' : '💼 Private Buyer'} · {w.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && <span role="alert" className="sale-error">{t(error)}</span>}
    </div>
  );
}
