import { useEffect, useState, type FormEvent } from 'react';
import { api } from './api';
import { useBusinessWorkspace } from './business-context';
import { getLanguage, t } from './i18n';
import { purchaseAPI, type PrivateRequest, type PurchaseAnalytics, type PurchaseNote, type PurchaseOffer, type PurchaseTerms } from './purchase-api';
import { saleAPI } from './sale-api';

interface Profile {id: number; business_type: string; name: string; address: string; district: string; state: string; can_publish: boolean}
const sections = ['Overview', 'My Buying Offers', 'Create Buying Offer', 'Incoming Farmer Requests', 'Accepted Requests', 'Appointments', 'Completed Purchases', 'Notifications', 'Business Profile', 'Settings'] as const;
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
  };
  return translated !== value ? translated : (hints[value] || value);
};

const localTime = (v: string) => {const d = new Date(v); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0,16);};

export function BusinessPurchasing({profile}: {profile: Profile}) {
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
  const active = access?.active_workspace.mode === 'BUSINESS' && access.active_workspace.business_id === profile.id;
  useEffect(() => {
    if (!active) return;
    let alive = true; setLoading(true); setError(''); setOffers([]); setRequests([]); setNotes({unread:0,items:[]}); setAnalytics(null);
    Promise.all([purchaseAPI.offers(profile.id, offset), purchaseAPI.requests(profile.id, offset), purchaseAPI.analytics(profile.id), purchaseAPI.notes(profile.id, offset)])
      .then(([o,r,a,n]) => {if (alive) {setOffers(o);setRequests(r);setAnalytics(a);setNotes(n);}})
      .catch(e => {if (alive) setError(e.message);}).finally(() => {if (alive) setLoading(false);});
    return () => {alive=false;};
  }, [profile.id, active, reload, offset]);
  const refresh = () => {setDetail(null); setReload(n => n+1);};
  const choice = access?.workspaces.find(w => w.business_id === profile.id);
  if (!active) return <section className="sale-card"><p>{t('Select this authorized business workspace to manage purchasing.')}</p>{choice && <button className="button button-primary" onClick={() => void switchTo(choice).catch(e => setError(e.message))}>{t('Open purchasing workspace')}</button>}{error && <p role="alert">{errorMessage(error)}</p>}</section>;
  const displayedRequests = section === 'Accepted Requests' ? requests.filter(r => ['ACCEPTED','CONFIRMED'].includes(r.status)) : requests;
  async function offerAction(offer: PurchaseOffer, verb: string) {setError(''); try {await saleAPI(`/business/offers/${offer.id}/${verb}`, {version: offer.version});refresh();} catch(e) {setError(e instanceof Error ? e.message : 'Request failed');}}
  return <section className="business-purchasing">
    <button type="button" className="button" onClick={refresh} disabled={loading}>{t('Refresh purchasing records')}</button>
    <header className="sale-row"><h2>{t(profile.business_type === 'PRIVATE_MANDI' ? 'Private mandi purchasing' : 'Private buyer purchasing')}</h2>{profile.can_publish && <button className="button button-primary" onClick={() => {setEditing(null);setSection('Create Buying Offer');}}>{t('Create New Buying Offer')}</button>}</header>
    <nav className="purchase-tabs" aria-label={t('Purchasing sections')}>{sections.map(s => <button key={s} type="button" aria-current={section===s ? 'page' : undefined} onClick={() => {setSection(s);setOffset(0);setDetail(null);}}>{t(s)}{s==='Notifications' ? ` (${notes.unread})` : ''}</button>)}</nav>
    {error && <p role="alert" className="sale-error">{errorMessage(error)} <button onClick={refresh}>{t('Retry')}</button></p>}
    {loading && <p role="status">{t('Loading purchasing records')}</p>}
    {section==='Overview' && analytics && <><div className="purchase-stats">{[['Buying offers',analytics.offer_count],['Incoming requests',analytics.incoming_requests],['Requested quintals',analytics.requested_quantity],['Confirmed quintals',analytics.confirmed_quantity],['Reserved quintals',analytics.reserved_quantity],['Remaining quintals',analytics.remaining_quantity],['Average listed price',analytics.average_offered_price ? rupees(analytics.average_offered_price) : t('Unavailable')],['Completed purchases',analytics.completed_purchases]].map(([label,value]) => <article className="sale-card" key={label}><span>{t(String(label))}</span><strong>{value}</strong></article>)}</div><p>{t('Submitted requests do not reserve quantity. Business responses reserve it until expiry; farmer confirmation commits it.')}</p><p>{t('Average listed price is an unweighted average across your offers, not a realized selling price.')}</p></>}
    {section==='Create Buying Offer' && profile.can_publish && <OfferForm key={editing?.id || 'new'} profile={profile} existing={editing} onSaved={() => {setSection('My Buying Offers');setEditing(null);refresh();}} />}
    {section==='My Buying Offers' && <>{!loading && !offers.length && <p>{t('No buying offers yet. Create your first offer.')}</p>}{offers.map(o => <article className="sale-card" key={o.id}><div className="sale-row"><h3>{o.commodity_name} · {o.terms.variety} · {o.terms.grade}</h3><span className="sale-status">{labelStatus(o.status)}</span></div><p>{rupees(String(o.terms.offered_price))} / {t('quintal')} · {labelStatus(o.terms.price_kind)} · {o.terms.purchasing_centre}</p><p>{t('Remaining')}: {o.quantity_remaining} / {o.quantity_required} {t('quintals')} · {t('Reserved')}: {o.quantity_reserved} · {t('Committed')}: {o.quantity_committed}</p><p>{t('Requests')}: {o.request_count} · {t('Offer expiry')}: {dateTime(o.terms.expires_at)}</p><p>{t('Last price update')}: {dateTime(o.price_updated_at)}</p>{o.terms.price_kind!=='FIRM' && <p className="sale-notice">{t('Indicative and negotiable prices are not guaranteed prices.')}</p>}<div className="sale-row"><button className="button" onClick={() => void purchaseAPI.offer(o.id).then(setDetail).catch(e=>setError(e.message))}>{t('Details and revision history')}</button>{profile.can_publish && o.status!=='CANCELLED' && <><button className="button" onClick={() => {setEditing(o);setSection('Create Buying Offer');}}>{t('Edit offer')}</button>{['DRAFT','PAUSED'].includes(o.status) && <button className="button" onClick={() => void offerAction(o,'publish')}>{t(o.status==='PAUSED' ? 'Resume offer' : 'Publish offer')}</button>}{['PUBLISHED','PARTIALLY_FILLED','FULLY_FILLED'].includes(o.status) && <button className="button" onClick={() => void offerAction(o,'pause')}>{t('Pause offer')}</button>}<button className="button" onClick={() => {if (window.confirm(t('Cancel publication? Existing response agreements remain unchanged.'))) void offerAction(o,'cancel');}}>{t('Cancel offer')}</button></>}</div></article>)}{detail && <article className="sale-card"><h3>{t('Offer terms and revisions')}</h3><TermDetails terms={detail.terms} /><h4>{t('Price history')}</h4><ol>{detail.price_history?.map((p,i)=><li key={i}>{rupees(p.price)} · {labelStatus(p.kind)} · {dateTime(p.created_at)}</li>)}</ol><h4>{t('Revision history')}</h4><ol>{detail.history?.map((h,i)=><li key={i}>{h.action} · #{h.revision} · {dateTime(h.created_at)}<details><summary>{t('Exact saved terms')}</summary><pre>{JSON.stringify(h.snapshot,null,2)}</pre></details></li>)}</ol></article>}</>}
    {['Incoming Farmer Requests','Accepted Requests'].includes(section) && <>{!loading && !displayedRequests.length && <p>{t('No matching farmer requests.')}</p>}{displayedRequests.map(r => <RequestCard key={`${r.id}:${r.version}`} request={r} canManage={profile.can_publish} onChange={refresh}/>)}</>}
    {section==='Appointments' && analytics && <><p className="sale-notice">{t('These are farmer-confirmed arrival terms. Appointment booking and arrival recording are not available in this stage.')}</p>{analytics.upcoming_arrivals.map(r=><article className="sale-card" key={r.request_id}>#{r.request_id} · {dateTime(r.arrival_at)} · {r.quantity} {t('quintals')} · {rupees(r.price)} / {t('quintal')}</article>)}{!analytics.upcoming_arrivals.length && <p>{t('No confirmed upcoming arrivals.')}</p>}</>}
    {section==='Completed Purchases' && <p className="sale-notice">{t('No completed purchase records exist. Actual weighment, payment and completion recording will be available in the farmer workflow stage.')}</p>}
    {section==='Notifications' && <>{!loading && !notes.items.length && <p>{t('No purchasing notifications.')}</p>}{notes.items.map(n=><article className="sale-card" key={n.id}><p>{n.message[getLanguage()]}</p><p>{dateTime(n.created_at)} · {t('Offer')} #{n.offer_id} {n.request_id && ` · #${n.request_id}`}</p>{!n.read_at && <button className="button" onClick={() => void saleAPI(`/private-purchases/notifications/${n.id}/read`, {}).then(refresh).catch(e=>setError(e.message))}>{t('Mark read')}</button>}</article>)}</>}
    {section==='Business Profile' && <article className="sale-card"><h3>{profile.name}</h3><p>{profile.address}, {profile.district}, {profile.state}</p><p>{t('Profile and verification documents are shown above. Profile changes require administrator review.')}</p></article>}
    {section==='Settings' && <article className="sale-card"><h3>{t('Notification settings')}</h3><p>{t('In-app purchasing notifications are active. External purchasing messages are not enabled in this stage.')}</p><p>{t('Use the language controls above to choose English or Kannada. Manage authorized workspaces through the top switch.')}</p></article>}
    {['My Buying Offers','Incoming Farmer Requests','Accepted Requests','Notifications'].includes(section) && <div className="sale-row"><button className="button" disabled={offset===0 || loading} onClick={()=>setOffset(n=>Math.max(0,n-50))}>{t('Previous page')}</button><span>{t('Page')} {offset/50+1}</span><button className="button" disabled={loading || (section==='My Buying Offers' ? offers.length : section==='Notifications' ? notes.items.length : requests.length)<50} onClick={()=>setOffset(n=>n+50)}>{t('Next page')}</button></div>}
  </section>;
}

function TermDetails({terms}: {terms: PurchaseTerms}) {return <dl className="sale-ledger">{Object.entries(terms).map(([key,v]) => <div key={key}><dt>{t(key.replaceAll('_',' '))}</dt><dd>{v===null || v==='' ? t('Unknown') : Array.isArray(v) ? v.join(', ') : String(v)}</dd></div>)}</dl>;}

function RequestCard({request:r,canManage,onChange}:{request:PrivateRequest;canManage:boolean;onChange:()=>void}) {
  const [action,setAction] = useState<'accept'|'counteroffer'|'reject'>('accept');
  const [busy,setBusy] = useState(false), [error,setError] = useState('');
  async function submit(e:FormEvent<HTMLFormElement>) {e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));if (!window.confirm(t('Send this response with the displayed terms?'))) return;setBusy(true);setError('');try {await saleAPI(`/business/requests/${r.id}/${action}`,action==='reject' ? {version:r.version,reason:data.reason} : {version:r.version,quantity:data.quantity,price:data.price,arrival_at:new Date(String(data.arrival_at)).toISOString(),expires_at:new Date(String(data.expires_at)).toISOString(),payment_terms:data.payment_terms,message:data.message});onChange();} catch(e) {setError(e instanceof Error ? e.message : 'Request failed');} finally {setBusy(false);}}
  return <article className="sale-card"><div className="sale-row"><h3>{r.public_id}</h3><span className="sale-status">{labelStatus(r.status)}</span></div><p>{r.farmer_name} · {r.details.variety} / {r.details.grade} · {t('Offer')} #{r.offer_id}</p><p>{r.quantity} {t('quintals')} · {t('Expected price')}: {rupees(r.expected_price)} / {t('quintal')}</p><p>{t('Requested arrival')}: {dateTime(r.arrival_at)} · {t('Submitted')}: {dateTime(r.created_at)}</p>{r.farmer_phone && <p>{t('Consented verified phone')}: {r.farmer_phone}</p>}<p>{r.details.message}</p><details><summary>{t('Full request details and history')}</summary><ol>{r.history.map((h,i)=><li key={i}>{labelStatus(h.action)} · {dateTime(h.created_at)}</li>)}</ol>{r.responses.map(response=><section key={response.id}><h4>{labelStatus(response.kind)}</h4><p>{response.quantity} {t('quintals')} · {rupees(response.price)} / {t('quintal')} · {dateTime(response.arrival_at)}</p><p>{t('Response expiry')}: {dateTime(response.expires_at)}</p><TermDetails terms={response.terms}/></section>)}</details>
    {canManage && ['SUBMITTED','ACCEPTED','COUNTEROFFERED'].includes(r.status) && <form className="sale-grid" onSubmit={submit}><label className="sale-field">{t('Response action')}<select aria-label={t('Response action')} value={action} onChange={e=>setAction(e.target.value as typeof action)}><option value="accept">{t('Accept request')}</option><option value="counteroffer">{t('Counteroffer')}</option><option value="reject">{t('Reject request')}</option></select></label>{action==='reject' ? <Field name="reason" label="Rejection reason or message" required={false}/> : <><Field name="quantity" label="Accepted quantity (quintals)" type="number" defaultValue={r.quantity} step="0.001" min="0.001" max={r.quantity}/><Field name="price" label="Confirmed price (INR/quintal)" type="number" defaultValue={r.expected_price} step="0.01" min="0.01"/><Field name="arrival_at" label="Arrival date and time (your local time)" type="datetime-local" defaultValue={localTime(r.arrival_at)}/><Field name="expires_at" label="Response expiry (your local time)" type="datetime-local"/><Field name="payment_terms" label="Confirm payment terms"/><Field name="message" label="Response explanation" required={false}/><p>{t('This response reserves quantity until expiry. The farmer must confirm; this is not a completed purchase.')}</p></>}{error && <p role="alert">{errorMessage(error)}</p>}<button className="button button-primary" disabled={busy}>{t('Send response')}</button></form>}
  </article>;
}

function Field({name,label,type='text',defaultValue,required=true,step,min,max}:{name:string;label:string;type?:string;defaultValue?:string|number;required?:boolean;step?:string;min?:string;max?:string}) {return <label className="sale-field">{t(label)}<input aria-label={t(label)} name={name} type={type} defaultValue={defaultValue} required={required} step={step} min={min} max={max} maxLength={2000}/></label>;}

export function OfferForm({profile,existing,onSaved}:{profile:Profile;existing:PurchaseOffer|null;onSaved:()=>void}) {
  const [step,setStep] = useState(0),[error,setError] = useState(''),[busy,setBusy] = useState(false);
  const [crops,setCrops] = useState<{id:number;name:string}[]>([]);
  const [terms,setTerms] = useState<Record<string,FormDataEntryValue>>({});
  const [key,setKey] = useState(()=>crypto.randomUUID());
  const value=(name:keyof PurchaseTerms,fallback='')=>existing?.terms[name]===null ? '' : String(existing?.terms[name] ?? fallback);
  useEffect(()=>{api.commodities().then(setCrops).catch(e=>setError(e.message));},[]);
  const names=['Crop and quantity','Price and validity','Location','Logistics and payment','Review buying offer'];
  async function submit(e:FormEvent<HTMLFormElement>) {
    e.preventDefault();const next={...terms,...Object.fromEntries(new FormData(e.currentTarget))};setTerms(next);setError('');
    if(step<4){setStep(n=>n+1);return;}
    const amount = (name: string) => Number(next[name]);
    if (!(amount('minimum_quantity') > 0 && amount('minimum_quantity') <= amount('maximum_quantity') && amount('maximum_quantity') <= amount('total_quantity'))) {setError(t('Minimum quantity must not exceed maximum quantity or total quantity.'));return;}
    if (next.minimum_price && (next.price_kind !== 'NEGOTIABLE' || amount('minimum_price') > amount('offered_price'))) {setError(t('Minimum price requires a negotiable quote and cannot exceed the offered price.'));return;}
    if (next.maximum_price && amount('maximum_price') < amount('offered_price')) {setError(t('Maximum price cannot be below the offered price.'));return;}
    const stamps = ['starts_at','expires_at','price_valid_until'].map(name => new Date(String(next[name])).getTime());
    if (stamps.some(v=>!Number.isFinite(v)) || !(stamps[0]<stamps[2] && stamps[2]<=stamps[1]) || stamps[2]<=Date.now()) {setError(t('Check start, expiry and price validity dates. Price validity must be in the future and within offer validity.'));return;}
    const body: Record<string,unknown>={...next};
    for(const name of ['starts_at','expires_at','price_valid_until']) body[name]=new Date(String(next[name])).toISOString();
    body.commodity_id=Number(next.commodity_id);body.unit='quintal';body.appointment_required=next.appointment_required==='yes';
    body.arrival_dates=String(next.arrival_dates).split(',').map(v=>v.trim()).filter(Boolean);
    body.payment_methods=String(next.payment_methods).split(',').map(v=>v.trim()).filter(Boolean);
    body.image_references=String(next.image_references||'').split('\n').map(v=>v.trim()).filter(Boolean);
    for(const n of ['daily_intake','minimum_price','maximum_price','pickup_charge','unloading_charge','latitude','longitude']) body[n]=next[n] || null;
    setBusy(true);
    try {await saleAPI(existing ? `/business/offers/${existing.id}` : '/business/offers', {...body,...(existing ? {version:existing.version} : {business_id:profile.id})},key,existing ? 'PUT' : 'POST');onSaved();}catch(e){setError(e instanceof Error ? e.message : 'Request failed');}finally{setBusy(false);}
  }
  function input(name:keyof PurchaseTerms,label:string,type='text',required=true,fallback='',extra: {step?:string;min?:string}={}) {return <Field key={name} name={name} label={label} type={type} required={required} defaultValue={String(terms[name]??(type==='datetime-local' && existing ? localTime(value(name)) : value(name,fallback)))} {...extra}/>;}
  function select(name:keyof PurchaseTerms,label:string,values:string[],fallback=values[0]) {return <label className="sale-field">{t(label)}<select aria-label={t(label)} name={name} defaultValue={String(terms[name]??value(name,fallback))}>{values.map(v=><option key={v} value={v}>{labelStatus(v)}</option>)}</select></label>;}
  const moment=(name:keyof PurchaseTerms)=>existing ? localTime(value(name)) : '';
  return <section className="sale-card"><h3>{t(existing?'Edit buying offer':'Create New Buying Offer')}</h3><p>{t('Step')} {step+1} / 5 · {t(names[step])}</p><form key={step} className="sale-grid" onSubmit={submit} onChange={()=>setKey(crypto.randomUUID())}>
    {step===0 && <><label className="sale-field">{t('Crop')}<select name="commodity_id" aria-label={t('Crop')} value={String(terms.commodity_id??value('commodity_id'))} onChange={e=>setTerms(v=>({...v,commodity_id:e.target.value}))} required><option value="">{t('Choose crop')}</option>{crops.map(c=><option key={c.id} value={c.id}>{t(c.name)}</option>)}</select></label>{input('variety','Variety')}{input('grade','Grade or quality requirement')}{input('crop_condition','Crop condition')}{input('quality_standards','Acceptable quality standards')}{input('total_quantity','Total quantity required (quintals)','number',true,'',{step:'0.001',min:'0.001'})}{input('minimum_quantity','Minimum farmer quantity (quintals)','number',true,'',{step:'0.001',min:'0.001'})}{input('maximum_quantity','Maximum farmer quantity (quintals)','number',true,'',{step:'0.001',min:'0.001'})}{input('daily_intake','Maximum daily intake (quintals)','number',false,'',{step:'0.001',min:'0.001'})}<label className="sale-field">{t('Optional protected crop image references')}<textarea aria-label={t('Optional protected crop image references')} name="image_references" defaultValue={String(terms.image_references??existing?.terms.image_references?.join('\n')??'')}/><small>{t('Secure image uploads are not enabled. References are not exposed to farmers.')}</small></label><p>{t('Remaining and committed quantities are calculated by the server. To change the requirement, edit total quantity; it cannot fall below reservations and commitments.')}</p></>}
    {step===1 && <>{input('offered_price','Offered price (INR/quintal)','number',true,'',{step:'0.01',min:'0.01'})}{select('price_kind','Price type',['FIRM','INDICATIVE','NEGOTIABLE'])}{input('minimum_price','Minimum negotiable price (INR/quintal)','number',false,'',{step:'0.01',min:'0.01'})}{input('maximum_price','Maximum offered price (INR/quintal)','number',false,'',{step:'0.01',min:'0.01'})}{input('price_basis','Price basis')}{input('starts_at','Offer starts (your local time)','datetime-local',true,moment('starts_at'))}{input('expires_at','Offer expires (your local time)','datetime-local',true,moment('expires_at'))}{input('price_valid_until','Price valid until (your local time)','datetime-local',true,moment('price_valid_until'))}<p>{t('Indicative and negotiable prices are not guaranteed prices.')}</p></>}
    {step===2 && <>{input('purchasing_centre','Purchasing centre','text',true,profile.name)}{input('address','Complete address','text',true,profile.address)}{input('district','District','text',true,profile.district)}{input('state','State','text',true,profile.state)}{input('latitude','Latitude','number',false,'',{step:'0.000001'})}{input('longitude','Longitude','number',false,'',{step:'0.000001'})}{input('service_area','Service or pickup area')}</>}
    {step===3 && <>{select('transport','Transport arrangement',['FARMER_DELIVERY','BUSINESS_PICKUP'])}{input('pickup_charge','Pickup charge (INR)','number',false,'',{step:'0.01',min:'0'})}{input('unloading_charge','Unloading charge (INR)','number',false,'',{step:'0.01',min:'0'})}{select('charge_basis','Charge basis',['INR_PER_QUINTAL','INR_PER_TRIP'])}{input('weighment','Weighment arrangements')}{input('arrival_dates','Arrival dates (YYYY-MM-DD, comma separated)','text',true,existing?.terms.arrival_dates?.join(', ')||'')}{select('appointment_required','Appointment required',['yes','no'],existing?.terms.appointment_required===false?'no':'yes')}{input('payment_methods','Payment methods (comma separated)','text',true,existing?.terms.payment_methods?.join(', ')||'')}{input('payment_timing','Payment timing')}{input('payment_terms','Payment terms')}{input('known_deductions','Known deductions')}{input('instructions','Buyer instructions','text',false)}{input('contact_availability','Contact availability')}{input('special_requirements','Special crop requirements','text',false)}<p>{t('Leave unknown charges blank. Zero means the business explicitly confirms no charge.')}</p></>}
    {step===4 && <><p className="sale-notice">{t('Review every term before saving. New offers are drafts until explicitly published. Existing accepted response terms will not change.')}</p><dl className="sale-ledger">{Object.entries(terms).map(([k,v])=><div key={k}><dt>{t(k.replaceAll('_',' '))}</dt><dd>{String(v)||t('Unknown')}</dd></div>)}</dl></>}
    {error && <p role="alert" className="sale-error">{errorMessage(error)}</p>}<div className="sale-row">{step>0 && <button type="button" className="button" onClick={e=>{const form=e.currentTarget.closest('form');if(form)setTerms(v=>({...v,...Object.fromEntries(new FormData(form))}));setStep(n=>n-1);}}>{t('Back')}</button>}<button className="button button-primary" disabled={busy}>{t(step===4?'Save buying offer':'Continue')}</button></div>
  </form></section>;
}
