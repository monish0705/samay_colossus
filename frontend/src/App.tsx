import { Component, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { BarChart3, ClipboardCheck, LayoutDashboard, Menu, RefreshCw, ShieldCheck, SlidersHorizontal, Sprout, TrendingUp, Wifi, WifiOff } from 'lucide-react';
import { AppProvider, useApp } from './state';
import { Dashboard, Forecast, Insights, Transparency } from './MarketPages';
import { AdvisorPage } from './AdvisorPage';
import { Results } from './Results';
import { ErrorState } from './ui';
import { localize, setLanguage, t } from './i18n';
import { SaleWorkspace } from './SalePages';
import { BusinessPage } from './BusinessPages';
import { PrivateRatesPage } from './PrivateRatesPage';
import { BusinessWorkspaceProvider, RoleSwitcher, useBusinessWorkspace } from './business-context';

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
  { to: '/sale-requests', title: 'My Sale Requests', farmer: true, icon: ClipboardCheck },
  { to: '/private-rates', title: 'Private Mandi Rates', farmer: true, icon: TrendingUp },
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
  const { language, scope, connection, catalog } = useApp();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { access, switchTo } = useBusinessWorkspace();
  const privateView = location.pathname.startsWith('/business');
  const businessMode = access?.active_workspace.mode === 'BUSINESS' || privateView;
  const main = useRef<HTMLElement>(null);

  const visibleNav = allNavigation;
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

  const currentW = access?.workspaces.find(w => w.business_id === access.active_workspace.business_id && w.role === access.active_workspace.role) || access?.workspaces[0];
  const isApmc = currentW?.business_type === 'APMC_MANDI' || location.pathname.startsWith('/business/apmc');
  const businessBase = currentW ? (
    currentW.business_type === 'APMC_MANDI' ? `/business/apmc/${currentW.business_id}` :
    currentW.business_type === 'PRIVATE_MANDI' ? `/business/mandi/${currentW.business_id}` :
    `/business/buyer/${currentW.business_id}`
  ) : '/business';

  const businessNav = isApmc ? [
    { to: businessBase, title: 'APMC Dashboard', icon: LayoutDashboard },
    { to: `${businessBase}/incoming`, title: 'Incoming Requests', icon: ClipboardCheck },
    { to: `${businessBase}/counteroffers`, title: 'Counteroffers', icon: TrendingUp },
    { to: `${businessBase}/arrivals`, title: 'Arrival Schedule', icon: BarChart3 },
    { to: `${businessBase}/arrived`, title: 'Arrived Produce', icon: ShieldCheck },
    { to: `${businessBase}/completed`, title: 'Completed Sales', icon: ShieldCheck },
    { to: `${businessBase}/settings`, title: 'Mandi Settings', icon: SlidersHorizontal },
  ] : [
    { to: businessBase, title: currentW?.business_type === 'PRIVATE_BUYER' ? 'Buyer Dashboard' : 'Business Dashboard', icon: LayoutDashboard },
    { to: `${businessBase}?tab=offers`, title: 'My Buying Offers', icon: TrendingUp },
    { to: `${businessBase}?tab=create`, title: 'Create Buying Offer', icon: Sprout },
    { to: `${businessBase}?tab=incoming`, title: 'Incoming Farmer Requests', icon: ClipboardCheck },
    { to: `${businessBase}?tab=confirmed`, title: 'Confirmed Requests', icon: ClipboardCheck },
    { to: `${businessBase}?tab=appointments`, title: 'Appointments', icon: BarChart3 },
    { to: `${businessBase}?tab=completed`, title: 'Completed Purchases', icon: ShieldCheck },
    { to: `${businessBase}?tab=settings`, title: 'Settings', icon: SlidersHorizontal },
  ];

  return localize(
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      {mobileOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <Link className="brand" to="/">
          <span className="brand-mark"><Sprout size={25} /></span>
          <span>SAMAY<small>THE RIGHT TIME TO DECIDE</small></span>
        </Link>
        <div className="workspace-label">
          {t(businessMode ? 'BUSINESS WORKSPACE' : 'FARMER WORKSPACE')}
        </div>
        {businessMode && access && access.workspaces && access.workspaces.length > 0 && (
          <div style={{ padding: '0.25rem 0.6rem 0.6rem 0.6rem', borderBottom: '1px solid rgba(255,255,255,0.12)', marginBottom: '0.5rem' }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'rgba(255,255,255,0.6)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
              {t('Select Business Persona')}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {access.workspaces.map(w => {
                const isActive = (isApmc && w.business_type === 'APMC_MANDI') || (!isApmc && currentW?.business_id === w.business_id && currentW?.role === w.role);
                const icon = w.business_type === 'APMC_MANDI' ? '🏛️' : w.business_type === 'PRIVATE_MANDI' ? '🏬' : '💼';
                const label = w.business_type === 'APMC_MANDI' ? `APMC Mandi · ${w.name}` : w.business_type === 'PRIVATE_MANDI' ? `Private Mandi · ${w.name}` : `Private Buyer · ${w.name}`;
                return (
                  <button
                    key={`${w.business_id}:${w.role}`}
                    type="button"
                    style={{
                      fontSize: '0.78rem',
                      padding: '0.4rem 0.6rem',
                      textAlign: 'left',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      border: isActive ? '1px solid #22c55e' : '1px solid rgba(255,255,255,0.12)',
                      background: isActive ? '#15803d' : 'rgba(255,255,255,0.06)',
                      color: '#ffffff',
                      cursor: 'pointer',
                      borderRadius: '6px',
                      width: '100%',
                      fontWeight: isActive ? 600 : 400,
                    }}
                    onClick={() => {
                      void switchTo(w);
                    }}
                  >
                    <span>{icon}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        <nav aria-label="Main navigation">
          {businessMode ? (
            <>
              {businessNav.map(({ to, title, icon: Icon }) => {
                const currentFull = location.pathname + location.search;
                const isItemActive = currentFull === to || (to === businessBase && location.pathname === businessBase && !location.search);
                return (
                  <NavLink
                    key={to}
                    to={to}
                    className={isItemActive ? 'active' : ''}
                  >
                    <Icon size={19} />
                    <span>{t(title)}</span>
                  </NavLink>
                );
              })}
              <div style={{ margin: '1rem 0 0.5rem 0', borderTop: '1px solid rgba(255,255,255,0.1)' }} />
              <NavLink to="/business/register">
                <Sprout size={19} />
                <span>{t('My business applications')}</span>
              </NavLink>
              {access?.roles.includes('SYSTEM_ADMIN') && (
                <NavLink to="/business/admin">
                  <ShieldCheck size={19} />
                  <span>{t('Review pending businesses')}</span>
                </NavLink>
              )}
            </>
          ) : (
            visibleNav.filter(item => item.farmer).map(({ to, title, farmerTitle, icon: Icon }) => (
              <NavLink end={to === '/'} key={to} to={to}>
                <Icon size={19} />
                <span>{t(farmerTitle || title)}</span>
              </NavLink>
            ))
          )}
          {!businessMode && (
            <details className="extra-navigation">
              <summary>{t('More tools')}</summary>
              {visibleNav.filter(item => !item.farmer).map(({ to, title, icon: Icon }) => (
                <NavLink key={to} to={to}>
                  <Icon size={19} />
                  <span>{t(title)}</span>
                </NavLink>
              ))}
            </details>
          )}
        </nav>
        <div className="sidebar-bottom">
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
              <strong>{t(activeNav?.farmerTitle || activeNav?.title || 'Page')}</strong>
            </span>
          </div>

          <div className="topbar-actions">
            <RoleSwitcher />
            <span className={`connection-pill ${connection.error ? 'is-offline' : ''}`} role="status">
              {connection.loading ? <RefreshCw size={14} className="spin" /> : connected ? <Wifi size={14} /> : <WifiOff size={14} />}
              <span>{connection.loading ? 'Connecting' : connected ? 'Backend connected' : 'Disconnected'}</span>
            </span>

            <div className="language-switch" role="group" aria-label="Language">
              <button lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button>
              <button lang="kn" aria-pressed={language === 'kn'} onClick={() => setLanguage('kn')}>ಕನ್ನಡ</button>
            </div>
          </div>
        </header>

        <main id="main-content" tabIndex={-1} ref={main}>
          {!privateView && <div className="scope-bar">
            <div>
              <span className="scope-dot" />
              <strong>{scope.market}</strong>
              <span className="scope-divider">/</span>
              {scope.commodity}
              <span className="scope-detail">· {scope.variety} / {scope.grade} ({t('Pilot scope: Karnataka')})</span>
            </div>
          </div>}

          {connection.error ? (
            <div className="disconnect-banner">
              <strong>Backend disconnected. Prices, forecasts and plans cannot be refreshed.</strong>
              <ErrorState error={connection.error} retry={() => { connection.retry(); catalog.retry(); }} />
            </div>
          ) : null}
          {!privateView && Boolean(catalog.error) && !connection.error && <ErrorState error={catalog.error} retry={catalog.retry} />}

          <p className="global-disclaimer" role="status" hidden={privateView || !catalog.data?.data.historical_demo_date}>
            {t('HISTORICAL REPLAY — not live market data')} · {catalog.data?.data.historical_demo_date}
          </p>
          {!privateView && <p className="global-disclaimer" role="note">Future prices are uncertain. You make the final decision.</p>}

          <Boundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/forecast" element={<Forecast />} />
              <Route path="/advisor" element={<AdvisorPage />} />
              <Route path="/results" element={<Results />} />
              <Route path="/explorer" element={<AdvisorPage explorer />} />
              <Route path="/transparency" element={<Transparency />} />
              <Route path="/sale-requests/*" element={<SaleWorkspace />} />
              <Route path="/sale-requests/:requestId" element={<SaleWorkspace />} />
              <Route path="/private-rates" element={<PrivateRatesPage />} />
              <Route path="/business" element={<BusinessPage />} />
              <Route path="/business/register" element={<BusinessPage />} />
              <Route path="/business/admin" element={<BusinessPage />} />
              <Route path="/business/apmc/:marketId/requests/:requestId" element={<SaleWorkspace owner={true} />} />
              <Route path="/business/apmc/:marketId/*" element={<SaleWorkspace owner={true} />} />
              <Route path="/business/apmc/:marketId" element={<SaleWorkspace owner={true} />} />
              <Route path="/mandi/requests/:requestId" element={<SaleWorkspace owner={true} />} />
              <Route path="/mandi/*" element={<SaleWorkspace owner={true} />} />
              <Route path="/business/mandi/:businessId" element={<BusinessPage />} />
              <Route path="/business/buyer/:businessId" element={<BusinessPage />} />
              <Route path="*" element={<><h1>{t('Page not found')}</h1><Link to="/">{t('Return to dashboard')}</Link></>} />
            </Routes>
          </Boundary>

          <footer className="footer">
            <span><ShieldCheck size={14} />Decision support, with the uncertainty left in.</span>
            <span>INR · Quintals · India Standard Time</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <AppProvider>
      <BusinessWorkspaceProvider>
      <Routes>
        <Route path="/mandi/*" element={<SaleWorkspace owner />} />
        <Route path="/mandi/requests/:requestId" element={<SaleWorkspace owner />} />
        <Route path="*" element={<Shell />} />
      </Routes>
      </BusinessWorkspaceProvider>
    </AppProvider>
  );
}
