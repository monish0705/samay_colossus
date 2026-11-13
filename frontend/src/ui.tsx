import { getLanguage, localize, t, warningMessages } from './i18n';
import { useEffect, useState, type ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, Database, LoaderCircle, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ApiError } from './api';
export const inr = (v: string | number | null | undefined) => v == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(v));
export const qty = (v: string | number | null | undefined) => v == null ? '—' : `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 3 }).format(Number(v))} ${t('qtl')}`;
export const dateLabel = (v: string | null | undefined) => v ? new Intl.DateTimeFormat(getLanguage() === 'kn' ? 'kn-IN' : 'en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(new Date(v.length === 10 ? `${v}T00:00:00+05:30` : v)) : t('Not available');
export function Card({ children, className = '', hidden = false }: { children: ReactNode; className?: string; hidden?: boolean }) { return localize(<section hidden={hidden} className={`card ${className}`}>{children}</section>); }
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'green' | 'amber' | 'neutral' | 'red' }) { return localize(<span className={`badge badge-${tone}`}>{children}</span>); }
export function PageHeading({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: ReactNode; action?: ReactNode }) { return localize(<div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{children}</p></div>{action}</div>); }
export function Empty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) { return localize(<div className="empty-state"><span className="empty-icon"><Database size={24}/></span><h3>{title}</h3><p>{children}</p>{action}</div>); }
export function Notice({ children, tone = 'amber' }: { children: ReactNode; tone?: 'amber' | 'green' | 'neutral' }) { return localize(<div className={`notice notice-${tone}`}><AlertCircle size={18}/><div>{children}</div></div>); }
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) { const message = error instanceof ApiError && error.status > 0 ? warningMessages[error.code] || 'The server could not complete this request.' : error instanceof Error ? error.message : 'Unable to load this information.'; return localize(<div className="error-state" role="alert"><AlertCircle size={20}/><div><strong>{error instanceof ApiError && error.status === 503 ? 'Service not ready' : 'Connection or request issue'}</strong><p>{message}</p>{error instanceof ApiError && error.requestId && <small>Request {error.requestId}</small>}{retry && <button className="text-button" onClick={retry}><RefreshCw size={14}/>Try again</button>}</div></div>); }
export function Loading({ label = 'Loading verified information…' }: { label?: string }) { return localize(<div className="loading" role="status"><LoaderCircle className="spin" size={20}/>{label}</div>); }
export function Stat({ label, value, note, icon }: { label: string; value: ReactNode; note: ReactNode; icon?: ReactNode }) { return localize(<Card className="stat"><div className="stat-label">{label}{icon}</div><div className="stat-value">{value}</div><p>{note}</p></Card>); }
export function ActionLink({ to, children }: { to: string; children: ReactNode }) { return localize(<Link className="text-button" to={to}>{children}<ArrowUpRight size={16}/></Link>); }
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, key: string) {
  const [state, setState] = useState<{ data: T | null; error: unknown; loading: boolean }>({ data: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { const c = new AbortController(); setState({ data: null, error: null, loading: true }); load(c.signal).then(data => { if (!c.signal.aborted) setState({ data, error: null, loading: false }); }).catch(error => { if (!c.signal.aborted) setState({ data: null, error, loading: false }); }); return () => c.abort(); }, [key, attempt]);
  return { ...state, retry: () => setAttempt(v => v + 1) };
}
