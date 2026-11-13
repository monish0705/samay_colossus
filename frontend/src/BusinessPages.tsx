import { useEffect, useState, type FormEvent } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { api } from './api';
import { saleAPI } from './sale-api';
import { Auth } from './SalePages';
import { useBusinessWorkspace } from './business-context';
import { t } from './i18n';
import './business.css';
import { BusinessPurchasing } from './BusinessPurchasing';

interface BusinessProfile { id: number; business_type: 'PRIVATE_MANDI' | 'PRIVATE_BUYER'; name: string; contact_name: string; phone: string; email: string; address: string; district: string; state: string; registration_details: string; verification_information: string; document_references: string[]; commodity_ids: number[]; operating_hours: string | null; buyer_type: string | null; verification_state: string; version: number; can_publish: boolean; created_by: number; assigned_private_mandi_id: number | null; is_apmc: false }
const stateName = (value: string) => t(value.replaceAll('_', ' '));
function Input({ name, label, type = 'text', required = true }: { name: string; label: string; type?: string; required?: boolean }) { return <label className="sale-field">{t(label)}<input name={name} type={type} required={required} maxLength={2000} /></label>; }

export function BusinessPage() {
  const { access, loading, error, refresh } = useBusinessWorkspace();
  const [profiles, setProfiles] = useState<BusinessProfile[]>([]);
  const [failure, setFailure] = useState('');
  const [fetching, setFetching] = useState(false);
  const [reload, setReload] = useState(0);
  const location = useLocation();
  const { businessId } = useParams();
  const isAdmin = location.pathname === '/business/admin';
  const registration = location.pathname === '/business/register' || location.pathname === '/business';
  useEffect(() => {
    if (!access) return;
    let alive = true;
    const path = isAdmin ? '/admin/businesses/pending' : businessId ? `/business/workspace/${businessId}` : '/business/profile';
    setFailure(''); setFetching(true); setProfiles([]);
    saleAPI<BusinessProfile[] | BusinessProfile>(path).then(rows => { if (alive) setProfiles(Array.isArray(rows) ? rows : [rows]); }).catch(e => { if (alive) { setProfiles([]); setFailure(e.message); } }).finally(() => { if (alive) setFetching(false); });
    return () => { alive = false; };
  }, [access, isAdmin, businessId, reload]);
  if (loading && !access) return <p role="status">{t('Loading account')}</p>;
  if (!access) return <section className="business-page"><h1>{t('Private business registration')}</h1><p>{t('Use one account for farming and approved business workspaces.')}</p>{error && <p role="alert">{t(error)}</p>}<Auth owner={false} purpose="Business account sign-in" onUser={() => void refresh()} /></section>;
  if (isAdmin && !access.roles.includes('SYSTEM_ADMIN')) return <p role="alert">{t('Administrator authorization required.')}</p>;
  return <section className="sale-workspace business-page"><header><p className="eyebrow">{t('PRIVATE MARKETPLACE')}</p><h1>{t(isAdmin ? 'Business verification review' : registration ? 'Private business registration' : profiles[0]?.business_type === 'PRIVATE_MANDI' ? 'Private Mandi Dashboard' : 'Private Buyer Dashboard')}</h1><p className="sale-notice">{t('Private businesses are separate from government APMC markets.')}</p></header>
    <nav className="sale-nav"><Link to="/business/register">{t('My business applications')}</Link>{access.roles.includes('SYSTEM_ADMIN') && <Link to="/business/admin">{t('Review pending businesses')}</Link>}</nav>
    {failure && <p role="alert" className="sale-error">{t(failure)}</p>}
    {isAdmin && <form className="sale-grid" onSubmit={e => { e.preventDefault(); const id = new FormData(e.currentTarget).get('business_id'); void saleAPI<BusinessProfile>(`/admin/businesses/${id}`).then(value => { setProfiles([value]); setFailure(''); }).catch(error => setFailure(error.message)); }}><label className="sale-field">{t('Find business by ID')}<input name="business_id" type="number" min="1" required /></label><button className="button">{t('Open business review')}</button></form>}
    {fetching && <p role="status">{t('Loading business profile')}</p>}
    <div aria-live="polite">{profiles.map(b => <BusinessCard key={b.id} business={b} admin={isAdmin} onChange={() => { setReload(n => n + 1); void refresh(); }} />)}</div>
    {!registration && !isAdmin && profiles[0] && <BusinessPurchasing key={profiles[0].id} profile={profiles[0]} />}
    {isAdmin && !fetching && profiles.length === 0 && !failure && <p>{t('No pending business applications.')}</p>}
    {registration && <Registration onRegistered={() => { setReload(n => n + 1); void refresh(); }} />}
  </section>;
}

function BusinessCard({ business: b, admin, onChange }: { business: BusinessProfile; admin: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [review, setReview] = useState('VERIFIED');
  const allowedReviews: Record<string, string[]> = { PENDING_VERIFICATION: ['VERIFIED', 'REJECTED'], VERIFIED: ['SUSPENDED'], REJECTED: ['PENDING_VERIFICATION'], SUSPENDED: ['VERIFIED', 'PENDING_VERIFICATION'] };
  const decisions = allowedReviews[b.verification_state] || [];
  useEffect(() => { if (!decisions.includes(review)) setReview(decisions[0] || 'VERIFIED'); }, [b.verification_state, review, decisions]);
  const [history, setHistory] = useState<{ to_state: string; created_at: string; evidence: string }[] | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); setBusy(true); setError('');
    try { await saleAPI(`/admin/businesses/${b.id}/verify`, { version: b.version, state: review, evidence: values.evidence, contact_verified: values.contact_verified === 'on', registration_checked: values.registration_checked === 'on', documents_required: values.documents_required === 'on' }); onChange(); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  return <article className="sale-card"><div className="sale-row"><h2>{b.name}</h2><span className="sale-status">{stateName(b.verification_state)}</span></div><p><strong>{t(b.business_type === 'PRIVATE_MANDI' ? 'Private mandi' : 'Private buyer')}</strong> · {t('Not an APMC market operator')}</p><dl className="sale-ledger"><dt>{t('Authorized contact')}</dt><dd>{b.contact_name}</dd><dt>{t('Business location')}</dt><dd>{b.address}, {b.district}, {b.state}</dd><dt>{t('Business email')}</dt><dd>{b.email}</dd><dt>{t('Business phone')}</dt><dd>{b.phone}</dd>{b.operating_hours && <><dt>{t('Operating hours')}</dt><dd>{b.operating_hours}</dd></>}{b.buyer_type && <><dt>{t('Buyer type')}</dt><dd>{stateName(b.buyer_type)}</dd></>}</dl>
    {!admin && <><p>{t(b.can_publish ? 'Verified business management permission is active.' : 'Public publishing is locked until verification and assignment are complete.')}</p><button className="button" onClick={() => { void saleAPI<{ history: NonNullable<typeof history> }>(`/business/verification-status?business_id=${b.id}`).then(r => setHistory(r.history)).catch(e => setError(e.message)); }}>{t('View verification history')}</button>{history && <ol>{history.map((h, i) => <li key={i}>{stateName(h.to_state)} · {h.created_at} · {h.evidence}</li>)}</ol>}</>}
    {error && <p role="alert" className="sale-error">{t(error)}</p>}
    {admin && <><h3>{t('Protected verification information')}</h3><p>{b.registration_details}</p><p>{b.verification_information}</p><ul>{b.document_references.map(ref => <li key={ref}>{ref}</li>)}</ul><form className="sale-grid" onSubmit={submit}><label className="sale-field">{t('Review decision')}<select aria-label={t('Review decision')} value={review} onChange={e => setReview(e.target.value as typeof review)}>{decisions.map(value => <option key={value} value={value}>{stateName(value)}</option>)}</select></label><Input name="evidence" label="Verification evidence and decision reason" /><label><input name="contact_verified" type="checkbox" /> {t('Contact ownership verified independently')}</label><label><input name="registration_checked" type="checkbox" /> {t('Business registration checked')}</label><label><input name="documents_required" type="checkbox" /> {t('Verification documents required')}</label><button className="button button-primary" disabled={busy}>{t('Save verification decision')}</button></form></>}
  </article>;
}

function Registration({ onRegistered }: { onRegistered: () => void }) {
  const [type, setType] = useState<'PRIVATE_MANDI' | 'PRIVATE_BUYER'>('PRIVATE_MANDI');
  const [crops, setCrops] = useState<{ id: number; name: string }[]>([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(() => crypto.randomUUID());
  useEffect(() => { api.commodities().then(setCrops).catch(e => setError(e.message)); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); const values = Object.fromEntries(data);
    const body = { business_type: type, name: values.name, contact_name: values.contact_name, phone: values.phone, email: values.email,
      address: values.address, district: values.district, state: values.state, registration_details: values.registration_details,
      verification_information: values.verification_information, document_references: String(values.document_references || '').split('\n').map(v => v.trim()).filter(Boolean),
      commodity_ids: data.getAll('commodity_ids').map(Number), ...(type === 'PRIVATE_MANDI' ? { operating_hours: values.operating_hours } : { buyer_type: values.buyer_type }) };
    setBusy(true); setError('');
    try { await saleAPI('/business/register', body, key); setSuccess(true); onRegistered(); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); } finally { setBusy(false); }
  }
  if (success) return <section className="sale-card"><h2>{t('Application saved for verification')}</h2><p>{t('Business Mode remains locked until an administrator verifies and assigns your business.')}</p><button onClick={() => { setSuccess(false); setKey(crypto.randomUUID()); }}>{t('Register another business')}</button></section>;
  return <section className="sale-card"><h2>{t('Register a private business')}</h2><div className="business-type-choice" role="group" aria-label={t('Business type')}><button type="button" aria-pressed={type === 'PRIVATE_MANDI'} onClick={() => setType('PRIVATE_MANDI')}>🏪 {t('Private mandi')}</button><button type="button" aria-pressed={type === 'PRIVATE_BUYER'} onClick={() => setType('PRIVATE_BUYER')}>🤝 {t('Private buyer')}</button></div>
    <p>{t('Selecting a business type submits an application; it does not grant a role.')}</p>
    <form className="sale-grid" onSubmit={submit} onChange={() => setKey(crypto.randomUUID())}>
      <Input name="name" label={type === 'PRIVATE_MANDI' ? 'Registered private mandi name' : 'Buyer or business name'} /><Input name="contact_name" label={type === 'PRIVATE_MANDI' ? 'Owner name' : 'Authorized contact person'} /><Input name="phone" label="Business phone in international format" type="tel" /><Input name="email" label="Business email" type="email" /><Input name="address" label="Business address" /><Input name="district" label="District" /><Input name="state" label="State" />
      {type === 'PRIVATE_MANDI' ? <Input name="operating_hours" label="Operating hours" /> : <label className="sale-field">{t('Buyer type')}<select name="buyer_type">{['INDIVIDUAL_TRADER', 'AGRICULTURAL_BUSINESS', 'PROCUREMENT_COMPANY', 'REGISTERED_BUYER'].map(v => <option key={v} value={v}>{stateName(v)}</option>)}</select></label>}
      <Input name="registration_details" label="Business registration details or applicability" /><Input name="verification_information" label="Verification information" />
      <fieldset className="business-crop-options"><legend>{t('Crops handled or purchased')}</legend>{crops.map(c => <label key={c.id}><input name="commodity_ids" type="checkbox" value={c.id} /> {t(c.name)}</label>)}</fieldset>
      <label className="sale-field">{t('Protected verification document references (one per line)')}<textarea aria-label={t('Protected verification document references (one per line)')} name="document_references" maxLength={5000} /><small>{t('Provide secure document references. Public document uploads are not enabled.')}</small></label>
      {error && <p className="sale-error" role="alert">{t(error)}</p>}<button className="button button-primary" disabled={busy}>{t(busy ? 'Please wait' : 'Submit for verification')}</button>
    </form>
  </section>;
}
