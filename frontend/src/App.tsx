import { Component, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { ArrowRight, BarChart3, ChevronDown, ClipboardCheck, LayoutDashboard, Leaf, Menu, Play, RefreshCw, ShieldCheck, SlidersHorizontal, Sprout, TrendingUp, Wifi, WifiOff } from 'lucide-react';
import { AppProvider, useApp } from './state';
import { Dashboard, Forecast, Insights, Transparency } from './MarketPages';
import { AdvisorPage } from './AdvisorPage';
import { Results } from './Results';
import { ErrorState } from './ui';
import { localize, setLanguage, t } from './i18n';
import { Demo } from './Demo';

interface NavItem {
  to: string;
  title: string;
  farmerTitle?: string;
  icon: typeof LayoutDashboard;
  farmer: boolean;
}

const allNavigation: NavItem[] = [
  { to: '/', title: 'Dashboard', farmer: true, icon: LayoutDashboard },
  { to: '/advisor', title: 'Selling Advisor', farmerTitle: 'Plan My Sale', farmer: true, icon: Sprout },
  { to: '/results', title: 'Recommendation Results', farmerTitle: 'Sale Results', farmer: true, icon: ClipboardCheck },
  { to: '/insights', title: 'Market Insights', farmer: true, icon: BarChart3 },
  { to: '/forecast', title: 'Price Forecast', farmer: false, icon: TrendingUp },
  { to: '/explorer', title: 'Scenario Explorer', farmer: false, icon: SlidersHorizontal },
  { to: '/transparency', title: 'Data & Model Transparency', farmer: false, icon: ShieldCheck },
];

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? localize(
      <div className="error-state" role="alert">
        <h1>This view could not be loaded.</h1>
        <p>The response was unexpected. No result has been substituted.</p>
        <button className="button" onClick={() => window.location.reload()}>Reload app</button>
      </div>
    ) : this.props.children;
  }
}

function Shell() {
  const { language, mode, setMode, scope, setScope, connection, catalog } = useApp();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [series, setSeries] = useState(scope);
  const [demo, setDemo] = useState(false);
  const location = useLocation();
  const main = useRef<HTMLElement>(null);

  const visibleNav = allNavigation.filter(item => mode === 'judge' || item.farmer);
  const activeNav = allNavigation.find(n => n.to === location.pathname);

  useEffect(() => {
    document.documentElement.lang = language;
    document.title = `${t(activeNav?.title || 'SAMAY')} · SAMAY`;
  }, [language, location.pathname, activeNav]);

  useEffect(() => {
    setMobileOpen(false);
    main.current?.focus({ preventScroll: true });
    window.scrollTo?.(0, 0);
  }, [location.pathname]);

  const connected = !connection.error && connection.data?.status === 'ok';

  return localize(
    <div className={`app-shell mode-${mode}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      {mobileOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <Link className="brand" to="/">
          <span className="brand-mark"><Sprout size={25} /></span>
          <span>SAMAY<small>THE RIGHT TIME TO DECIDE</small></span>
        </Link>
        <div className="workspace-label">
          {mode === 'farmer' ? t('FARMER WORKSPACE') : t('JUDGE & AUDIT WORKSPACE')}
        </div>
        <nav aria-label="Main navigation">
          {visibleNav.map(({ to, title, farmerTitle, icon: Icon }) => (
            <NavLink end={to === '/'} key={to} to={to}>
              <Icon size={19} />
              <span>{t(mode === 'farmer' && farmerTitle ? farmerTitle : title)}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <Leaf size={22} />
            <strong>A little clarity goes a long way.</strong>
            <p>Start with your cash needs. Keep the uncertainty visible.</p>
            <button onClick={() => { setDemo(true); setMobileOpen(false); }} className="text-button">
              Take the guided tour<ArrowRight size={14} />
            </button>
          </div>
          <p>TEAM RESONANCE<span>COLOSSUS 3.0 · Decision support</span></p>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-location">
            <button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(!mobileOpen)}>
              <Menu size={23} />
            </button>
            <span className="breadcrumb">
              Your workspace<span>/</span>
              <strong>{t(mode === 'farmer' && activeNav?.farmerTitle ? activeNav.farmerTitle : activeNav?.title || 'Page')}</strong>
            </span>
          </div>

          <div className="topbar-actions">
            <div className="mode-switch" role="group" aria-label="Experience mode">
              <button
                type="button"
                aria-pressed={mode === 'farmer'}
                onClick={() => setMode('farmer')}
                title="Simplified, low-friction mobile experience for farmers"
              >
                <Sprout size={13} />
                <span>{t('Farmer Mode')}</span>
              </button>
              <button
                type="button"
                aria-pressed={mode === 'judge'}
                onClick={() => setMode('judge')}
                title="Full transparency: data provenance, retrospective evaluations, model metrics, optimizer ledger"
              >
                <ShieldCheck size={13} />
                <span>{t('Judge Mode')}</span>
              </button>
            </div>

            <span className={`connection-pill ${connection.error ? 'is-offline' : ''}`} role="status">
              {connection.loading ? <RefreshCw size={14} className="spin" /> : connected ? <Wifi size={14} /> : <WifiOff size={14} />}
              <span>{connection.loading ? 'Connecting' : connected ? 'Backend connected' : 'Disconnected'}</span>
            </span>

            <button className="button button-secondary demo-start" onClick={() => setDemo(true)}>
              <Play size={14} />90-sec demo
            </button>

            <div className="language-switch" role="group" aria-label="Language">
              <button lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button>
              <button lang="kn" aria-pressed={language === 'kn'} onClick={() => setLanguage('kn')}>ಕನ್ನಡ</button>
            </div>
          </div>
        </header>

        <main id="main-content" tabIndex={-1} ref={main}>
          <div className="scope-bar">
            <div>
              <span className="scope-dot" />
              <strong>{scope.market}</strong>
              <span className="scope-divider">/</span>
              {scope.commodity}
              <span className="scope-detail">· {scope.variety} / {scope.grade} ({t('Pilot scope: Karnataka')})</span>
            </div>
            {mode === 'judge' && (
              <button className="text-button" aria-expanded={scopeOpen} onClick={() => { setSeries(scope); setScopeOpen(!scopeOpen); }}>
                Change series<ChevronDown size={15} />
              </button>
            )}
          </div>

          {scopeOpen && mode === 'judge' && (
            <form className="scope-editor card" onSubmit={e => { e.preventDefault(); setScope({ ...series, variety: series.variety.trim().toLowerCase(), grade: series.grade.trim().toLowerCase() }); setScopeOpen(false); }}>
              <label>Market
                <select value={series.market} onChange={e => setSeries({ ...series, market: e.target.value })}>
                  <option value="Kolar APMC">Kolar APMC · configured scope</option>
                </select>
              </label>
              <label>Commodity
                <select value={series.commodity} onChange={e => setSeries({ ...series, commodity: e.target.value })}>
                  <option value="Tomato">Tomato · configured scope</option>
                </select>
              </label>
              <label>Variety<input value={series.variety} required maxLength={120} onChange={e => setSeries({ ...series, variety: e.target.value })} /></label>
              <label>Grade<input value={series.grade} required maxLength={120} onChange={e => setSeries({ ...series, grade: e.target.value })} /></label>
              <button className="button button-primary" type="submit">Apply series</button>
              <p className="small muted">Only Kolar APMC / Tomato is supported. A configured series does not imply imported data or an operational forecast.</p>
            </form>
          )}

          {connection.error ? (
            <div className="disconnect-banner">
              <strong>Backend disconnected. Prices, forecasts and plans cannot be refreshed.</strong>
              <ErrorState error={connection.error} retry={() => { connection.retry(); catalog.retry(); }} />
            </div>
          ) : null}
          {Boolean(catalog.error) && !connection.error && <ErrorState error={catalog.error} retry={catalog.retry} />}

          <p className="global-disclaimer" role="status" hidden={!catalog.data?.data.historical_demo_date}>
            {t('HISTORICAL REPLAY — not live market data')} · {catalog.data?.data.historical_demo_date}
          </p>
          <p className="global-disclaimer" role="note">Future prices are uncertain. You make the final decision.</p>

          <Boundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/forecast" element={<Forecast />} />
              <Route path="/advisor" element={<AdvisorPage />} />
              <Route path="/results" element={<Results />} />
              <Route path="/explorer" element={<AdvisorPage explorer />} />
              <Route path="/transparency" element={<Transparency />} />
              <Route path="*" element={<><h1>{t('Page not found')}</h1><Link to="/">{t('Return to dashboard')}</Link></>} />
            </Routes>
          </Boundary>

          <footer className="footer">
            <span><ShieldCheck size={14} />Decision support, with the uncertainty left in.</span>
            <span>INR · Quintals · India Standard Time</span>
          </footer>
        </main>
      </div>
      {demo && <Demo close={() => setDemo(false)} />}
    </div>
  );
}

export function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
