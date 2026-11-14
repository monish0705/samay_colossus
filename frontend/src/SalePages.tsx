import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, CROP_SCOPES, getDecisionPlan } from './api';
import { getLanguage, setLanguage, t, useLanguage } from './i18n';
import { saleAPI, SaleAPIError, type Preferences, type Sale, type SaleEvent, type SaleInput, type SaleMandi, type SaleNote, type SaleUser, type StaffMember } from './sale-api';
import { useBusinessWorkspace } from './business-context';
import { useApp } from './state';
import { inr, qty, useResource } from './ui';
import './sales.css';
import './crop-picker.css';

const saleTime = (value: string) => new Intl.DateTimeFormat(getLanguage() === 'kn' ? 'kn-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(value)) + ' IST';
const statusText = (status: string) => t(status.replaceAll('_', ' '));
const formValues = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); return Object.fromEntries(new FormData(event.currentTarget)); };
function Field({ name, label, value, type = 'text', min, step, required = true }: { name: string; label: string; value?: string; type?: string; min?: string; step?: string; required?: boolean }) {
  return <label className="sale-field">{t(label)}<input name={name} type={type} defaultValue={value} min={min} step={step} required={required} maxLength={type === 'password' ? 128 : 2000} /></label>;
}
function ErrorMessage({ error }: { error: string }) { return error ? <p className="sale-error" role="alert">{t(error)}</p> : null; }
export function Auth({ owner, onUser, purpose }: { owner: boolean; onUser: (user: SaleUser) => void; purpose?: string }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const language = useLanguage();
  async function submit(event: FormEvent<HTMLFormElement>) {
    const values = formValues(event);
    setBusy(true); setError('');
    try {
      onUser(await saleAPI<SaleUser>(register ? '/auth/register' : '/auth/login', {
        email: values.email, password: values.password, ...(register ? { name: values.name, language, ...(values.invitation_token ? { invitation_token: values.invitation_token } : {}) } : {}),
      }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  return <section className="sale-card sale-auth"><h1>{t(purpose || (owner ? 'Mandi Owner Portal' : 'My Sale Requests'))}</h1><p>{t('Sign in to securely send and track sale requests.')}</p>
    <form onSubmit={submit} className="sale-grid">
      {register && <Field name="name" label="Full name" />}
      <Field name="email" label="Email" type="email" /><Field name="password" label="Password (at least 12 characters)" type="password" />
      {register && owner && <Field name="invitation_token" label="Administrator invitation code" />}
      <ErrorMessage error={error} /><button className="button button-primary" disabled={busy}>{t(busy ? 'Please wait' : register ? 'Create account' : 'Sign in')}</button>
    </form>
    <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(0,0,0,0.1)' }}>
      <button
        type="button"
        className="button"
        style={{ width: '100%', background: '#15803d', color: '#ffffff', fontWeight: 600, padding: '0.6rem' }}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError('');
          try {
            const u = await saleAPI<SaleUser>('/auth/demo-login', {});
            onUser(u);
          } catch (e) {
            setError(e instanceof Error ? e.message : 'Demo sign in failed');
          } finally {
            setBusy(false);
          }
        }}
      >
        ⚡ {t('1-Click Sign In (Monish MR · All 3 Personas)')}
      </button>
    </div>
    <button className="text-button" onClick={() => { setRegister(!register); setError(''); }}>{t(register ? 'Already registered? Sign in' : owner ? 'Redeem authorized invitation' : 'Create farmer account')}</button>
    {owner && <p>{t('Mandi accounts require administrator approval. No owner accounts are created automatically.')}</p>}
  </section>;
}

export function SaleWorkspace({ owner = false }: { owner?: boolean }) {
  const [user, setUser] = useState<SaleUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<SaleNote[]>([]);
  const [count, setCount] = useState(0);
  const [pollError, setPollError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const language = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams();
  const bWorkspace = useBusinessWorkspace();
  const root = owner ? (location.pathname.startsWith('/business/apmc') ? location.pathname.split('/').slice(0, 4).join('/') : '/mandi') : '/sale-requests';
  const RESERVED_SALE_PATHS = new Set([
    '', 'new', 'requests', 'incoming', 'counteroffers', 'arrivals',
    'arrived', 'completed', 'notifications', 'settings', 'staff',
    'undefined', 'null', 'sale-requests', 'mandi'
  ]);
  let rawReqId = params.requestId || (params['*']?.startsWith('requests/') ? params['*'].replace('requests/', '') : undefined);
  if (rawReqId && RESERVED_SALE_PATHS.has(rawReqId.trim().toLowerCase())) {
    rawReqId = undefined;
  }
  const reqId = rawReqId;
  useEffect(() => {
    saleAPI<SaleUser>('/auth/me')
      .then(setUser)
      .catch(async e => {
        if (e instanceof SaleAPIError && e.status === 401) {
          try {
            const demo = await saleAPI<SaleUser>('/auth/demo-login', {});
            setUser(demo);
            return;
          } catch {
            // ignore
          }
        }
        if (!(e instanceof SaleAPIError && e.status === 401)) setError(e.message);
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const [next, unread] = await Promise.all([saleAPI<SaleNote[]>('/notifications'), saleAPI<{ count: number }>('/notifications/unread-count')]);
        if (!cancelled) { setNotes(next); setCount(unread.count); setPollError(false); failures = 0; }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof SaleAPIError && err.status === 401) {
            try {
              const freshUser = await saleAPI<SaleUser>('/auth/demo-login', {});
              if (!cancelled) {
                setUser(freshUser);
                setPollError(false);
                failures = 0;
                timer = setTimeout(poll, 1500);
                return;
              }
            } catch {
              // ignore
            }
          }
          failures++;
          if (failures >= 4) {
            setPollError(true);
          }
        }
      }
      if (!cancelled) timer = setTimeout(poll, Math.min(30000, 5000 * 2 ** Math.min(failures, 3)));
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [user, refresh]);
  if (loading) return <p role="status">{t('Loading account')}</p>;
  if (!user) return <><ErrorMessage error={error} /><Auth owner={owner} onUser={setUser} /></>;
  const isOperator = ['MANDI_OWNER', 'MANDI_STAFF', 'SYSTEM_ADMIN'].includes(user.role) || (user.roles && user.roles.some(r => ['MANDI_OWNER', 'MANDI_STAFF', 'SYSTEM_ADMIN'].includes(r)));
  const allowed = owner ? (isOperator || location.pathname.startsWith('/business/apmc')) : true;
  const action = async (run: () => Promise<unknown>) => {
    setError('');
    try { await run(); setRefresh(n => n + 1); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
  };
  return <div className={`sale-workspace ${owner ? 'mandi-workspace' : ''}`}>
    {owner && bWorkspace && bWorkspace.access && bWorkspace.access.workspaces.length > 0 && (
      <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1.25rem', background: '#f0fdf4', padding: '0.6rem 1rem', borderRadius: '8px', border: '1px solid #bbf7d0', alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '0.85rem', color: '#166534' }}>{t('Switch Persona:')}</strong>
        <button
          type="button"
          className={`button ${bWorkspace.access?.active_workspace.mode === 'FARMER' ? 'button-primary' : ''}`}
          style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
          onClick={() => void bWorkspace.switchTo()}
        >
          🌾 {t('Farmer Mode')}
        </button>
        {bWorkspace.access.workspaces.map(w => (
          <button
            key={`${w.business_id}:${w.role}`}
            type="button"
            className={`button ${bWorkspace.access?.active_workspace.business_id === w.business_id && bWorkspace.access?.active_workspace.role === w.role ? 'button-primary' : ''}`}
            style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
            onClick={() => void bWorkspace.switchTo(w)}
          >
            {w.business_type === 'APMC_MANDI' ? '🏛️ APMC Mandi' : w.business_type === 'PRIVATE_MANDI' ? '🏬 Private Mandi' : '💼 Private Buyer'} · {w.name}
          </button>
        ))}
      </div>
    )}
    <header className="sale-header"><div><Link to="/" onClick={() => void bWorkspace.switchTo()}>SAMAY</Link><h1>{t(owner ? (location.pathname.startsWith('/business/apmc') ? 'APMC Mandi Dashboard' : 'Mandi Owner Portal') : 'My Sale Requests')}</h1><p>{user.name} · {t(user.role.replaceAll('_', ' '))}</p></div>
      <div><button className="button" onClick={() => setLanguage(language === 'en' ? 'kn' : 'en')}>{language === 'en' ? 'ಕನ್ನಡ' : 'English'}</button><button className="button" onClick={() => void action(async () => { await saleAPI('/auth/logout', {}); setUser(null); })}>{t('Sign out')}</button></div>
    </header>
    <p className="sale-notice">{t('SAMAY connects farmers and registered mandi operators. Physical sales and payments take place outside SAMAY.')}</p>
    {allowed && <nav className="sale-nav" aria-label={t('Sale navigation')}>
      {(owner ? [['', 'Dashboard'], ['/incoming', 'Incoming Requests'], ['/counteroffers', 'Counteroffers'], ['/arrivals', 'Arrival Schedule'], ['/arrived', 'Arrived Produce'], ['/completed', 'Completed Sales'], ['/notifications', 'Notifications'], ['/settings', 'Mandi Settings'], ['/staff', 'Staff Management']] : [['', 'My Sale Requests'], ['/new', 'Send Sale Request'], ['/notifications', 'Notifications'], ['/settings', 'Notification settings']]).map(([path, label]) => <NavLink key={path} end to={root + path}>{t(label)}{path === '/notifications' && <span aria-live="polite"> ({count})</span>}</NavLink>)}
    </nav>}
    {!allowed ? <section className="sale-card"><h2>{t('Use a mandi operator account')}</h2><p>{t('You are signed in as a farmer. Your farmer account cannot manage mandi requests.')}</p><div className="sale-row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}><Link className="button button-primary" to="/sale-requests">{t('Go to my sale requests')}</Link><Link className="button" to="/business">{t('Go to Business Mode')}</Link><button className="button" onClick={() => void action(async () => { await saleAPI('/auth/logout', {}); setUser(null); })}>{t('Sign in with an operator account')}</button></div><p>{t('APMC Mandi accounts require administrator approval. Private mandis and private buyers operate in Business Mode.')}</p></section> : <>
      <ErrorMessage error={error} />
      {pollError && <p role="status">{t('Notification connection lost. Retrying automatically.')} <button onClick={() => setRefresh(n => n + 1)}>{t('Retry now')}</button></p>}
      {notes.some(n => !n.read_at) && !location.pathname.endsWith('/notifications') && <aside className="sale-notice" aria-live="polite"><strong>{t('Unread notifications')}: {count}</strong> <Link to={root + '/notifications'}>{t('Open inbox')}</Link></aside>}
      {location.pathname.endsWith('/notifications') ? <section><h2>{t('Notifications')}</h2>{notes.length === 0 && <p>{t('No notifications yet')}</p>}{notes.map(n => <article key={n.id} className="sale-card"><p>{n.message[language]}</p><p>{saleTime(n.created_at)} · {t(n.read_at ? 'Read' : 'Unread')}</p><button className="button" onClick={() => void action(async () => { await saleAPI(`/notifications/${n.id}/read`, {}); navigate(`${root}/${owner ? 'requests/' : ''}${n.request_id}`); })}>{t('Open request')}</button>{n.deliveries.map(d => <p key={d.channel}>{t(d.channel)}: {t(d.status)} {d.error_reason && t(d.error_reason)}</p>)}</article>)}</section>
        : location.pathname.endsWith('/settings') ? <Settings user={user} />
        : location.pathname.endsWith('/staff') ? <Staff />
        : reqId && reqId !== 'new' ? <SaleDetails key={reqId} requestId={reqId} owner={owner} changed={() => setRefresh(n => n + 1)} />
        : !owner && location.pathname.endsWith('/new') ? <SaleCreateForm />
        : <SaleList owner={owner} root={root} refresh={refresh + (notes[0]?.id || 0)} />}
    </>}
  </div>;
}

function SaleList({ owner, root = owner ? '/mandi' : '/sale-requests', refresh }: { owner: boolean; root?: string; refresh: number }) {
  const [rows, setRows] = useState<Sale[]>([]);
  const [counts, setCounts] = useState<{ counts: Record<string, number>; total: number } | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(0);
  const location = useLocation();
  useEffect(() => {
    let live = true;
    setLoading(true);
    const automatic = location.pathname.endsWith('/counteroffers') ? 'COUNTER_OFFERED' : location.pathname.endsWith('/arrivals') ? 'ARRIVAL_SCHEDULED' : location.pathname.endsWith('/arrived') ? 'ARRIVED' : location.pathname.endsWith('/completed') ? 'COMPLETED' : '';
    saleAPI<Sale[]>(`${owner ? '/mandi/requests' : '/sale-requests'}?limit=20&offset=${page * 20}&status=${filter || automatic}`).then(data => { if (live) { setRows(data); setError(''); } }).catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setLoading(false); });
    if (owner) saleAPI<{ counts: Record<string, number>; total: number }>('/mandi/dashboard').then(data => { if (live) setCounts(data); }).catch(() => {});
    return () => { live = false; };
  }, [owner, refresh, filter, page, location.pathname]);
  return <section>
    {counts && <div className="sale-stats"><div className="sale-card"><strong>{counts.total}</strong><p>{t('Total requests')}</p></div>{Object.entries(counts.counts).map(([key, value]) => <div className="sale-card" key={key}><strong>{value}</strong><p>{statusText(key)}</p></div>)}</div>}
    <label>{t('Filter by status')} <select value={filter} onChange={e => { setFilter(e.target.value); setPage(0); }}><option value="">{t('All')}</option>{['SUBMITTED', 'NOTIFIED', 'VIEWED', 'MANDI_ACCEPTED', 'COUNTER_OFFERED', 'ARRIVAL_SCHEDULED', 'ARRIVED', 'WEIGHED', 'COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED'].map(s => <option key={s} value={s}>{statusText(s)}</option>)}</select></label>
    <ErrorMessage error={error} />{loading ? <p role="status">{t('Loading requests')}</p> : rows.length === 0 ? <p>{t('No sale requests in this view')}</p> : rows.map(row => <article className="sale-card" key={row.public_request_id}><div className="sale-row"><h2><Link to={`${owner ? (location.pathname.startsWith('/business/apmc') ? `${root}/requests` : '/mandi/requests') : '/sale-requests'}/${row.public_request_id}`}>{row.public_request_id}</Link></h2><span className="sale-status">{statusText(row.delivery_status === 'WAITING_FOR_MANDI_ACTIVATION' ? 'WAITING FOR MANDI ACTIVATION' : row.status)}</span></div><p>{row.mandi_name} · {t(row.crop_name)} · {row.variety} / {row.grade}</p><p>{qty(row.requested_quantity)} · {t('Farmer expected price')}: {inr(row.expected_price_per_quintal)}/{t('quintal')}</p><p>{t('Observed reference price')}: {row.reference_modal_price ? inr(row.reference_modal_price) : t('Unavailable')} · {row.reference_price_date || ''}</p><p>{t('Preferred arrival')}: {saleTime(row.preferred_arrival_at)}</p><p>{t('Last updated')}: {saleTime(row.updated_at)}</p>{row.offers.at(-1) && <p>{t('Latest owner offer')}: {inr(row.offers.at(-1)!.price)} · {qty(row.offers.at(-1)!.quantity)}</p>}</article>)}
    <div className="sale-row"><button disabled={page === 0 || loading} onClick={() => setPage(p => p - 1)}>{t('Previous')}</button><span>{page + 1}</span><button disabled={rows.length < 20 || loading} onClick={() => setPage(p => p + 1)}>{t('Next')}</button></div>
  </section>;
}

function SaleCreateForm() {
  const { result, scope, draft } = useApp();
  const [mandis, setMandis] = useState<SaleMandi[]>([]);
  const [crops, setCrops] = useState<{ id: number; name: string }[]>([]);
  const [chosenCrop, setChosenCrop] = useState(scope.commodity);
  const [chosenMandiId, setChosenMandiId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<SaleInput | null>(null);
  const [previewResult, setPreviewResult] = useState<{ expected_price_per_quintal: string; reference_price_date: string | null; estimated_net_inr: string; waiting_for_mandi_activation: boolean } | null>(null);
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const selectedScope = CROP_SCOPES[chosenCrop] || CROP_SCOPES.Tomato;
  const market = (chosenMandiId ? mandis.find(m => m.id === chosenMandiId) : null) || mandis.find(m => m.id === 1) || mandis.find(m => m.name === selectedScope.market) || mandis[0];
  const crop = crops.find(c => c.name === chosenCrop);
  const latest = useResource(signal => api.latest(selectedScope, signal), chosenCrop);
  const plan = result && getDecisionPlan(result);
  useEffect(() => { Promise.all([saleAPI<SaleMandi[]>('/sale-mandis'), api.commodities()]).then(([m, c]) => { setMandis(m); setCrops(c); }).catch(e => setError(e.message)); }, []);
  async function preview(event: FormEvent<HTMLFormElement>) {
    const v = formValues(event);
    if (!market || !crop) { setError('Market data is still loading. Please retry.'); return; }
    const quantity = String(v.requested_quantity);
    const input: SaleInput = { mandi_id: market.id, crop_id: crop.id, variety: selectedScope.variety, grade: selectedScope.grade,
      total_harvest_quantity: chosenCrop === scope.commodity && Number(draft.quantity) > 0 ? draft.quantity : quantity,
      requested_quantity: quantity, use_mandi_price: true, preferred_arrival_at: new Date(String(v.preferred_arrival_at)).toISOString(),
      estimated_costs_inr: String(v.estimated_costs_inr || '0'), farmer_message: String(v.farmer_message || ''), contact_sharing_consent: v.contact_sharing_consent === 'on' };
    if (Number(quantity) > Number(input.total_harvest_quantity)) { setError('Requested quantity exceeds harvest'); return; }
    setBusy(true); setError('');
    try {
      const response = await saleAPI<NonNullable<typeof previewResult>>('/sale-requests/preview', input);
      setPreviewResult(response); setPending({ ...input, expected_price_per_quintal: response.expected_price_per_quintal }); setKey(crypto.randomUUID());
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  async function send() {
    if (!pending || busy) return;
    setBusy(true); setError('');
    try {
      const sale = await saleAPI<Sale>('/sale-requests', pending, key);
      try { sessionStorage.setItem(`samay_sale_${sale.public_request_id}`, JSON.stringify(sale)); } catch {}
      navigate(`/sale-requests/${sale.public_request_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  return <section className="sale-card"><h2>{t('Send Sale Request')}</h2><ErrorMessage error={error} />
    {pending && previewResult ? <><h3>{t('Confirm request summary')}</h3><dl className="sale-ledger"><dt>{t('Selected mandi')}</dt><dd>{market?.name}</dd><dt>{t('Crop')}</dt><dd>{selectedScope.icon} {t(chosenCrop)}</dd><dt>{t('Requested quantity')}</dt><dd>{qty(pending.requested_quantity)}</dd><dt>{t('Mandi reference price')}</dt><dd>{inr(previewResult.expected_price_per_quintal)}/{t('quintal')} · {previewResult.reference_price_date}</dd><dt>{t('Reference value less entered costs')}</dt><dd>{inr(previewResult.estimated_net_inr)}</dd><dt>{t('Preferred arrival')}</dt><dd>{saleTime(pending.preferred_arrival_at)}</dd></dl>
      <p>{t('This is a wholesale reference, not a confirmed buyer offer.')}</p>
      {previewResult.waiting_for_mandi_activation && <p className="sale-notice" role="status">{t('Your request will be saved as waiting for mandi activation. No owner has received it yet.')}</p>}
      <button className="button" disabled={busy} onClick={() => setPending(null)}>{t('Edit request')}</button><button className="button button-primary" disabled={busy} onClick={() => void send()}>{t(busy ? 'Sending' : 'Confirm and send request')}</button></>
    : <form onSubmit={preview}>
      <fieldset className="crop-choice-group"><legend>{t('Choose your crop')}</legend><div className="crop-choice-row">{Object.values(CROP_SCOPES).map(c => <button className="crop-choice" type="button" key={c.id} aria-pressed={chosenCrop === c.commodity} onClick={() => setChosenCrop(c.commodity)}><span className="crop-emoji" aria-hidden="true">{c.icon}</span><strong>{t(c.commodity)}</strong><small>{t(c.market)}</small></button>)}</div></fieldset>
      <div style={{ margin: '0.75rem 0' }}>
        <label className="sale-field" style={{ fontWeight: 600 }}>
          {t('Destination APMC Mandi')}
          <select
            style={{ marginTop: '0.25rem', padding: '0.45rem 0.6rem', width: '100%', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.9rem' }}
            value={market?.id || ''}
            onChange={e => setChosenMandiId(Number(e.target.value))}
          >
            {mandis.map(m => (
              <option key={m.id} value={m.id}>
                🏛️ {m.name} {m.id === 1 ? `(${t('Primary Pilot APMC')})` : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p><strong>{market?.name || t(selectedScope.market)}</strong> · {t(chosenCrop)} · {selectedScope.variety} / {selectedScope.grade}</p>
      <div className="mandi-price-box" role="status"><span>{t('Mandi price used automatically')}</span><strong>{latest.loading ? t('Loading market price') : latest.data?.observation ? inr(latest.data.observation.modal_price_inr_per_quintal) + ' / ' + t('quintal') : t('Unavailable')}</strong><small>{latest.data?.observation?.report_date || ''}</small><p>{t('This is a wholesale reference, not a confirmed buyer offer.')}</p></div>
      <div className="sale-grid"><Field name="requested_quantity" label="Quantity to sell (quintals)" type="number" min="0.001" step="0.001" value={plan && chosenCrop === scope.commodity && Number(plan.sell_today_quintals) > 0 ? String(plan.sell_today_quintals) : draft.quantity} /><Field name="preferred_arrival_at" label="Preferred arrival (your local time)" type="datetime-local" /></div>
      <details><summary>{t('Optional details: costs and message')}</summary><p>{t('Fees and transport are excluded unless you enter them below.')}</p><Field name="estimated_costs_inr" label="Estimated selling costs (INR)" type="number" min="0" step="0.01" value="0" /><label className="sale-field">{t('Message')}<textarea name="farmer_message" maxLength={2000} /></label><label><input type="checkbox" name="contact_sharing_consent" /> {t('Share my verified phone number with this mandi')}</label></details>
      {market && !market.online_requests_available && market.can_save_request !== false && <p className="sale-notice">{t('You can save this request now. The mandi will receive it after an approved operator activates the portal.')}</p>}
      {market?.can_save_request === false && <p role="status">{t('This mandi has temporarily paused new requests.')}</p>}
      <button className="button button-primary" disabled={busy || !market || !crop || market.can_save_request === false}>{t('Review request')}</button>
    </form>}
  </section>;
}

function SaleDetails({ requestId, owner, changed }: { requestId: string; owner: boolean; changed: () => void }) {
  const [sale, setSale] = useState<Sale | null>(null);
  const [events, setEvents] = useState<SaleEvent[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const prefix = owner ? '/mandi/requests' : '/sale-requests';
  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const row = owner ? await saleAPI<Sale>(`${prefix}/${requestId}/view`, {}) : await saleAPI<Sale>(`${prefix}/${requestId}`);
        const history = await saleAPI<SaleEvent[]>(`${prefix}/${requestId}/timeline`);
        if (live) { setSale(row); setEvents(history); setError(''); }
      } catch (e) {
        if (live) {
          try {
            const cached = sessionStorage.getItem(`samay_sale_${requestId}`);
            if (cached) {
              const cachedSale = JSON.parse(cached) as Sale;
              setSale(cachedSale);
              setError('');
              return;
            }
          } catch {}
          setError(e instanceof Error ? e.message : 'Request failed');
        }
      }
    }
    void load();
    return () => { live = false; };
  }, [prefix, requestId, owner, refresh]);
  async function act(action: string, values: Record<string, unknown> = {}, farmer = false) {
    if (!sale || busy) return;
    setBusy(true); setError('');
    try { await saleAPI(`${farmer ? '/sale-requests' : prefix}/${requestId}/${action}`, { ...values, version: sale.version }); setRefresh(n => n + 1); changed(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  if (!sale) {
    if (error) {
      return (
        <section className="sale-card">
          <ErrorMessage error={error} />
          <p>{t('The requested sale record could not be found or may have expired.')}</p>
          <div className="sale-row" style={{ marginTop: '1rem' }}>
            <Link className="button button-primary" to={owner ? '/mandi' : '/sale-requests'}>
              {t('Back to requests')}
            </Link>
          </div>
        </section>
      );
    }
    return <p role="status">{t('Loading request')}</p>;
  }
  const offers = sale.offers || [];
  const offer = offers.at(-1);
  const actionable = offer && ['MANDI_ACCEPTED', 'COUNTER_OFFERED'].includes(sale.status) && new Date(offer.expires_at).getTime() > Date.now();
  const offerSubmit = (event: FormEvent<HTMLFormElement>) => {
    const v = formValues(event);
    void act(String(v.action), { quantity: v.quantity, price: v.price, arrival_at: new Date(String(v.arrival_at)).toISOString(), expires_at: new Date(String(v.expires_at)).toISOString(), message: v.message });
  };
  return <section><Link to={owner ? '/mandi/incoming' : '/sale-requests'}>{t('Back to requests')}</Link><h2>{sale.public_request_id}</h2><span className="sale-status">{statusText(sale.delivery_status === 'WAITING_FOR_MANDI_ACTIVATION' ? 'WAITING FOR MANDI ACTIVATION' : sale.status)}</span>{sale.delivery_status === 'WAITING_FOR_MANDI_ACTIVATION' && <p className="sale-notice">{t('Your request is saved. No owner has received it yet. You will be notified after mandi activation.')}</p>}<ErrorMessage error={error} />
    <article className="sale-card"><h3>{sale.mandi_name} · {t(sale.crop_name)}</h3><dl className="sale-ledger"><dt>{t('Variety / grade')}</dt><dd>{sale.variety} / {sale.grade}</dd><dt>{t('Requested quantity')}</dt><dd>{qty(sale.requested_quantity)}</dd><dt>{t(sale.price_basis === 'mandi_reference' ? 'Mandi reference price' : 'Farmer expected price')}</dt><dd>{inr(sale.expected_price_per_quintal)}/{t('quintal')}</dd><dt>{t('Observed reference price')}</dt><dd>{sale.reference_modal_price ? inr(sale.reference_modal_price) : t('Unavailable')} · {sale.reference_price_date || ''}</dd><dt>{t('Estimated net realization')}</dt><dd>{inr(sale.estimated_net_inr)} ({t('Farmer estimate')})</dd><dt>{t('Estimated selling costs')}</dt><dd>{inr(sale.estimated_costs_inr)}</dd><dt>{t('Preferred arrival')}</dt><dd>{saleTime(sale.preferred_arrival_at)}</dd><dt>{t('Message')}</dt><dd>{sale.farmer_message || '—'}</dd>{sale.farmer_phone && <><dt>{t('Shared verified phone')}</dt><dd>{sale.farmer_phone}</dd></>}</dl></article>
    <article className="sale-card"><h3>{t('Offer history')}</h3>{offers.length === 0 && <p>{t('No owner offer yet')}</p>}{offers.map(o => <div className="sale-offer" key={o.id}><strong>{t('Owner offer')}: {inr(o.price)}/{t('quintal')} · {qty(o.quantity)}</strong><p>{t('Arrival slot')}: {saleTime(o.arrival_at)}</p><p>{t('Offer expiry')}: {saleTime(o.expires_at)}</p><p>{o.message}</p>{o.id === offer?.id && !actionable && <p>{t('This offer is not actionable')}</p>}</div>)}
      {!owner && actionable && <div className="sale-row"><button className="button button-primary" disabled={busy} onClick={() => { if (window.confirm(t('Confirm this exact price, quantity and arrival slot?'))) void act('confirm', { offer_id: offer.id }); }}>{t('Confirm offer and book arrival')}</button><button className="button" disabled={busy} onClick={() => void act('reject-offer', { reason: 'Farmer declined offer' })}>{t('Reject offer')}</button></div>}
    </article>
    {owner && ['VIEWED', 'COUNTER_OFFERED', 'MANDI_ACCEPTED'].includes(sale.status) && <article className="sale-card"><h3>{t('Respond to farmer')}</h3><form className="sale-grid" onSubmit={offerSubmit}><label>{t('Response')}<select name="action"><option value="counteroffer">{t('Send counteroffer')}</option>{sale.status === 'VIEWED' && <option value="accept">{t('Accept original price and quantity')}</option>}</select></label><Field name="quantity" label="Accepted quantity (quintals)" type="number" min="0.001" step="0.001" value={sale.requested_quantity} /><Field name="price" label="Offered price (INR/quintal)" type="number" min="0.01" step="0.01" value={sale.expected_price_per_quintal} /><Field name="arrival_at" label="Offered arrival slot (your local time)" type="datetime-local" /><Field name="expires_at" label="Offer expiry (your local time)" type="datetime-local" /><Field name="message" label="Offer message" required={false} /><button className="button button-primary" disabled={busy}>{t('Send terms to farmer')}</button></form>{sale.status === 'VIEWED' && <form onSubmit={e => { const v = formValues(e); void act('reject', { reason: v.reason }); }}><Field name="reason" label="Rejection reason" required={false} /><button className="button" disabled={busy}>{t('Reject request')}</button></form>}</article>}
    {sale.booking && <article className="sale-card"><h3>{t('Arrival booking')}</h3><p>{saleTime(sale.booking.arrival_at)}</p><p>{t('Cancellation is allowed until two hours before the agreed arrival slot, before produce arrives.')}</p></article>}
    {!owner && ['SUBMITTED', 'NOTIFIED', 'VIEWED', 'COUNTER_OFFERED', 'MANDI_ACCEPTED', 'ARRIVAL_SCHEDULED'].includes(sale.status) && <button className="button" disabled={busy} onClick={() => { if (window.confirm(t('Cancel this sale request?'))) void act('cancel', { reason: 'Farmer cancelled' }); }}>{t('Cancel request')}</button>}
    {owner && sale.status === 'ARRIVAL_SCHEDULED' && <ActionForm title="Record arrival" disabled={busy} onSubmit={v => act('mark-arrived', { received_quantity: v.received_quantity })}><Field name="received_quantity" label="Received quantity (quintals)" type="number" min="0.001" step="0.001" /></ActionForm>}
    {owner && sale.status === 'ARRIVED' && <ActionForm title="Record weighment and final terms" disabled={busy} onSubmit={v => act('record-weighment', v)}><Field name="weighed_quantity" label="Weighed quantity (quintals)" type="number" min="0.001" step="0.001" /><Field name="final_price" label="Final actual price (INR/quintal)" type="number" min="0.01" step="0.01" /><Field name="deductions_inr" label="Actual deductions (INR)" type="number" min="0" step="0.01" /><Field name="quality" label="Actual quality assessment" /><PaymentFields /></ActionForm>}
    {sale.transaction && <article className="sale-card"><h3>{t('Recorded actual transaction')}</h3><dl className="sale-ledger">{Object.entries(sale.transaction).filter(([key]) => ['weighed_quantity', 'final_price', 'gross_inr', 'deductions_inr', 'net_inr', 'quality', 'payment_status', 'payment_reference'].includes(key)).map(([key, value]) => <div key={key}><dt>{t(key.replaceAll('_', ' '))}</dt><dd>{key === 'payment_status' ? statusText(String(value)) : String(value)}</dd></div>)}</dl><p>{t('Payment status is manually recorded. SAMAY does not transfer money.')}</p>
      {owner ? <><ActionForm title="Update payment record" disabled={busy} onSubmit={v => act('payment', v)}><PaymentFields /></ActionForm>{sale.status === 'WEIGHED' && <button className="button button-primary" disabled={busy} onClick={() => void act('complete')}>{t('Complete sale record')}</button>}</> : <ActionForm title="Report discrepancy" disabled={busy} onSubmit={v => act('discrepancy', v, true)}><Field name="reason" label="Describe discrepancy" /></ActionForm>}
    </article>}
    <article className="sale-card"><h3>{t('Request timeline')}</h3><ol>{events.map(e => <li key={e.id}><strong>{statusText(e.to_status)}</strong> · {saleTime(e.created_at)}{Object.keys(e.details).length > 0 && <details><summary>{t('Audit details')}</summary><pre>{JSON.stringify(e.details, null, 2)}</pre></details>}</li>)}</ol></article>
  </section>;
}

function ActionForm({ title, onSubmit, disabled, children }: { title: string; onSubmit: (values: Record<string, unknown>) => Promise<unknown>; disabled: boolean; children: ReactNode }) { return <form className="sale-card sale-grid" onSubmit={e => { const v = formValues(e); void onSubmit(v); }}><h3>{t(title)}</h3>{children}<button className="button button-primary" disabled={disabled}>{t(title)}</button></form>; }
function PaymentFields() { return <><label className="sale-field">{t('Manually recorded payment status')}<select name="payment_status">{['NOT_PAID', 'PENDING', 'PARTIALLY_PAID', 'PAID', 'DISPUTED'].map(s => <option key={s} value={s}>{statusText(s)}</option>)}</select></label><Field name="payment_reference" label="Payment reference (optional)" required={false} /></>; }

function Settings({ user }: { user: SaleUser }) {
  const [pref, setPref] = useState<Preferences | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { saleAPI<Preferences>('/notification-preferences').then(setPref).catch(e => setError(e.message)); }, []);
  async function run(work: () => Promise<unknown>) { setBusy(true); setError(''); try { await work(); setPref(await saleAPI<Preferences>('/notification-preferences')); setMessage('Saved'); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); } }
  return <section className="sale-card"><h2>{t('Notification settings')}</h2><ErrorMessage error={error} /><p role="status">{t(message)}</p><p>{t('In-app notifications are always available. External channels require configuration, verified contacts and consent.')}</p>{pref && <form onSubmit={e => { const v = formValues(e); void run(() => saleAPI('/notification-preferences', { email: v.email === 'on', sms: v.sms === 'on', whatsapp: v.whatsapp === 'on' })); }}><div className="sale-grid">{(['email', 'sms', 'whatsapp'] as const).map(channel => <label key={channel}><input type="checkbox" name={channel} defaultChecked={pref[channel]} disabled={channel === 'email' ? !pref.email_verified : !pref.phone_verified} />{t(channel)} · {t(pref.channels[channel])}</label>)}</div><button disabled={busy}>{t('Save preferences')}</button></form>}
    {!pref?.email_verified && <><button disabled={busy} onClick={() => void run(() => saleAPI('/auth/verify-email/start', {}))}>{t('Send email verification code')}</button><form onSubmit={e => { const v = formValues(e); void run(() => saleAPI('/auth/verify-email/confirm', v)); }}><Field name="token" label="Email verification code" /><button disabled={busy}>{t('Verify email')}</button></form></>}
    <p>{t('Phone verification requires an authorized operator to verify ownership before enabling SMS or WhatsApp.')}</p>
    {user.role === 'SYSTEM_ADMIN' && <Administration />}
  </section>;
}

function Administration() {
  const [mandis, setMandis] = useState<SaleMandi[]>([]);
  const [crops, setCrops] = useState<{ id: number; name: string }[]>([]);
  const [error, setError] = useState('');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { Promise.all([saleAPI<SaleMandi[]>('/sale-mandis'), api.commodities()]).then(([m, c]) => { setMandis(m); setCrops(c); }).catch(e => setError(e.message)); }, []);
  async function run(path: string, body: unknown) { setBusy(true); setError(''); try { const reply = await saleAPI<{ invitation_token?: string }>(path, body); setToken(reply.invitation_token || 'Saved'); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); } }
  const markets = <label>{t('Selected mandi')}<select name="market_id">{mandis.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>;
  return <section><h2>{t('Authorized mandi onboarding')}</h2><ErrorMessage error={error} /><output className="sale-token">{token}</output><p>{t('Share invitation codes only through an authorized private channel after verifying operator identity.')}</p>
    <form className="sale-grid" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void run('/admin/mandis', { market_id: Number(data.get('market_id')), active: data.get('active') === 'on', registration_details: data.get('registration_details'), commodity_ids: data.getAll('commodity_ids').map(Number) }); }}>{markets}<Field name="registration_details" label="Verified registration details" />{crops.map(c => <label key={c.id}><input name="commodity_ids" value={c.id} type="checkbox" />{t(c.name)}</label>)}<label><input name="active" type="checkbox" />{t('Activate online request handling')}</label><button disabled={busy}>{t('Save mandi registration')}</button></form>
    <form className="sale-grid" onSubmit={e => { const v = formValues(e); void run('/admin/mandi-invitations', { ...v, market_id: Number(v.market_id) }); }}>{markets}<Field name="email" label="Operator email" type="email" /><label>{t('Role')}<select name="role"><option value="MANDI_OWNER">{t('Mandi owner')}</option><option value="MANDI_STAFF">{t('Mandi staff')}</option></select></label><Field name="identity_evidence" label="Identity verification evidence reference" /><button disabled={busy}>{t('Create invitation')}</button></form>
  </section>;
}

function Staff() {
  const [rows, setRows] = useState<StaffMember[]>([]);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { saleAPI<StaffMember[]>('/mandi/staff').then(setRows).catch(e => setError(e.message)); }, [refresh]);
  async function update(row: StaffMember, active: boolean) { try { await saleAPI('/mandi/staff', { user_id: row.user_id, market_id: row.market_id, can_transact: !row.can_transact, active }); setRefresh(n => n + 1); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } }
  return <section><h2>{t('Staff Management')}</h2><ErrorMessage error={error} /><p>{t('Staff must first redeem an administrator-approved invitation for this mandi.')}</p>{rows.map(row => <article className="sale-card" key={`${row.market_id}:${row.user_id}`}><p>{row.name} · {t(row.role)} · {row.market_id}</p>{row.role === 'MANDI_STAFF' && <><button onClick={() => void update(row, true)}>{t(row.can_transact ? 'Restrict to viewing' : 'Allow transaction updates')}</button><button onClick={() => void update(row, false)}>{t('Remove staff assignment')}</button></>}</article>)}</section>;
}
