import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { setLanguage, t } from './i18n';
import { explainRecommendation, explainChanges } from './explanations';
import { validateAdvisor, exampleAdvisor, buildRecommendation, getEffectiveAdvisorValues, blankAdvisor } from './advisor';
import { CROP_SCOPES, defaultScope, type Recommendation } from './api';
import { ReadAloud } from './Speech';
import recommendationFixture from './test/fixtures/recommendation.json';
import infeasibleFixture from './test/fixtures/infeasible.json';
import conditionalFixture from './test/fixtures/conditional-hold.json';

const recommendation = recommendationFixture as Recommendation;
const conditional = conditionalFixture as Recommendation;
let research = false;
let historical = false;
let staleReference = false;
let multiCrop = false;
let dailyHorizons = false;
let forecastRequests: Record<string, unknown>[] = [];
let offline = false, rows: unknown[] = [], model = false, submitted: unknown[] = [], nextResult: Recommendation = recommendation;
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const mockFetch = vi.fn(async (input: RequestInfo | URL) => {
  if (offline) throw new TypeError('offline');
  const request = input as Request;
  const rawUrl = typeof input === 'string' ? input : (input && 'url' in input) ? (input as Request).url : String(input);
  const path = (rawUrl.startsWith('http') ? new URL(rawUrl).pathname : rawUrl).replace(/^\/backend/, '');
  if (path === '/api/health') return json({ status: 'ok', service: 'samay', version: '0.1.0' });
  if (path === '/api/v1/markets') return json([]);
  if (path === '/api/v1/commodities') return json([]);
  if (path === '/api/v1/models/horizons') return json({ ...defaultScope, planning_ceiling_calendar_days: 365, saved_horizons:dailyHorizons ? [1,3,7,14,30,60] : [], requested_status:'saved_artifact',reasons:[],sample_counts:{} });
  if (path === '/api/v1/context') return json({ status: 'unavailable', market: defaultScope.market, commodity: defaultScope.commodity, decision_at: '2026-11-05T12:00:00Z', weather: [], events: [], news: [], sources: [], warnings: [], numeric_price_adjustment_applied: false, note: 'TEST_ONLY' });
  if (path === '/api/v1/data/status') return json({ status: 'unavailable', official_observations: 0, fixture_observations: 3, demo_observations: 0, latest_official_report_date: null, latest_official_fetched_at: null, note: 'TEST_ONLY' });
  if (path === '/api/v1/models/status' && multiCrop) return json({ status: 'no_models_deployed', models: [], research_studies: [], research_models: Object.values(CROP_SCOPES).map(scope => ({ ...scope, horizon: 3, model_version: 'TEST_ONLY_CURRENT', status: 'research_only_limited_evidence' })) });
  if (path === '/api/v1/predict' && multiCrop) {
    const body = await request.clone().json() as Record<string, unknown>;
    forecastRequests.push(body);
    return json({ ...body, request_id: 'TEST_ONLY_CURRENT', horizon_calendar_days: body.horizon, timestamp: '2026-11-05T12:00:00+05:30', target_date: '2026-11-08', latest_report_date: '2026-11-03', reliability_status: 'limited evidence', prediction_inr_per_quintal: '1000.00', model_version: 'TEST_ONLY_CURRENT', intervals: [], flags: ['short_history_baseline_only'], data_source: { source: 'TEST_ONLY' } });
  }
  if (path === '/api/v1/models/status') return json({ status: model ? 'configured' : 'no_models_deployed', research_studies: research ? [{ ...defaultScope, version: 'TEST_ONLY_RESEARCH', research_only: true, train_start: '2021-01-01', train_end: '2023-12-31', validation_end: '2024-12-31', test_end: '2025-06-30', limitations: 'TEST_ONLY', source_fingerprint: 'TEST_ONLY', horizons: [{ horizon: 1, selected_model: 'naive', train_n: 120, validation_n: 30, final_n: 2, final_metrics: { mae_inr_per_quintal: 10, wape_pct: 1 }, naive_metrics: { mae_inr_per_quintal: 10 } }] }] : [], models: model ? [{ ...defaultScope, horizon: 3, model_version: 'TEST_ONLY', status: 'artifact_present', reliability_evidence_configured: false }] : [] });
  if (path === '/api/v1/models/evaluation') {
    if (!historical) return json({ error: { code: 'no_research_evaluation', message: 'TEST_ONLY no report', request_id: 'TEST_ONLY' } },404);
    const points = Array.from({ length: 31 }, (_,i) => ({ origin_date: `2025-01-${String(i+1).padStart(2,'0')}`, target_date: new Date(Date.UTC(2025,0,i+4)).toISOString().slice(0,10), actual_inr_per_quintal: String(1000+i*10), prediction_inr_per_quintal: String(1010+i*10), absolute_error_inr_per_quintal: '10' }));
    return json({ research_only: true, source_kind: 'secondary', scope: defaultScope, horizon: 3, selected_model: 'TEST_ONLY_NAIVE', model_version: 'TEST_ONLY', status: 'evaluated', final_n: points.length, metrics: { mae_inr_per_quintal: 10, wape_pct: 100*310/points.reduce((n,p) => n+Number(p.actual_inr_per_quintal),0) }, naive_metrics: { mae_inr_per_quintal: 10 }, train_end: '2023-12-31', validation_end: '2024-12-31', test_start: '2025-01-01', test_end: '2025-02-03', source: [], limitations: 'TEST_ONLY', points, price_unit: 'INR/quintal', rounding_note: 'TEST_ONLY' });
  }
  if (path === '/api/v1/prices/history') return json({ items: rows, limit: 1000, offset: 0, next_offset: null });
  if (path === '/api/v1/prices/latest' && staleReference) return json({ observation: { ...defaultScope, modal_price_inr_per_quintal: '99999', report_date: '2021-01-01' }, stale: true, age_calendar_days: 2000 });
  if (path === '/api/v1/prices/latest') return json({ error: { code: 'no_official_observation', message: 'No official observation', request_id: 'TEST_ONLY' } }, 404);
  if (path === '/api/v1/predict') return model ? json({ ...defaultScope, request_id: 'TEST_ONLY_PREDICTION', horizon_calendar_days: 3, timestamp: '2026-11-04T00:00:00+05:30', target_date: '2026-11-07', latest_report_date: '2026-11-03', reliability_status: 'limited evidence', prediction_inr_per_quintal: '1000.00', model_version: 'TEST_ONLY', intervals: [{ nominal_level: '.9', lower_inr_per_quintal: '900', upper_inr_per_quintal: '1100' }], flags: ['limited_unseen_interval_evidence'], data_source: { source: 'TEST_ONLY' } }) : json({ error: { code: 'missing_model', message: 'No saved model', request_id: 'TEST_ONLY' } }, 503);
  if (path === '/api/v1/recommend') { submitted.push(await request.clone().json()); return json(nextResult, nextResult.optimization.recommended_plan ? 200 : 409); }
  throw new Error(`Unexpected test request ${path}`);
});
const show = (path = '/') => render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>);
beforeEach(() => { setLanguage('en'); research = false; historical = false; staleReference = false; multiCrop = false; dailyHorizons = false; forecastRequests = []; offline = false; rows = []; model = false; submitted = []; nextResult = recommendation; vi.stubGlobal('fetch', mockFetch); mockFetch.mockClear(); });
afterEach(() => { vi.unstubAllGlobals(); setLanguage('en'); });

describe('SAMAY farmer dashboard and Kannada journey', () => {
  it('shows the conditional hold decision separately from the safe fallback in both languages', async () => {
    const held = conditional.optimization.recommended_plan!;
    nextResult = { ...recommendation, decision_support: {
      action: 'partial_sell_and_hold', basis: 'conditional_scenario_analysis', conditional: true,
      plan: { ...held, recommendation_eligible: false }, safe_fallback_plan: recommendation.optimization.recommended_plan,
      reasons: ['mandatory_cash_and_storage_constraints_satisfied'], horizon_comparisons: [held],
      context: { status: 'unavailable', market: defaultScope.market, commodity: defaultScope.commodity, decision_at: '2026-11-05T12:00:00Z', weather: [], events: [], news: [], sources: [], warnings: [], numeric_price_adjustment_applied: false, note: 'TEST_ONLY' }, note: 'TEST_ONLY conditional analysis',
    } };
    show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Load labeled example' }));
    fireEvent.click(screen.getByRole('button', { name: 'Calculate my sale plan' }));
    expect(await screen.findByRole('heading', { name: 'Sell some now; conditionally hold the rest' })).toBeInTheDocument();
    expect(screen.getAllByText('Conditional analysis, not validated advice')[0]).toBeInTheDocument();
    expect(screen.getByText('Full calculation audit for the displayed plan')).toBeInTheDocument();
    const expectedCash = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(held.cash_today_inr));
    expect(screen.getAllByText(expectedCash).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByRole('heading', { name: 'ಈಗ ಸ್ವಲ್ಪ ಮಾರಿ; ಉಳಿದುದನ್ನು ಷರತ್ತುಗಳಿಗೆ ಒಳಪಟ್ಟು ಇಡಿ' })).toBeInTheDocument();
    expect(screen.getAllByText(expectedCash).length).toBeGreaterThan(0);
  });
  it('builds short-date comparisons and an explicit long buyer-price scenario without changing values by language', () => {
    const scope = CROP_SCOPES.Arecanut;
    const draft = { ...exampleAdvisor, capacity: '10', days: '90', limit: '180', scenarioPrice: '60000', loss: '0.01' };
    const english = buildRecommendation(draft,scope,'2026-11-04');
    expect(english.holding_options.map(o => o.days)).toEqual([1,3,7,90]);
    expect(english.holding_options.find(o => o.days === 90)?.scenario_price_inr_per_quintal).toBe('60000');
    expect(english.holding_options.find(o => o.days === 3)?.scenario_price_inr_per_quintal).toBeUndefined();
    expect(english.decision_policy?.adverse_fraction).toBe('0.200000');
    setLanguage('kn');
    expect(buildRecommendation(draft,scope,'2026-11-04')).toEqual(english);
  });
  it('requires an honest price basis for longer holding dates', () => {
    const draft = { ...exampleAdvisor, capacity: '10', days: '90', limit: '180', scenarioPrice: '' };
    expect(validateAdvisor({...draft,longReference:'require_user_price'},'Arecanut').scenarioPrice).toMatch(/future buyer quote/);
    expect(validateAdvisor({...draft,longReference:'saved_forecast'},'Arecanut').scenarioPrice).toBeUndefined();
    expect(validateAdvisor({ ...draft, longReference: 'flat_reference' },'Arecanut').scenarioPrice).toBeUndefined();
  });
  it('requests the saved current variety and grade for every additional crop', async () => {
    multiCrop = true; show('/forecast');
    await screen.findAllByText('Research only · limited evidence');
    for (const crop of ['Copra', 'Arecanut', 'Onion', 'Potato']) {
      const scope = CROP_SCOPES[crop];
      fireEvent.click(screen.getByRole('button', { name: new RegExp(`${crop} ·`) }));
      fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
      await screen.findAllByText('₹1,000.00');
      expect(forecastRequests.at(-1)).toMatchObject({ market: scope.market, commodity: crop, variety: scope.variety, grade: scope.grade, horizon: 3 });
      expect(screen.getByText('No sufficiently calibrated interval is available.')).toBeInTheDocument();
    }
    expect(forecastRequests).toHaveLength(4);
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByText('ಹಳೆಯ ದಾಖಲೆಗಳು ಮೂಲಭೂತ ಮುನ್ಸೂಚನೆಗೆ ಮಾತ್ರ ಸಾಕಾಗಿವೆ; ಮುಂದುವರಿದ ಮಾದರಿಯ ತರಬೇತಿಗೆ ಸಾಕಾಗುವುದಿಲ್ಲ.')).toBeInTheDocument();
  });
  it('shows truthful empty/connected states and switches all core headings', async () => {
    show();
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
    expect(await screen.findByText('A clearer picture starts with verified data')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /observations/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByRole('heading', { name: 'ತಿಳಿದು ತೀರ್ಮಾನಿಸಿ.' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('kn');
    expect(screen.getByText('ಮುಂದಿನ ಬೆಲೆಗಳು ಅನಿಶ್ಚಿತ. ಅಂತಿಮ ತೀರ್ಮಾನ ನಿಮ್ಮದೇ.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('heading', { name: 'A better day to decide.' })).toBeInTheDocument();
  });
  it('shows explicit disconnected state without successful data or plans', async () => {
    offline = true; show();
    expect(await screen.findByText(/Backend disconnected/)).toBeInTheDocument();
    expect(screen.queryByText('₹18,700.00')).not.toBeInTheDocument();
    offline = false;
    fireEvent.click(screen.getAllByRole('button', { name: /Try again/ })[0]);
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
  });
  it('renders dated observations with provenance and an accessible chart', async () => {
    rows = [{ id: 1, market_id: 1, commodity_id: 1, ...defaultScope, report_date: '2026-11-01', min_price_inr_per_quintal: '900', modal_price_inr_per_quintal: '1000', max_price_inr_per_quintal: '1100', arrivals_quintals: null, price_unit: 'INR/quintal', source: 'TEST_ONLY_SOURCE', source_url: null, fetched_at: '2026-11-01T18:00:00Z', data_kind: 'official' }];
    show('/insights');
    expect(await screen.findByText('TEST_ONLY_SOURCE')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /1 observations/ })).toBeInTheDocument();
    expect(screen.getByText(/not prediction intervals/)).toBeInTheDocument();
  });
  it('does not present unavailable horizons as operational and preserves forecast warnings/history', async () => {
    model = true; show('/forecast');
    await screen.findByText('Saved artifact available');
    expect(screen.getByRole('button', { name: /1 day.*Not deployed/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
    expect((await screen.findAllByText('₹1,000.00')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('limited evidence').length).toBeGreaterThan(0);
    expect(screen.getByText(/90% nominal empirical band/)).toBeInTheDocument();
    expect(screen.getByText(/Model TEST_ONLY/)).toBeInTheDocument();
  });
  it('validates the manual farmer workflow and translates hints without losing values', async () => {
    show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getAllByText('Enter a value greater than zero.').length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText(/Harvest quantity/), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText(/Expected buyer price today/), { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByLabelText(/ಕೊಯ್ಲು ಮಾಡಿದ ಪ್ರಮಾಣ/)).toHaveValue('20');
    expect(screen.getByLabelText(/ಇಂದು ಖರೀದಿದಾರರಿಂದ ನಿರೀಕ್ಷಿಸುವ ಬೆಲೆ/)).toHaveValue('1000');
    expect(submitted).toHaveLength(0);
  });
  it('requires a manual buyer quote and acknowledgment when no observation is available', async () => {
    show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.change(screen.getByLabelText(/Harvest quantity/), { target: { value: '30' } });
    fireEvent.change(screen.getByLabelText(/Expected buyer price today/), { target: { value: '1400' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.change(screen.getByLabelText(/Immediate net cash needed/), { target: { value: '10000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('checkbox', { name: /I understand these are my inputs/ }));
    const calcBtn = screen.getByRole('button', { name: 'Calculate my sale plan' });
    expect(calcBtn).not.toBeDisabled();
    fireEvent.click(calcBtn);
    expect(await screen.findByRole('heading', { name: 'Keep today’s cash needs covered.' })).toBeInTheDocument();
    expect(submitted).toHaveLength(1);
    const sub = submitted[0] as Record<string, unknown>;
    expect(sub.total_quantity_quintals).toBe('30');
    expect(sub.today_price_inr_per_quintal).toBe('1400');
  });
  it('calculates through the API, switches languages without recalculation and exposes exact numbers', async () => {
    show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Load labeled example' }));
    fireEvent.click(screen.getByRole('button', { name: 'Calculate my sale plan' }));
    expect(await screen.findByRole('heading', { name: 'Keep today’s cash needs covered.' })).toBeInTheDocument();
    expect(submitted).toHaveLength(1);
    expect(JSON.stringify(submitted[0])).not.toContain('reliability_status');
    expect(screen.getAllByText('₹18,700.00').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Why this recommendation?'));
    expect(screen.getByText(/₹20000.00.*₹1000.00.*₹300.00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByText('ಈ ಯೋಜನೆ ಏಕೆ?')).toBeInTheDocument();
    expect(screen.getAllByText('₹18,700.00').length).toBeGreaterThan(0);
    expect(submitted).toHaveLength(1);
  });
  it('keeps backend infeasibility as an explained outcome rather than an HTTP success plan', async () => {
    nextResult = infeasibleFixture as Recommendation; show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Load labeled example' }));
    fireEvent.click(screen.getByRole('button', { name: 'Calculate my sale plan' }));
    expect(await screen.findByRole('heading', { name: 'These constraints need another look.' })).toBeInTheDocument();
    expect(screen.getByText('Infeasible')).toBeInTheDocument();
  });
  it('updates conservative, central and adverse previews using backend amounts only', async () => {
    nextResult = conditional; show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Load labeled example' }));
    fireEvent.click(screen.getByRole('button', { name: 'Calculate my sale plan' }));
    await screen.findByRole('heading', { name: 'A balanced view of selling and holding.' });
    const initialCount = submitted.length;
    fireEvent.click(screen.getByRole('button', { name: 'Adverse scenario' }));
    expect(screen.getByRole('button', { name: 'Adverse scenario' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Conservative scenario' }));
    expect(screen.getByRole('button', { name: 'Conservative scenario' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Scenario preview only. The backend-selected plan does not change unless you recalculate.')).toBeInTheDocument();
    expect(submitted).toHaveLength(initialCount);
  });
  it('offers manual text when Kannada speech is not supported', () => {
    setLanguage('kn'); render(<ReadAloud lines={['ಪರೀಕ್ಷೆಯ ವಿವರಣೆ ₹18700.00']}/>);
    expect(screen.getByRole('button', { name: 'ವಿವರಣೆಯನ್ನು ಧ್ವನಿಯಲ್ಲಿ ಓದಿ' })).toBeDisabled();
    expect(screen.getByText(/ಪೂರ್ಣ ಪಠ್ಯ ಕೆಳಗೆ ಲಭ್ಯವಿದೆ/)).toBeInTheDocument();
  });
  it('displays research errors with limitations and preserves values in Kannada', async () => {
    research = true; show('/transparency');
    expect(await screen.findByRole('heading', { name: 'Retrospective research results' })).toBeInTheDocument();
    expect(screen.getByText('Research only · not deployed')).toBeInTheDocument();
    expect(screen.getAllByText('₹10.00')).toHaveLength(2);
    expect(screen.getByText(/original revision history is unverified/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getByRole('heading', { name: 'ಹಿಂದಿನ ದಾಖಲೆಗಳ ಆಧಾರದ ಸಂಶೋಧನಾ ಫಲಿತಾಂಶಗಳು' })).toBeInTheDocument();
    expect(screen.getAllByText('₹10.00')).toHaveLength(2);
  });
  it('handles unknown routes', () => { show('/missing'); expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument(); });
  it('selects the actual Arecanut scope, requires a manual quote when disconnected and retains long planning dates', async () => {
    show('/advisor');
    const arecaBtn = screen.getByRole('button', { name: /Arecanut/i });
    expect(arecaBtn).toBeInTheDocument();
    fireEvent.click(arecaBtn);
    expect(screen.getAllByText(/Shivamogga Mandi/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/48,000/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/rashi.*local/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getAllByText(/Shivamogga Mandi/i).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText(/Expected buyer price today/), { target: { value: '48000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByText(/No verified storage facility or tariff is configured/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Yes (Can hold)' }));
    expect(screen.getByRole('option', { name: /730 calendar days/ })).toBeInTheDocument();
  });
});

describe('stale historical quotes', () => {
  it('shows the dated reference but requires a current manually entered buyer quote', async () => {
    staleReference = true; show('/advisor');
    expect(await screen.findByText(/Historical price only/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.change(screen.getByLabelText(/Harvest quantity/), { target: { value: '20' } });
    expect(screen.getByLabelText(/Expected buyer price today/)).toHaveValue('');
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(submitted).toHaveLength(0);
  });
});

describe('frozen historical evaluation', () => {
  it('shows dated actual predictions, provenance and identical amounts after language switching', async () => {
    historical = true; show('/forecast');
    expect(await screen.findByText(/TEST_ONLY_NAIVE/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Historical observed and frozen/ })).toBeInTheDocument();
    expect(screen.getByText('Secondary mirror: India Data Portal')).toBeInTheDocument();
    expect(screen.getAllByText('₹10.00').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getAllByText('₹10.00').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'ಹಿಂದಿನ ಪರೀಕ್ಷೆ: ನಿಜವಾದ ಮತ್ತು ಮುನ್ಸೂಚಿತ ಬೆಲೆಗಳು' })).toBeInTheDocument();
  });
});

describe('deterministic explanation and request construction', () => {
  it('compares every supported date within the verified storage limit', () => {
    const input=buildRecommendation({...exampleAdvisor,capacity:'10',days:'30',limit:'30',loss:'0.01'},CROP_SCOPES.Copra,undefined,[1,2,3,4,5,6,7,14,21,30,60]);
    expect(input.holding_options.map(o=>o.days)).toEqual([1,2,3,4,5,6,7,14,21,30]);
    expect(input.holding_options.every(o=>!o.scenario_price_inr_per_quintal)).toBe(true);
  });
  it('requests an exact saved monthly horizon and preserves the forecast value in Kannada', async () => {
    dailyHorizons=true; multiCrop=true; show('/forecast');
    fireEvent.click(screen.getByRole('button',{name:/Copra ·/}));
    const exact=screen.getByLabelText('Exact forecast horizon (calendar days)');
    fireEvent.change(exact,{target:{value:'30'}});
    const button=await screen.findByRole('button',{name:'Get forecast'});
    fireEvent.click(button);
    await screen.findAllByText('₹1,000.00');
    expect(forecastRequests.at(-1)).toMatchObject({commodity:'Copra',horizon:30});
    fireEvent.click(screen.getByRole('button',{name:'ಕನ್ನಡ'}));
    expect(screen.getAllByText('₹1,000.00').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('ಮುನ್ಸೂಚನೆಯ ನಿಖರ ಅವಧಿ (ಕ್ಯಾಲೆಂಡರ್ ದಿನಗಳು)')).toHaveValue(30);
  });
  it('preserves zero loss assumptions and never inserts a missing buyer quote', () => {
    expect(getEffectiveAdvisorValues({ ...exampleAdvisor, loss: '0' }).loss).toBe('0');
    expect(getEffectiveAdvisorValues(blankAdvisor).price).toBe('');
    expect(validateAdvisor({ ...exampleAdvisor, price: '' }).price).toBeTruthy();
  });

  it('keeps every currency amount identical in both languages', () => {
    const english = explainRecommendation(conditional, 'en').join(' '), kannada = explainRecommendation(conditional, 'kn').join(' ');
    expect(english.match(/₹[-\d.]+/g)).toEqual(kannada.match(/₹[-\d.]+/g));
    expect(explainRecommendation(conditional, 'kn')).toEqual(explainRecommendation(conditional, 'kn'));
    expect(kannada).toContain('ಅಂತಿಮ ತೀರ್ಮಾನ ನಿಮ್ಮದೇ');
  });
  it('explains changes from validated response fields without inventing an improved return', () => {
    const changed = structuredClone(recommendation);
    changed.optimization.request_and_assumptions.required_net_cash_inr = '11000';
    expect(explainChanges(recommendation, changed, 'en').join(' ')).toContain('10000 to 11000');
    expect(explainChanges(recommendation, changed, 'kn').join(' ')).toContain('11000');
    expect(explainChanges(recommendation, changed, 'en').join(' ')).not.toContain('profit');
  });
  it('does not send any client-declared future model or confidence', () => {
    expect(validateAdvisor(exampleAdvisor)).toEqual({});
    const input = buildRecommendation(exampleAdvisor, defaultScope);
    expect(input.today_sale_costs.commission_rate).toBe('0.050000');
    expect(input.holding_options).toEqual([]);
    expect(validateAdvisor({ ...exampleAdvisor, price: '-1' }).price).toBeTruthy();
    expect(t('Tomato', {}, 'kn')).toBe('ಟೊಮೇಟೊ');
  });
});
