import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api';
import { purchaseAPI, type PrivateRateOffer, type PrivateRequest } from './purchase-api';
import { rupees } from './BusinessPurchasing';
import { t } from './i18n';
import './sales.css';

const stateName = (value: string) => t(value.replaceAll('_', ' '));
const formatDateTime = (v: string) => new Date(v).toLocaleDateString('en-IN', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Kolkata',
});

export function PrivateRatesPage() {
  const [tab, setTab] = useState<'PRIVATE_MANDI' | 'PRIVATE_BUYER'>('PRIVATE_MANDI');
  const [offers, setOffers] = useState<PrivateRateOffer[]>([]);
  const [crops, setCrops] = useState<{ id: number; name: string }[]>([]);
  const [selectedCrop, setSelectedCrop] = useState<string>('');
  const [variety, setVariety] = useState<string>('');
  const [district, setDistrict] = useState<string>('');
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('price_desc');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [activeOffer, setActiveOffer] = useState<PrivateRateOffer | null>(null);

  useEffect(() => {
    api.commodities().then(setCrops).catch(() => {});
  }, []);

  const loadOffers = () => {
    setLoading(true);
    setError('');
    purchaseAPI
      .privateRates({
        business_type: tab,
        crop_id: selectedCrop ? Number(selectedCrop) : undefined,
        variety: variety.trim() || undefined,
        district: district.trim() || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        sort_by: sortBy,
      })
      .then(rows => setOffers(rows))
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load rates'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadOffers();
  }, [tab, selectedCrop, variety, district, minPrice, maxPrice, sortBy]);

  return (
    <section className="sale-workspace private-rates-page">
      <header>
        <p className="eyebrow">{t('PRIVATE MARKETPLACE')}</p>
        <h1>{t('Private Mandi & Buyer Rates')}</h1>
        <p className="sale-notice">
          {t('Real-time purchasing offers published directly by verified private mandis and licensed private buyers in Karnataka. Prices and terms are legally binding upon mutual agreement.')}
        </p>
      </header>

      <nav className="purchase-tabs" role="tablist" aria-label={t('Business rates categories')}>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'PRIVATE_MANDI'}
          aria-current={tab === 'PRIVATE_MANDI' ? 'page' : undefined}
          onClick={() => setTab('PRIVATE_MANDI')}
        >
          🏪 {t('Private Mandis')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'PRIVATE_BUYER'}
          aria-current={tab === 'PRIVATE_BUYER' ? 'page' : undefined}
          onClick={() => setTab('PRIVATE_BUYER')}
        >
          🤝 {t('Private Buyers')}
        </button>
      </nav>

      {/* Filters & Sorting */}
      <div className="sale-card filter-card">
        <div className="sale-grid filter-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
          <label className="sale-field">
            {t('Crop')}
            <select value={selectedCrop} onChange={e => setSelectedCrop(e.target.value)} aria-label={t('Filter by Crop')}>
              <option value="">{t('All crops')}</option>
              {crops.map(c => (
                <option key={c.id} value={c.id}>{t(c.name)}</option>
              ))}
            </select>
          </label>

          <label className="sale-field">
            {t('Variety')}
            <input
              type="text"
              placeholder={t('e.g. Local, Hybrid')}
              value={variety}
              onChange={e => setVariety(e.target.value)}
              aria-label={t('Filter by Variety')}
            />
          </label>

          <label className="sale-field">
            {t('District')}
            <input
              type="text"
              placeholder={t('e.g. Kolar, Bengaluru')}
              value={district}
              onChange={e => setDistrict(e.target.value)}
              aria-label={t('Filter by District')}
            />
          </label>

          <label className="sale-field">
            {t('Min Price (₹)')}
            <input
              type="number"
              placeholder="0"
              value={minPrice}
              onChange={e => setMinPrice(e.target.value)}
              aria-label={t('Minimum Price')}
            />
          </label>

          <label className="sale-field">
            {t('Max Price (₹)')}
            <input
              type="number"
              placeholder="10000"
              value={maxPrice}
              onChange={e => setMaxPrice(e.target.value)}
              aria-label={t('Maximum Price')}
            />
          </label>

          <label className="sale-field">
            {t('Sort by')}
            <select value={sortBy} onChange={e => setSortBy(e.target.value)} aria-label={t('Sort Offers')}>
              <option value="price_desc">{t('Highest offered price')}</option>
              <option value="net_realization_desc">{t('Highest estimated net realization')}</option>
              <option value="updated_desc">{t('Recently updated')}</option>
            </select>
          </label>
        </div>
      </div>

      {error && <p role="alert" className="sale-error">{t(error)}</p>}
      {loading && <p role="status">{t('Loading verified private marketplace offers...')}</p>}

      {!loading && offers.length === 0 && !error && (
        <section className="sale-card">
          <h3>{t('No active purchasing offers found')}</h3>
          <p>{t('There are currently no active purchasing offers from verified')} {t(tab === 'PRIVATE_MANDI' ? 'private mandis' : 'private buyers')} {t('matching your filter criteria.')}</p>
        </section>
      )}

      <div className="offers-list" aria-live="polite">
        {offers.map(offer => (
          <OfferCard key={offer.offer_id} offer={offer} onRequest={() => setActiveOffer(offer)} />
        ))}
      </div>

      {activeOffer && (
        <SellingRequestModal
          offer={activeOffer}
          onClose={() => setActiveOffer(null)}
          onSuccess={() => {
            setActiveOffer(null);
            loadOffers();
          }}
        />
      )}
    </section>
  );
}

function OfferCard({ offer, onRequest }: { offer: PrivateRateOffer; onRequest: () => void }) {
  const isFirm = offer.price_kind === 'FIRM';
  const apmcPrice = offer.apmc_reference_modal_price;

  return (
    <article className="sale-card offer-card">
      <div className="sale-row" style={{ alignItems: 'flex-start' }}>
        <div>
          <h2>{offer.business_name}</h2>
          <p className="eyebrow" style={{ margin: '0.2rem 0' }}>
            {t(offer.business_type === 'PRIVATE_MANDI' ? 'Verified Private Mandi' : 'Verified Private Buyer')} · {offer.district}, {offer.state}
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--brand, #166534)' }}>
            {rupees(offer.offered_price)} <small style={{ fontSize: '0.85rem', fontWeight: 400 }}>/ {t('quintal')}</small>
          </div>
          <span className={`sale-status status-${offer.price_kind.toLowerCase()}`}>
            {stateName(offer.price_kind)} {isFirm ? `(${t('Fixed')})` : `(${t('Negotiable')})`}
          </span>
        </div>
      </div>

      <dl className="sale-ledger" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', margin: '1rem 0' }}>
        <div>
          <dt>{t('Crop & Variety')}</dt>
          <dd><strong>{offer.commodity_name}</strong> · {offer.variety} ({offer.grade})</dd>
        </div>
        <div>
          <dt>{t('Capacity & Limits')}</dt>
          <dd>{offer.quantity_remaining} / {offer.quantity_required} {t('quintals')} (Min: {offer.minimum_quantity}, Max: {offer.maximum_quantity})</dd>
        </div>
        <div>
          <dt>{t('Address / Delivery Point')}</dt>
          <dd>{offer.address}</dd>
        </div>
        <div>
          <dt>{t('Transport & Handling')}</dt>
          <dd>
            {stateName(offer.transport)}
            {offer.unloading_charge ? ` · Unloading: ₹${offer.unloading_charge}` : ''}
            {offer.pickup_charge ? ` · Pickup: ₹${offer.pickup_charge}` : ''}
          </dd>
        </div>
        <div>
          <dt>{t('Offer Validity')}</dt>
          <dd>{formatDateTime(offer.expires_at)}</dd>
        </div>
        <div>
          <dt>{t('Last Price Update')}</dt>
          <dd>{formatDateTime(offer.price_updated_at)}</dd>
        </div>
      </dl>

      {/* Financial Realization & APMC Comparison */}
      <div className="sale-card" style={{ background: '#f8fafc', borderColor: '#e2e8f0', margin: '0.75rem 0' }}>
        <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>💰 {t('Price & Net Realization Comparison')}</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.9rem' }}>
          <div>
            <span style={{ color: '#64748b' }}>{t('Gross Offered Price')}:</span>
            <div><strong>{rupees(offer.offered_price)}</strong> / {t('quintal')}</div>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>{t('APMC Benchmark Modal')}:</span>
            <div>{apmcPrice ? <strong>{rupees(String(apmcPrice))} / {t('quintal')}</strong> : <em>{t('No local APMC rate')}</em>}</div>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>{t('Known Deductions')}:</span>
            <div>{offer.unloading_charge || offer.pickup_charge ? `₹${(Number(offer.unloading_charge || 0) + Number(offer.pickup_charge || 0)).toFixed(2)}` : t('None specified')}</div>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>{t('Estimated Net Realization')}:</span>
            <div style={{ color: '#166534', fontWeight: 700 }}>
              {rupees(offer.estimated_net_realization)} / {t('quintal')}
              {offer.has_unknown_costs && <small style={{ display: 'block', fontWeight: 400, color: '#b45309' }}>*{t('Some costs unknown')}</small>}
            </div>
          </div>
        </div>
      </div>

      <div className="sale-row" style={{ marginTop: '1rem', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="button button-primary"
          onClick={onRequest}
          style={{ padding: '0.6rem 1.25rem', fontSize: '1rem' }}
        >
          {t('SEND SELLING REQUEST')}
        </button>
      </div>
    </article>
  );
}

function SellingRequestModal({
  offer,
  onClose,
  onSuccess,
}: {
  offer: PrivateRateOffer;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [availableHarvest, setAvailableHarvest] = useState<string>(offer.quantity_remaining);
  const [sellQuantity, setSellQuantity] = useState<string>(offer.minimum_quantity);
  const [expectedPrice, setExpectedPrice] = useState<string>(offer.offered_price);
  const [arrivalDate, setArrivalDate] = useState<string>(offer.arrival_dates[0] || '');
  const [message, setMessage] = useState<string>('');
  const [contactConsent, setContactConsent] = useState<boolean>(true);
  const [qualityConfirmed, setQualityConfirmed] = useState<boolean>(false);
  const [termsConfirmed, setTermsConfirmed] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [submittedRequest, setSubmittedRequest] = useState<PrivateRequest | null>(null);

  const numQty = Number(sellQuantity) || 0;
  const numPrice = Number(expectedPrice) || 0;
  const grossOutcome = numQty * numPrice;
  const knownDeductionsPerQuintal = Number(offer.unloading_charge || 0) + Number(offer.pickup_charge || 0);
  const totalKnownDeductions = numQty * knownDeductionsPerQuintal;
  const estimatedNetOutcome = grossOutcome - totalKnownDeductions;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!qualityConfirmed || !termsConfirmed) {
      setError(t('Please confirm both quality compliance and terms agreement.'));
      return;
    }
    if (numQty < Number(offer.minimum_quantity) || numQty > Number(offer.maximum_quantity)) {
      setError(t(`Quantity must be between ${offer.minimum_quantity} and ${offer.maximum_quantity} quintals.`));
      return;
    }
    if (numQty > Number(availableHarvest)) {
      setError(t('Requested selling quantity cannot exceed available harvest.'));
      return;
    }
    if (!arrivalDate) {
      setError(t('Please select a preferred arrival date.'));
      return;
    }

    setBusy(true);
    setError('');

    try {
      const key = crypto.randomUUID();
      // Format arrival datetime using the selected arrival date at noon IST
      const arrivalAtIso = `${arrivalDate}T12:00:00+05:30`;
      const payload = {
        offer_version: offer.version,
        available_quantity: availableHarvest,
        quantity: sellQuantity,
        expected_price: expectedPrice,
        variety: offer.variety,
        grade: offer.grade,
        arrival_at: arrivalAtIso,
        message: message.trim(),
        contact_consent: contactConsent,
        quality_confirmed: true,
        terms_confirmed: true,
      };

      const result = await purchaseAPI.submitFarmerRequest(offer.offer_id, payload, key);
      setSubmittedRequest(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setBusy(false);
    }
  }

  if (submittedRequest) {
    return (
      <div className="modal-backdrop" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
        <div className="sale-card" style={{ maxWidth: '550px', width: '100%', background: '#fff' }}>
          <h2>🎉 {t('Selling Request Submitted!')}</h2>
          <p>{t('Your request has been successfully delivered to')} <strong>{offer.business_name}</strong>.</p>
          <dl className="sale-ledger" style={{ margin: '1rem 0' }}>
            <div>
              <dt>{t('Request ID')}</dt>
              <dd><strong>{submittedRequest.public_id}</strong></dd>
            </div>
            <div>
              <dt>{t('Status')}</dt>
              <dd><span className="sale-status">{stateName(submittedRequest.status)}</span></dd>
            </div>
            <div>
              <dt>{t('Quantity & Expected Price')}</dt>
              <dd>{submittedRequest.quantity} {t('quintals')} · ₹{submittedRequest.expected_price} / {t('quintal')}</dd>
            </div>
            <div>
              <dt>{t('Preferred Arrival')}</dt>
              <dd>{formatDateTime(submittedRequest.arrival_at)}</dd>
            </div>
          </dl>
          <p className="sale-notice">
            {t('The business owner has been notified. You will see their response inside "My Sale Requests".')}
          </p>
          <div className="sale-row" style={{ marginTop: '1.5rem', justifyContent: 'space-between' }}>
            <Link to="/sale-requests" className="button button-primary">{t('Go to My Sale Requests')}</Link>
            <button type="button" className="button" onClick={onSuccess}>{t('Close')}</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem', overflowY: 'auto' }}>
      <div className="sale-card" style={{ maxWidth: '650px', width: '100%', background: '#fff', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="sale-row">
          <h3>{t('Send Selling Request')}</h3>
          <button type="button" className="text-button" onClick={onClose} style={{ fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
        </div>

        <p><strong>{offer.business_name}</strong> · {t(offer.business_type === 'PRIVATE_MANDI' ? 'Private Mandi' : 'Private Buyer')}</p>
        <p className="sale-notice" style={{ margin: '0.5rem 0 1rem 0' }}>
          {offer.commodity_name} ({offer.variety} / {offer.grade}) · {t('Offered')}: <strong>{rupees(offer.offered_price)}</strong> / {t('quintal')}
        </p>

        <form className="sale-grid" onSubmit={handleSubmit}>
          <label className="sale-field">
            {t('Total Harvest Available (quintals)')}
            <input
              type="number"
              step="0.001"
              min="0.001"
              required
              value={availableHarvest}
              onChange={e => setAvailableHarvest(e.target.value)}
            />
          </label>

          <label className="sale-field">
            {t('Quantity You Want to Sell (quintals)')}
            <input
              type="number"
              step="0.001"
              min={offer.minimum_quantity}
              max={offer.maximum_quantity}
              required
              value={sellQuantity}
              onChange={e => setSellQuantity(e.target.value)}
            />
            <small>{t('Allowed range')}: {offer.minimum_quantity} – {offer.maximum_quantity} {t('quintals')}</small>
          </label>

          <label className="sale-field">
            {t('Your Expected Price (₹/quintal)')}
            <input
              type="number"
              step="0.01"
              min="1"
              required
              value={expectedPrice}
              onChange={e => setExpectedPrice(e.target.value)}
            />
            <small>{t('Business published price')}: {rupees(offer.offered_price)}</small>
          </label>

          <label className="sale-field">
            {t('Preferred Arrival Date')}
            <select
              required
              value={arrivalDate}
              onChange={e => setArrivalDate(e.target.value)}
              aria-label={t('Preferred Arrival Date')}
            >
              <option value="" disabled>{t('Select an available date')}</option>
              {offer.arrival_dates.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </label>

          <label className="sale-field">
            {t('Farmer Notes / Arrival Instructions (Optional)')}
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              maxLength={1000}
              placeholder={t('e.g. Expected truck arrival by 10 AM, bagged in standard 50kg sacks.')}
            />
          </label>

          {/* Financial Preview */}
          <div className="sale-card" style={{ background: '#f1f5f9', border: '1px solid #cbd5e1' }}>
            <h4 style={{ margin: '0 0 0.5rem 0' }}>{t('Estimated Financial Outcome')}</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.9rem' }}>
              <div>{t('Gross Sale Value')}:</div>
              <div style={{ textAlign: 'right' }}><strong>₹{grossOutcome.toFixed(2)}</strong></div>
              <div>{t('Estimated Known Deductions')}:</div>
              <div style={{ textAlign: 'right', color: '#b45309' }}>-₹{totalKnownDeductions.toFixed(2)}</div>
              <div style={{ borderTop: '1px solid #cbd5e1', paddingTop: '0.4rem', fontWeight: 700 }}>{t('Net Outcome')}:</div>
              <div style={{ borderTop: '1px solid #cbd5e1', paddingTop: '0.4rem', textAlign: 'right', fontWeight: 700, color: '#166534' }}>
                ₹{estimatedNetOutcome.toFixed(2)}
              </div>
            </div>
            <small style={{ display: 'block', marginTop: '0.5rem', color: '#64748b' }}>
              *{t('Final weighment and payment settlement take place at delivery according to verified terms.')}
            </small>
          </div>

          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={contactConsent}
              onChange={e => setContactConsent(e.target.checked)}
            />
            <span>{t('Share my verified contact phone with this business when they review my request.')}</span>
          </label>

          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={qualityConfirmed}
              onChange={e => setQualityConfirmed(e.target.checked)}
              required
            />
            <span><strong>*</strong> {t('I confirm my produce matches the specified variety, grade, and quality standards.')}</span>
          </label>

          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={termsConfirmed}
              onChange={e => setTermsConfirmed(e.target.checked)}
              required
            />
            <span><strong>*</strong> {t('I understand and confirm the published purchasing terms, arrival conditions, and payment procedures.')}</span>
          </label>

          {error && <p role="alert" className="sale-error">{t(error)}</p>}

          <div className="sale-row" style={{ justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button type="button" className="button" onClick={onClose} disabled={busy}>{t('Cancel')}</button>
            <button type="submit" className="button button-primary" disabled={busy}>
              {busy ? t('Submitting...') : t('Confirm & Submit Request')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

