import { useEffect, useState, type FormEvent } from 'react';
import { api } from './api';
import { useBusinessWorkspace } from './business-context';
import { getLanguage, t } from './i18n';
import { purchaseAPI, type PrivateRequest, type PurchaseAnalytics, type PurchaseNote, type PurchaseOffer, type PurchaseTerms } from './purchase-api';
import { saleAPI } from './sale-api';

interface Profile {id: number; business_type: string; name: string; address: string; district: string; state: string; can_publish: boolean}
const sections = ['Overview', 'My Buying Offers', 'Create Buying Offer', 'Incoming Farmer Requests', 'Confirmed Requests', 'Appointments', 'Completed Purchases', 'Notifications', 'Business Profile', 'Settings'] as const;
type Section = typeof sections[number];
const dateTime = (v: string) => new Date(v).toLocaleString(getLanguage() === 'kn' ? 'kn-IN' : 'en-IN', {timeZone: 'Asia/Kolkata'});
export const rupees = (v: string) => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', minimumFractionDigits: 2}).format(Number(v));
const labelStatus = (v: string) => t(v.replaceAll('_', ' '));
const errorMessage = (value: string) => {
  const translated = t(value);
  const hints: Record<string,string> = {
    active_business_workspace_required: 'Select this business in the top workspace switch first.',
    purchase_offer_changed_refresh: 'This offer changed. Refresh the records and review the latest version.',
    private_request_changed_or_terminal: 'This request changed or has already been resolved. Refresh before responding.',
    insufficient_remaining_purchase_quantity: 'The remaining buying quantity is too small. Reduce the accepted quantity.',
    quantity_below_existing_reservations: 'Total quantity cannot be reduced below current reservations and commitments.',
    daily_purchasing_capacity_exceeded: 'The selected arrival date is at capacity. Choose another available date.',
    arrival_not_available: 'Choose a future arrival date listed in the offer.',
    response_expiry_must_precede_arrival_and_offer_expiry: 'The response must expire in the future, before arrival and offer expiry.',
    purchase_offer_not_currently_available: 'This offer is paused, expired, not yet started or no longer has a valid price.',
    offer_validity_must_be_in_future: 'Offer and price validity must end in the future.',
    arrival_dates_must_not_be_in_past: 'Remove past arrival dates before publishing.',
    business_not_verified: 'This business is not currently verified for purchasing.',
    authentication_required: 'Please sign in or select your business persona to continue.',
  };
  return translated !== value ? translated : (hints[value] || value);
};

const localTime = (v: string) => {const d = new Date(v); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0,16);};

export function BusinessPurchasing({profile, activeTab}: {profile: Profile; activeTab?: string | null}) {
  const {access, switchTo} = useBusinessWorkspace();
  const [section, setSection] = useState<Section>('Overview');
  const [offers, setOffers] = useState<PurchaseOffer[]>([]);
  const [requests, setRequests] = useState<PrivateRequest[]>([]);
  const [analytics, setAnalytics] = useState<PurchaseAnalytics | null>(null);
  const [notes, setNotes] = useState<{unread: number; items: PurchaseNote[]}>({unread: 0, items: []});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [reload, setReload] = useState(0);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<PurchaseOffer | null>(null);
  const [detail, setDetail] = useState<PurchaseOffer | null>(null);

  useEffect(() => {
    if (!activeTab) return;
    const map: Record<string, Section> = {
      'overview': 'Overview',
      'offers': 'My Buying Offers',
      'create': 'Create Buying Offer',
      'incoming': 'Incoming Farmer Requests',
      'confirmed': 'Confirmed Requests',
      'appointments': 'Appointments',
      'completed': 'Completed Purchases',
      'notifications': 'Notifications',
      'profile': 'Business Profile',
      'settings': 'Settings',
    };
    if (map[activeTab]) {
      setSection(map[activeTab]);
      setOffset(0);
      setDetail(null);
    }
  }, [activeTab]);

  const targetRole = profile.business_type === 'PRIVATE_MANDI' ? 'PRIVATE_MANDI_OWNER' : 'PRIVATE_BUYER';
  const choice = access?.workspaces.find(w => w.business_id === profile.id && (w.business_type === profile.business_type || w.role === targetRole)) ||
                 access?.workspaces.find(w => w.business_id === profile.id);
  const activeRole = access?.active_workspace.role;
  const active = access?.active_workspace.mode === 'BUSINESS' &&
                 access.active_workspace.business_id === profile.id &&
                 (!activeRole || activeRole === targetRole || (access.active_workspace as any).business_type === profile.business_type);

  useEffect(() => {
    if (!active && choice) {
      void switchTo(choice);
    }
  }, [active, choice, switchTo]);

  useEffect(() => {
    if (!active) return;
    let alive = true; setLoading(true); setError(''); setOffers([]); setRequests([]); setNotes({unread:0,items:[]}); setAnalytics(null);
    Promise.all([purchaseAPI.offers(profile.id, offset), purchaseAPI.requests(profile.id, offset), purchaseAPI.analytics(profile.id), purchaseAPI.notes(profile.id, offset)])
      .then(([o,r,a,n]) => {if (alive) {setOffers(o);setRequests(r);setAnalytics(a);setNotes(n);}})
      .catch(async e => {
        if (alive) {
          if (e.message === 'active_business_workspace_required' && choice) {
            try {
              await switchTo(choice);
              const [o,r,a,n] = await Promise.all([purchaseAPI.offers(profile.id, offset), purchaseAPI.requests(profile.id, offset), purchaseAPI.analytics(profile.id), purchaseAPI.notes(profile.id, offset)]);
              if (alive) { setOffers(o); setRequests(r); setAnalytics(a); setNotes(n); setError(''); return; }
            } catch {}
          }
          setError(e.message);
        }
      }).finally(() => {if (alive) setLoading(false);});
    return () => {alive=false;};
  }, [profile.id, active, activeRole, reload, offset, choice, switchTo]);
  const refresh = () => {setDetail(null); setReload(n => n+1);};
  if (!active) return <section className="sale-card"><p>{t('Select this authorized business workspace to manage purchasing.')}</p>{choice && <button className="button button-primary" onClick={() => void switchTo(choice).catch(e => setError(e.message))}>{t('Open purchasing workspace')}</button>}{error && <p role="alert" className="sale-error">{errorMessage(error)}</p>}</section>;

  const displayedRequests = section === 'Confirmed Requests'
    ? requests.filter(r => ['CONFIRMED', 'BOOKING_CONFIRMED', 'CONFIRMED_BY_FARMER', 'ARRIVED'].includes(r.status))
    : section === 'Completed Purchases'
    ? requests.filter(r => r.status === 'COMPLETED')
    : section === 'Incoming Farmer Requests'
    ? requests.filter(r => ['SUBMITTED', 'PENDING_BUSINESS_RESPONSE', 'VIEWED', 'ACCEPTED', 'COUNTEROFFERED'].includes(r.status))
    : requests;

  async function offerAction(offer: PurchaseOffer, verb: string) {setError(''); try {await saleAPI(`/business/offers/${offer.id}/${verb}`, {version: offer.version});refresh();} catch(e) {setError(e instanceof Error ? e.message : 'Request failed');}}
  return <section className="business-purchasing">
    <button type="button" className="button" onClick={refresh} disabled={loading}>{t('Refresh purchasing records')}</button>
    <header className="sale-row"><h2>{t(profile.business_type === 'PRIVATE_MANDI' ? 'Private mandi purchasing' : 'Private buyer purchasing')}</h2>{profile.can_publish && <button className="button button-primary" onClick={() => {setError('');setEditing(null);setSection('Create Buying Offer');}}>{t('Create New Buying Offer')}</button>}</header>
    <nav className="purchase-tabs" aria-label={t('Purchasing sections')}>{sections.map(s => <button key={s} type="button" aria-current={section===s ? 'page' : undefined} onClick={() => {setError('');setSection(s);setOffset(0);setDetail(null);}}>{t(s)}{s==='Notifications' ? ` (${notes.unread})` : ''}</button>)}</nav>
    {error && <p role="alert" className="sale-error">{errorMessage(error)} <button onClick={refresh}>{t('Retry')}</button></p>}
    {loading && <p role="status">{t('Loading purchasing records')}</p>}
    {section==='Overview' && analytics && <><div className="purchase-stats">{[['Buying offers',analytics.offer_count],['Incoming requests',analytics.incoming_requests],['Requested quintals',analytics.requested_quantity],['Confirmed quintals',analytics.confirmed_quantity],['Reserved quintals',analytics.reserved_quantity],['Remaining quintals',analytics.remaining_quantity],['Average listed price',analytics.average_offered_price ? rupees(analytics.average_offered_price) : t('Unavailable')],['Completed purchases',analytics.completed_purchases]].map(([label,value]) => <article className="sale-card" key={label}><span>{t(String(label))}</span><strong>{value}</strong></article>)}</div><p>{t('Submitted requests do not reserve quantity. Business responses reserve it until expiry; farmer confirmation commits it.')}</p><p>{t('Average listed price is an unweighted average across your offers, not a realized selling price.')}</p></>}
    {section==='Create Buying Offer' && profile.can_publish && <OfferForm key={editing?.id || 'new'} profile={profile} existing={editing} onSaved={() => {setSection('My Buying Offers');setEditing(null);refresh();}} />}
    {section==='My Buying Offers' && <>{!loading && !offers.length && <p>{t('No buying offers yet. Create your first offer.')}</p>}{offers.map(o => <article className="sale-card" key={o.id}><div className="sale-row"><h3>{o.commodity_name} · {o.terms.variety} · {o.terms.grade}</h3><span className="sale-status">{labelStatus(o.status)}</span></div><p>{rupees(String(o.terms.offered_price))} / {t('quintal')} · {labelStatus(o.terms.price_kind)} · {o.terms.purchasing_centre}</p><p>{t('Remaining')}: {o.quantity_remaining} / {o.quantity_required} {t('quintals')} · {t('Reserved')}: {o.quantity_reserved} · {t('Committed')}: {o.quantity_committed}</p><p>{t('Requests')}: {o.request_count} · {t('Offer expiry')}: {dateTime(o.terms.expires_at)}</p><p>{t('Last price update')}: {dateTime(o.price_updated_at)}</p>{o.terms.price_kind!=='FIRM' && <p className="sale-notice">{t('Indicative and negotiable prices are not guaranteed prices.')}</p>}<div className="sale-row"><button className="button" onClick={() => void purchaseAPI.offer(o.id).then(setDetail).catch(e=>setError(e.message))}>{t('Details and revision history')}</button>{profile.can_publish && o.status!=='CANCELLED' && <><button className="button" onClick={() => {setEditing(o);setSection('Create Buying Offer');}}>{t('Edit offer')}</button>{['DRAFT','PAUSED'].includes(o.status) && <button className="button" onClick={() => void offerAction(o,'publish')}>{t(o.status==='PAUSED' ? 'Resume offer' : 'Publish offer')}</button>}{['PUBLISHED','PARTIALLY_FILLED','FULLY_FILLED'].includes(o.status) && <button className="button" onClick={() => void offerAction(o,'pause')}>{t('Pause offer')}</button>}<button className="button" onClick={() => {if (window.confirm(t('Cancel publication? Existing response agreements remain unchanged.'))) void offerAction(o,'cancel');}}>{t('Cancel offer')}</button></>}</div></article>)}{detail && <article className="sale-card"><h3>{t('Offer terms and revisions')}</h3><TermDetails terms={detail.terms} /><h4>{t('Price history')}</h4><ol>{detail.price_history?.map((p,i)=><li key={i}>{rupees(p.price)} · {labelStatus(p.kind)} · {dateTime(p.created_at)}</li>)}</ol><h4>{t('Revision history')}</h4><ol>{detail.history?.map((h,i)=><li key={i}>{h.action} · #{h.revision} · {dateTime(h.created_at)}<details><summary>{t('Exact saved terms')}</summary><pre>{JSON.stringify(h.snapshot,null,2)}</pre></details></li>)}</ol></article>}</>}
    {['Incoming Farmer Requests','Confirmed Requests'].includes(section) && <>{!loading && !displayedRequests.length && <p>{t('No matching farmer requests.')}</p>}{displayedRequests.map(r => <RequestCard key={`${r.id}:${r.version}`} request={r} canManage={profile.can_publish} onChange={refresh}/>)}</>}
    {section==='Appointments' && <>{!requests.filter(r => ['CONFIRMED', 'BOOKING_CONFIRMED', 'CONFIRMED_BY_FARMER', 'ARRIVED'].includes(r.status)).length ? <p>{t('No confirmed upcoming appointments or arrivals.')}</p> : requests.filter(r => ['CONFIRMED', 'BOOKING_CONFIRMED', 'CONFIRMED_BY_FARMER', 'ARRIVED'].includes(r.status)).map(r => <RequestCard key={`${r.id}:${r.version}`} request={r} canManage={profile.can_publish} onChange={refresh} />)}</>}
    {section==='Completed Purchases' && <>{!requests.filter(r => r.status === 'COMPLETED').length ? <p className="sale-notice">{t('No completed purchase records exist. Actual weighment, payment and completion recording will be shown here.')}</p> : requests.filter(r => r.status === 'COMPLETED').map(r => <RequestCard key={`${r.id}:${r.version}`} request={r} canManage={profile.can_publish} onChange={refresh} />)}</>}
    {section==='Notifications' && <>{!loading && !notes.items.length && <p>{t('No purchasing notifications.')}</p>}{notes.items.map(n=><article className="sale-card" key={n.id}><p>{n.message[getLanguage()]}</p><p>{dateTime(n.created_at)} · {t('Offer')} #{n.offer_id} {n.request_id && ` · #${n.request_id}`}</p>{!n.read_at && <button className="button" onClick={() => void saleAPI(`/private-purchases/notifications/${n.id}/read`, {}).then(refresh).catch(e=>setError(e.message))}>{t('Mark read')}</button>}</article>)}</>}
    {section==='Business Profile' && <article className="sale-card"><h3>{profile.name}</h3><p>{profile.address}, {profile.district}, {profile.state}</p><p>{t('Profile and verification documents are shown above. Profile changes require administrator review.')}</p></article>}
    {section==='Settings' && <article className="sale-card"><h3>{t('Notification settings')}</h3><p>{t('In-app purchasing notifications are active. External purchasing messages are not enabled in this stage.')}</p><p>{t('Use the language controls above to choose English or Kannada. Manage authorized workspaces through the top switch.')}</p></article>}
    {['My Buying Offers','Incoming Farmer Requests','Confirmed Requests','Notifications'].includes(section) && <div className="sale-row"><button className="button" disabled={offset===0 || loading} onClick={()=>setOffset(n=>Math.max(0,n-50))}>{t('Previous page')}</button><span>{t('Page')} {offset/50+1}</span><button className="button" disabled={loading || (section==='My Buying Offers' ? offers.length : section==='Notifications' ? notes.items.length : requests.length)<50} onClick={()=>setOffset(n=>n+50)}>{t('Next page')}</button></div>}
  </section>;
}

function TermDetails({terms}: {terms: PurchaseTerms}) {return <dl className="sale-ledger">{Object.entries(terms).map(([key,v]) => <div key={key}><dt>{t(key.replaceAll('_',' '))}</dt><dd>{v===null || v==='' ? t('Unknown') : Array.isArray(v) ? v.join(', ') : String(v)}</dd></div>)}</dl>;}

function RequestCard({request:r,canManage,onChange}:{request:PrivateRequest;canManage:boolean;onChange:()=>void}) {
  const [action,setAction] = useState<'accept'|'counteroffer'|'reject'>('accept');
  const [showComplete, setShowComplete] = useState(false);
  const [busy,setBusy] = useState(false), [error,setError] = useState('');

  async function submit(e:FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.currentTarget));
    if (!window.confirm(t('Send this response with the displayed terms?'))) return;
    setBusy(true);
    setError('');
    try {
      await saleAPI(`/business/requests/${r.id}/${action}`, action==='reject' ? {version:r.version,reason:data.reason} : {version:r.version,quantity:data.quantity,price:data.price,arrival_at:new Date(String(data.arrival_at)).toISOString(),expires_at:new Date(String(data.expires_at)).toISOString(),payment_terms:data.payment_terms,message:data.message});
      onChange();
    } catch(e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleArrive() {
    if (!window.confirm(t('Record that the farmer produce has arrived at the purchasing premises?'))) return;
    setBusy(true);
    setError('');
    try {
      await purchaseAPI.recordArrival(r.id, r.version);
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Arrival recording failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleCompleteSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    if (!window.confirm(t('Complete purchase with these weighment and settlement details?'))) return;
    setBusy(true);
    setError('');
    try {
      await purchaseAPI.completePurchase(r.id, {
        version: r.version,
        actual_quantity: String(data.actual_quantity),
        settled_price: String(data.settled_price),
        deductions: Number(data.deductions) || 0,
        payment_reference: String(data.payment_reference),
        payment_method: String(data.payment_method || 'BANK_TRANSFER'),
        notes: String(data.notes || ''),
      });
      setShowComplete(false);
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Purchase completion failed');
    } finally {
      setBusy(false);
    }
  }

  const completion = (r.details as unknown as { completion?: Record<string, string> })?.completion;

  return <article className="sale-card"><div className="sale-row"><h3>{r.public_id}</h3><span className="sale-status">{labelStatus(r.status)}</span></div><p>{r.farmer_name} · {r.details.variety} / {r.details.grade} · {t('Offer')} #{r.offer_id}</p><p>{r.quantity} {t('quintals')} · {t('Expected price')}: {rupees(r.expected_price)} / {t('quintal')}</p><p>{t('Requested arrival')}: {dateTime(r.arrival_at)} · {t('Submitted')}: {dateTime(r.created_at)}</p>{r.farmer_phone && <p>{t('Consented verified phone')}: {r.farmer_phone}</p>}<p>{r.details.message}</p>

    {completion && (
      <div className="sale-card" style={{ background: '#f0fdf4', borderColor: '#86efac', margin: '0.75rem 0' }}>
        <h4>✅ {t('Settled Purchase Details')}</h4>
        <dl className="sale-ledger">
          <div><dt>{t('Actual Weighed Quantity')}</dt><dd>{completion.actual_quantity} {t('quintals')}</dd></div>
          <div><dt>{t('Final Settled Price')}</dt><dd>{rupees(completion.settled_price)} / {t('quintal')}</dd></div>
          <div><dt>{t('Gross Sale Amount')}</dt><dd>{rupees(completion.gross_amount)}</dd></div>
          <div><dt>{t('Deductions')}</dt><dd>{rupees(completion.deductions)}</dd></div>
          <div><dt>{t('Net Paid to Farmer')}</dt><dd><strong style={{ color: '#166534' }}>{rupees(completion.net_realization)}</strong></dd></div>
          <div><dt>{t('Payment Reference')}</dt><dd>{completion.payment_reference} ({completion.payment_method})</dd></div>
          <div><dt>{t('Completed At')}</dt><dd>{dateTime(completion.completed_at)}</dd></div>
        </dl>
      </div>
    )}

    <details><summary>{t('Full request details and history')}</summary><ol>{r.history.map((h,i)=><li key={i}>{labelStatus(h.action)} · {dateTime(h.created_at)}</li>)}</ol>{r.responses.map(response=><section key={response.id}><h4>{labelStatus(response.kind)}</h4><p>{response.quantity} {t('quintals')} · {rupees(response.price)} / {t('quintal')} · {dateTime(response.arrival_at)}</p><p>{t('Response expiry')}: {dateTime(response.expires_at)}</p><TermDetails terms={response.terms}/></section>)}</details>

    {canManage && ['SUBMITTED','ACCEPTED','COUNTEROFFERED'].includes(r.status) && <form className="sale-grid" onSubmit={submit}><label className="sale-field">{t('Response action')}<select aria-label={t('Response action')} value={action} onChange={e=>setAction(e.target.value as typeof action)}><option value="accept">{t('Accept request')}</option><option value="counteroffer">{t('Counteroffer')}</option><option value="reject">{t('Reject request')}</option></select></label>{action==='reject' ? <Field name="reason" label="Rejection reason or message" required={false}/> : <><Field name="quantity" label="Accepted quantity (quintals)" type="number" defaultValue={r.quantity} step="0.001" min="0.001" max={r.quantity}/><Field name="price" label="Confirmed price (INR/quintal)" type="number" defaultValue={r.expected_price} step="0.01" min="0.01"/><Field name="arrival_at" label="Arrival date and time (your local time)" type="datetime-local" defaultValue={localTime(r.arrival_at)}/><Field name="expires_at" label="Response expiry (your local time)" type="datetime-local"/><Field name="payment_terms" label="Confirm payment terms"/><Field name="message" label="Response explanation" required={false}/><p>{t('This response reserves quantity until expiry. The farmer must confirm; this is not a completed purchase.')}</p></>}{error && <p role="alert">{errorMessage(error)}</p>}<button className="button button-primary" disabled={busy}>{t('Send response')}</button></form>}

    {canManage && ['CONFIRMED', 'BOOKING_CONFIRMED', 'CONFIRMED_BY_FARMER'].includes(r.status) && (
      <div className="sale-row" style={{ marginTop: '0.75rem', gap: '0.5rem' }}>
        <button type="button" className="button button-primary" onClick={handleArrive} disabled={busy}>
          {busy ? t('Recording...') : t('Record Produce Arrival')}
        </button>
        <button type="button" className="button" onClick={() => setShowComplete(!showComplete)}>
          {t('Record Weighment & Settlement')}
        </button>
      </div>
    )}

    {canManage && r.status === 'ARRIVED' && (
      <div className="sale-row" style={{ marginTop: '0.75rem' }}>
        <button type="button" className="button button-primary" onClick={() => setShowComplete(!showComplete)}>
          {t('Record Weighment & Complete Purchase')}
        </button>
      </div>
    )}

    {showComplete && (
      <form className="sale-grid" onSubmit={handleCompleteSubmit} style={{ marginTop: '1rem', padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
        <h4>{t('Record Weighment & Settlement Details')}</h4>
        <Field name="actual_quantity" label="Actual Weighed Quantity (quintals)" type="number" defaultValue={r.quantity} step="0.001" min="0.001" />
        <Field name="settled_price" label="Final Settled Price (INR/quintal)" type="number" defaultValue={r.expected_price} step="0.01" min="0.01" />
        <Field name="deductions" label="Deductions (INR, if any)" type="number" defaultValue="0" step="0.01" min="0" required={false} />
        <Field name="payment_reference" label="Payment Reference / UTR Number" type="text" placeholder={t('e.g. UTR1234567890 or Cheque #102030')} />
        <label className="sale-field">
          {t('Payment Method')}
          <select name="payment_method" aria-label={t('Payment Method')} defaultValue="BANK_TRANSFER">
            <option value="BANK_TRANSFER">{t('Bank Transfer / NEFT / RTGS')}</option>
            <option value="CHEQUE">{t('Bank Cheque')}</option>
            <option value="CASH">{t('Cash against receipt')}</option>
            <option value="UPI">{t('UPI')}</option>
          </select>
        </label>
        <Field name="notes" label="Settlement Notes / Observations" type="text" required={false} />
        {error && <p role="alert" className="sale-error">{errorMessage(error)}</p>}
        <div className="sale-row">
          <button type="button" className="button" onClick={() => setShowComplete(false)}>{t('Cancel')}</button>
          <button type="submit" className="button button-primary" disabled={busy}>
            {busy ? t('Completing...') : t('Save & Complete Purchase')}
          </button>
        </div>
      </form>
    )}
  </article>;
}

function Field({name,label,type='text',defaultValue,required=true,step,min,max,placeholder}:{name:string;label:string;type?:string;defaultValue?:string|number;required?:boolean;step?:string;min?:string;max?:string;placeholder?:string}) {return <label className="sale-field">{t(label)}<input aria-label={t(label)} name={name} type={type} defaultValue={defaultValue} required={required} step={step} min={min} max={max} placeholder={placeholder} maxLength={2000}/></label>;}

export function OfferForm({profile,existing,onSaved}:{profile:Profile;existing:PurchaseOffer|null;onSaved:()=>void}) {
  const { access, switchTo } = useBusinessWorkspace();
  const [step,setStep] = useState(0),[error,setError] = useState(''),[busy,setBusy] = useState(false);
  const [crops,setCrops] = useState<{id:number;name:string}[]>([]);
  const [terms,setTerms] = useState<Record<string,FormDataEntryValue>>({});
  const [key,setKey] = useState(()=>crypto.randomUUID());
  const targetRole = profile.business_type === 'PRIVATE_MANDI' ? 'PRIVATE_MANDI_OWNER' : 'PRIVATE_BUYER';
  const choice = access?.workspaces.find(w => w.business_id === profile.id && (w.business_type === profile.business_type || w.role === targetRole)) ||
                 access?.workspaces.find(w => w.business_id === profile.id);
  const activeRole = access?.active_workspace.role;
  const active = access?.active_workspace.mode === 'BUSINESS' &&
                 access.active_workspace.business_id === profile.id &&
                 (!activeRole || activeRole === targetRole || (access.active_workspace as any).business_type === profile.business_type);
  const value=(name:keyof PurchaseTerms,fallback='')=>existing?.terms[name]===null ? '' : String(existing?.terms[name] ?? fallback);
  useEffect(()=>{api.commodities().then(setCrops).catch(e=>setError(e.message));},[]);
  const names=['Crop and quantity','Price and validity','Location','Logistics and payment','Review buying offer'];

  const defaultDates = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(Date.now() + (i + 1) * 86400000);
    return d.toISOString().split('T')[0];
  }).join(', ');
  const defaultStart = new Date().toISOString().slice(0, 16);
  const defaultExpiry = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 16);
  const defaultPriceValid = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16);

  async function directPublish(allTerms: Record<string, FormDataEntryValue>) {
    setBusy(true);
    setError('');
    let body: Record<string, unknown> = {};
    try {
      if (!active && choice) {
        try { await switchTo(choice); } catch {}
      }
      const amount = (name: string) => Number(allTerms[name]);
      if (!(amount('minimum_quantity') > 0 && amount('minimum_quantity') <= amount('maximum_quantity') && amount('maximum_quantity') <= amount('total_quantity'))) {
        setError(t('Minimum quantity must not exceed maximum quantity or total quantity.'));
        setBusy(false);
        return;
      }
      const stamps = ['starts_at','expires_at','price_valid_until'].map(name => new Date(String(allTerms[name])).getTime());
      if (stamps.some(v=>!Number.isFinite(v)) || !(stamps[0]<stamps[2] && stamps[2]<=stamps[1]) || stamps[2]<=Date.now()) {
        setError(t('Check start, expiry and price validity dates. Price validity must be in the future and within offer validity.'));
        setBusy(false);
        return;
      }
      body = { ...allTerms };
      for (const name of ['starts_at','expires_at','price_valid_until']) body[name] = new Date(String(allTerms[name])).toISOString();
      body.commodity_id = Number(allTerms.commodity_id);
      body.unit = 'quintal';
      body.appointment_required = allTerms.appointment_required === 'yes';
      body.arrival_dates = String(allTerms.arrival_dates).split(',').map(v=>v.trim()).filter(Boolean);
      body.payment_methods = String(allTerms.payment_methods).split(',').map(v=>v.trim()).filter(Boolean);
      body.image_references = String(allTerms.image_references||'').split('\n').map(v=>v.trim()).filter(Boolean);
      for (const n of ['daily_intake','minimum_price','maximum_price','pickup_charge','unloading_charge','latitude','longitude']) body[n] = allTerms[n] || null;
      const saved = await saleAPI<{ id: number; version: number; status: string }>(existing ? `/business/offers/${existing.id}` : '/business/offers', {...body,...(existing ? {version:existing.version} : {business_id:profile.id})}, key, existing ? 'PUT' : 'POST');
      if (!existing && saved?.status === 'DRAFT') {
        try {
          await saleAPI(`/business/offers/${saved.id}/publish`, { version: saved.version });
        } catch {
          // If already published or error, proceed
        }
      }
      onSaved();
    } catch(e) {
      if (e instanceof Error && e.message === 'active_business_workspace_required' && choice) {
        try {
          await switchTo(choice);
          const saved = await saleAPI<{ id: number; version: number; status: string }>(existing ? `/business/offers/${existing.id}` : '/business/offers', {...body,...(existing ? {version:existing.version} : {business_id:profile.id})}, key, existing ? 'PUT' : 'POST');
          if (!existing && saved?.status === 'DRAFT') {
            try { await saleAPI(`/business/offers/${saved.id}/publish`, { version: saved.version }); } catch {}
          }
          onSaved();
          return;
        } catch (retryErr) {
          setError(retryErr instanceof Error ? retryErr.message : 'Request failed');
          return;
        }
      }
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setBusy(false);
    }
  }

  async function submit(e:FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const next = { ...terms, ...Object.fromEntries(new FormData(e.currentTarget)) };
    setTerms(next);
    setError('');
    if (step < 4) {
      setStep(n => n + 1);
      return;
    }
    await directPublish(next);
  }

  function handleFastPublish() {
    const cid = String(terms.commodity_id || (crops[0] ? crops[0].id : 1));
    const merged: Record<string, FormDataEntryValue> = {
      commodity_id: cid,
      variety: terms.variety || 'local',
      grade: terms.grade || 'faq',
      crop_condition: terms.crop_condition || 'Standard fresh produce',
      quality_standards: terms.quality_standards || 'Fair Average Quality (FAQ), healthy and dry',
      total_quantity: terms.total_quantity || '50',
      minimum_quantity: terms.minimum_quantity || '1',
      maximum_quantity: terms.maximum_quantity || terms.total_quantity || '50',
      offered_price: terms.offered_price || '1400',
      price_kind: terms.price_kind || 'FIRM',
      price_basis: terms.price_basis || 'Net purchasing price at gate',
      starts_at: terms.starts_at || defaultStart,
      expires_at: terms.expires_at || defaultExpiry,
      price_valid_until: terms.price_valid_until || defaultPriceValid,
      purchasing_centre: terms.purchasing_centre || profile.name,
      address: terms.address || profile.address,
      district: terms.district || profile.district,
      state: terms.state || profile.state,
      service_area: terms.service_area || `${profile.district} and nearby areas`,
      transport: terms.transport || 'FARMER_DELIVERY',
      charge_basis: terms.charge_basis || 'INR_PER_QUINTAL',
      weighment: terms.weighment || 'Direct digital scale weighment',
      arrival_dates: terms.arrival_dates || defaultDates,
      appointment_required: terms.appointment_required || 'yes',
      payment_methods: terms.payment_methods || 'Bank Transfer, UPI',
      payment_timing: terms.payment_timing || 'Immediate upon weighment',
      payment_terms: terms.payment_terms || 'Net payment within 24 hours of weighment',
      known_deductions: terms.known_deductions || 'None (0 INR)',
      contact_availability: terms.contact_availability || 'Mon-Sat 08:00 - 18:00 IST',
      ...terms,
    };
    void directPublish(merged);
  }

  function input(name:keyof PurchaseTerms,label:string,type='text',required=true,fallback='',extra: {step?:string;min?:string}={}) {return <Field key={name} name={name} label={label} type={type} required={required} defaultValue={String(terms[name]??(type==='datetime-local' && existing ? localTime(value(name)) : value(name,fallback)))} {...extra}/>;}
  function select(name:keyof PurchaseTerms,label:string,values:string[],fallback=values[0]) {return <label className="sale-field">{t(label)}<select aria-label={t(label)} name={name} defaultValue={String(terms[name]??value(name,fallback))}>{values.map(v=><option key={v} value={v}>{labelStatus(v)}</option>)}</select></label>;}
  const moment=(name:keyof PurchaseTerms)=>existing ? localTime(value(name)) : '';
  return <section className="sale-card"><h3>{t(existing?'Edit buying offer':'Create New Buying Offer')}</h3>
    {!existing && (
      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1rem' }}>
        <strong style={{ fontSize: '0.85rem', color: '#166534', display: 'block', marginBottom: '0.4rem' }}>
          ⚡ {t('Quick 1-Click Presets (Click any preset to auto-fill everything):')}
        </strong>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { name: 'Tomato', emoji: '🍅', price: '1400', qty: '50' },
            { name: 'Onion', emoji: '🧅', price: '1800', qty: '100' },
            { name: 'Potato', emoji: '🥔', price: '1200', qty: '50' },
            { name: 'Arecanut', emoji: '🌴', price: '45000', qty: '20' },
          ].map(p => {
            const crop = crops.find(c => c.name.toLowerCase() === p.name.toLowerCase());
            return (
              <button
                key={p.name}
                type="button"
                className="button"
                style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem', background: '#fff' }}
                onClick={() => {
                  const cid = crop ? String(crop.id) : (crops[0] ? String(crops[0].id) : '1');
                  setTerms(prev => ({
                    ...prev,
                    commodity_id: cid,
                    variety: 'local',
                    grade: 'faq',
                    crop_condition: 'Standard fresh produce',
                    quality_standards: 'Fair Average Quality (FAQ), healthy and dry',
                    total_quantity: p.qty,
                    minimum_quantity: '1',
                    maximum_quantity: p.qty,
                    offered_price: p.price,
                    price_kind: 'FIRM',
                    price_basis: 'Net purchasing price at gate',
                    starts_at: defaultStart,
                    expires_at: defaultExpiry,
                    price_valid_until: defaultPriceValid,
                    purchasing_centre: profile.name,
                    address: profile.address,
                    district: profile.district,
                    state: profile.state,
                    service_area: `${profile.district} and nearby areas`,
                    transport: 'FARMER_DELIVERY',
                    charge_basis: 'INR_PER_QUINTAL',
                    weighment: 'Direct digital scale weighment',
                    arrival_dates: defaultDates,
                    appointment_required: 'yes',
                    payment_methods: 'Bank Transfer, UPI',
                    payment_timing: 'Immediate upon weighment',
                    payment_terms: 'Net payment within 24 hours of weighment',
                    known_deductions: 'None (0 INR)',
                    contact_availability: 'Mon-Sat 08:00 - 18:00 IST',
                  }));
                }}
              >
                {p.emoji} {p.name} (₹{p.price}/qtl · {p.qty} qtl)
              </button>
            );
          })}
        </div>
      </div>
    )}
    <p>{t('Step')} {step+1} / 5 · {t(names[step])}</p>
    <form key={step} className="sale-grid" onSubmit={submit} onChange={()=>setKey(crypto.randomUUID())}>
    {step===0 && <><label className="sale-field">{t('Crop')}<select name="commodity_id" aria-label={t('Crop')} value={String(terms.commodity_id??value('commodity_id'))} onChange={e=>setTerms(v=>({...v,commodity_id:e.target.value}))} required><option value="">{t('Choose crop')}</option>{crops.map(c=><option key={c.id} value={c.id}>{t(c.name)}</option>)}</select></label>{input('variety','Variety', 'text', true, 'local')}{input('grade','Grade or quality requirement', 'text', true, 'faq')}{input('crop_condition','Crop condition', 'text', true, 'Standard fresh produce')}{input('quality_standards','Acceptable quality standards', 'text', true, 'Fair Average Quality (FAQ)')}{input('total_quantity','Total quantity required (quintals)','number',true,'50',{step:'0.001',min:'0.001'})}{input('minimum_quantity','Minimum farmer quantity (quintals)','number',true,'1',{step:'0.001',min:'0.001'})}{input('maximum_quantity','Maximum farmer quantity (quintals)','number',true,'50',{step:'0.001',min:'0.001'})}{input('daily_intake','Maximum daily intake (quintals)','number',false,'',{step:'0.001',min:'0.001'})}<label className="sale-field">{t('Optional protected crop image references')}<textarea aria-label={t('Optional protected crop image references')} name="image_references" defaultValue={String(terms.image_references??existing?.terms.image_references?.join('\n')??'')}/><small>{t('Secure image uploads are not enabled. References are not exposed to farmers.')}</small></label></>}
    {step===1 && <>{input('offered_price','Offered price (INR/quintal)','number',true,'1400',{step:'0.01',min:'0.01'})}{select('price_kind','Price type',['FIRM','INDICATIVE','NEGOTIABLE'])}{input('minimum_price','Minimum negotiable price (INR/quintal)','number',false,'',{step:'0.01',min:'0.01'})}{input('maximum_price','Maximum offered price (INR/quintal)','number',false,'',{step:'0.01',min:'0.01'})}{input('price_basis','Price basis', 'text', true, 'Net purchasing price at gate')}{input('starts_at','Offer starts (your local time)','datetime-local',true,moment('starts_at') || defaultStart)}{input('expires_at','Offer expires (your local time)','datetime-local',true,moment('expires_at') || defaultExpiry)}{input('price_valid_until','Price valid until (your local time)','datetime-local',true,moment('price_valid_until') || defaultPriceValid)}<p>{t('Indicative and negotiable prices are not guaranteed prices.')}</p></>}
    {step===2 && <>{input('purchasing_centre','Purchasing centre','text',true,profile.name)}{input('address','Complete address','text',true,profile.address)}{input('district','District','text',true,profile.district)}{input('state','State','text',true,profile.state)}{input('latitude','Latitude','number',false,'',{step:'0.000001'})}{input('longitude','Longitude','number',false,'',{step:'0.000001'})}{input('service_area','Service or pickup area', 'text', true, `${profile.district} and surrounding taluks`)}</>}
    {step===3 && <>{select('transport','Transport arrangement',['FARMER_DELIVERY','BUSINESS_PICKUP'])}{input('pickup_charge','Pickup charge (INR)','number',false,'',{step:'0.01',min:'0'})}{input('unloading_charge','Unloading charge (INR)','number',false,'',{step:'0.01',min:'0'})}{select('charge_basis','Charge basis',['INR_PER_QUINTAL','INR_PER_TRIP'])}{input('weighment','Weighment arrangements', 'text', true, 'Direct digital scale weighment')}{input('arrival_dates','Arrival dates (YYYY-MM-DD, comma separated)','text',true,existing?.terms.arrival_dates?.join(', ')||defaultDates)}{select('appointment_required','Appointment required',['yes','no'],existing?.terms.appointment_required===false?'no':'yes')}{input('payment_methods','Payment methods (comma separated)','text',true,existing?.terms.payment_methods?.join(', ')||'Bank Transfer, UPI')}{input('payment_timing','Payment timing', 'text', true, 'Immediate upon weighment')}{input('payment_terms','Payment terms', 'text', true, 'Net payment within 24 hours of weighment')}{input('known_deductions','Known deductions', 'text', true, 'None (0 INR)')}{input('instructions','Buyer instructions','text',false)}{input('contact_availability','Contact availability', 'text', true, 'Mon-Sat 08:00 - 18:00 IST')}{input('special_requirements','Special crop requirements','text',false)}</>}
    {step===4 && <><p className="sale-notice">{t('Review every term before saving. New offers are drafts until explicitly published. Existing accepted response terms will not change.')}</p><dl className="sale-ledger">{Object.entries(terms).map(([k,v])=><div key={k}><dt>{t(k.replaceAll('_',' '))}</dt><dd>{String(v)||t('Unknown')}</dd></div>)}</dl></>}
    {error && <p role="alert" className="sale-error">{errorMessage(error)}</p>}
    <div className="sale-row" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
      {step>0 && <button type="button" className="button" onClick={e=>{const form=e.currentTarget.closest('form');if(form)setTerms(v=>({...v,...Object.fromEntries(new FormData(form))}));setStep(n=>n-1);}}>{t('Back')}</button>}
      <button type="submit" className="button button-primary" disabled={busy}>{t(step===4?'Save buying offer':'Continue')}</button>
      {step===0 && !existing && (
        <button
          type="button"
          className="button"
          style={{ background: '#16a34a', color: '#fff', borderColor: '#15803d' }}
          disabled={busy}
          onClick={handleFastPublish}
        >
          {busy ? t('Publishing...') : `⚡ ${t('Fast 1-Click Publish with Smart Defaults')}`}
        </button>
      )}
    </div>
  </form></section>;
}
