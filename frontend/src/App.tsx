import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken } from './api';
import { fmtNum, fmtTimeAgo } from './format';
import {
  LANG_KEY,
  LangContext,
  bn,
  en,
  translate,
  type Lang,
  type StrKey,
  type TranslateVars,
} from './i18n';
import type { Me, Stats, Tender, ThemePref } from './types';
import Admin from './components/Admin';
import Alerts from './components/Alerts';
import AuthPanel from './components/AuthPanel';
import Capability from './components/Capability';
import Consulting from './components/Consulting';
import Explorer from './components/Explorer';
import JvRoom from './components/JvRoom';
import Plans from './components/Plans';
import TenderDetail from './components/TenderDetail';

export type Tab =
  | 'tenders'
  | 'capability'
  | 'jv'
  | 'alerts'
  | 'consulting'
  | 'plans'
  | 'admin';

const THEME_KEY = 'tenderbd_theme';

function readThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v === 'dark' || v === 'device') return v;
  } catch {
    // Fall through to the default.
  }
  return 'light';
}

function resolveTheme(pref: ThemePref): 'light' | 'dark' {
  if (pref === 'device') {
    return window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }
  return pref;
}

function readLang(): Lang {
  try {
    return localStorage.getItem(LANG_KEY) === 'bn' ? 'bn' : 'en';
  } catch {
    return 'en';
  }
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(readLang);
  const [themePref, setThemePref] = useState<ThemePref>(readThemePref);
  const [user, setUser] = useState<Me | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [tab, setTab] = useState<Tab>('tenders');
  const [authOpen, setAuthOpen] = useState(false);
  const [selectedTenderId, setSelectedTenderId] = useState<number | null>(null);
  const [jvPrefill, setJvPrefill] = useState<Tender | null>(null);
  const [consultingPrefill, setConsultingPrefill] = useState<Tender | null>(null);
  const [resetParams, setResetParams] = useState<{ email: string; token: string } | null>(null);

  const t = useCallback(
    (key: StrKey, vars?: TranslateVars) => translate(lang, key, vars),
    [lang],
  );
  const d = lang === 'bn' ? bn : en;

  const langValue = useMemo(
    () => ({
      lang,
      setLang: (next: Lang) => {
        setLangState(next);
        try {
          localStorage.setItem(LANG_KEY, next);
        } catch {
          // Storage unavailable; language just won't persist.
        }
      },
      d,
      t,
    }),
    [lang, d, t],
  );

  // Apply the resolved theme to <html data-theme>.
  useEffect(() => {
    document.documentElement.dataset.theme = resolveTheme(themePref);
    try {
      localStorage.setItem(THEME_KEY, themePref);
    } catch {
      // Ignore storage failures.
    }
  }, [themePref]);

  // Follow the OS theme while 'device' is selected.
  useEffect(() => {
    if (themePref !== 'device') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      document.documentElement.dataset.theme = resolveTheme('device');
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [themePref]);

  const refreshMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setToken(null);
      setUser(null);
    }
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.getStats());
    } catch {
      // Stats are decorative; the explorer still works without them.
    }
  }, []);

  useEffect(() => {
    void refreshMe();
    void refreshStats();
  }, [refreshMe, refreshStats]);

  // Password-reset deep link: the emailed link lands on
  // /reset-password?token=...&email=... (see backend email service).
  // Open the auth panel straight into the set-new-password form.
  useEffect(() => {
    if (window.location.pathname !== '/reset-password') return;
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const email = params.get('email');
    if (token && email) {
      setResetParams({ email, token });
      setAuthOpen(true);
    }
  }, []);

  const handleAuth = useCallback((me: Me) => {
    setUser(me);
    setAuthOpen(false);
    setResetParams(null);
    if (window.location.pathname === '/reset-password') {
      window.history.replaceState({}, '', '/');
    }
  }, []);

  const handleSignOut = useCallback(async () => {
    try {
      await api.signout();
    } catch {
      // Still sign out locally even if the server call fails.
    }
    setToken(null);
    setUser(null);
    setTab('tenders');
  }, []);

  const openTender = useCallback((id: number) => setSelectedTenderId(id), []);

  const goToJv = useCallback((tender?: Tender) => {
    setJvPrefill(tender ?? null);
    setTab('jv');
    setSelectedTenderId(null);
  }, []);

  const goToConsulting = useCallback((tender?: Tender) => {
    setConsultingPrefill(tender ?? null);
    setTab('consulting');
    setSelectedTenderId(null);
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'tenders', label: d.tabTenders },
    { id: 'capability', label: d.tabCapability },
    { id: 'jv', label: d.tabJv },
    { id: 'alerts', label: d.tabAlerts },
    { id: 'consulting', label: d.tabConsulting },
    { id: 'plans', label: d.tabPlans },
  ];
  if (user?.is_admin) tabs.push({ id: 'admin', label: d.tabAdmin });

  const lastRun = stats?.last_run ?? null;

  return (
    <LangContext.Provider value={langValue}>
      <div className="page">
        <header className="masthead">
          <div className="wrap">
            <div className="masthead-top">
              <div>
                <h1 className="brand">TenderBD</h1>
                <p className="tagline">{d.tagline}</p>
                <p className="intro">{d.intro}</p>
              </div>
              <div className="masthead-actions">
                <div className="lang-toggle" role="group" aria-label={d.languageLabel}>
                  <button
                    type="button"
                    className={lang === 'en' ? 'active' : ''}
                    onClick={() => langValue.setLang('en')}
                  >
                    EN
                  </button>
                  <button
                    type="button"
                    className={lang === 'bn' ? 'active' : ''}
                    onClick={() => langValue.setLang('bn')}
                  >
                    বাংলা
                  </button>
                </div>
                {user ? (
                  <>
                    <div className="user-block">
                      <div className="user-name">{user.name}</div>
                      <div>
                        {user.plan} {d.planWord} ·{' '}
                        {user.has_profile ? d.profileReady : d.noProfileYet}
                      </div>
                      {user.pending_payment_plan && (
                        <div className="pending-warn">
                          {d.paymentPendingBadge}: {user.pending_payment_plan}
                        </div>
                      )}
                    </div>
                    <button type="button" className="btn btn-light btn-sm" onClick={handleSignOut}>
                      {d.signOut}
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn btn-light"
                    onClick={() => setAuthOpen((v) => !v)}
                  >
                    {d.signInJoin}
                  </button>
                )}
              </div>
            </div>

            {authOpen && !user && (
              <AuthPanel
                onAuth={handleAuth}
                onClose={() => setAuthOpen(false)}
                initialMode={resetParams ? 'reset' : 'signin'}
                resetEmail={resetParams?.email}
                resetToken={resetParams?.token}
              />
            )}

            <div className="stats-row" aria-live="polite">
              <span className="stat-chip">
                {fmtNum(stats?.total ?? 0, lang)}
                {d.tendersStored}
              </span>
              <span className="stat-chip">
                {fmtNum(stats?.open_now ?? 0, lang)}
                {d.closingInFuture}
              </span>
              {(lastRun?.finished_at || lastRun?.started_at) && (
                <span className="stat-chip">
                  {t('lastRefresh', {
                    when: fmtTimeAgo(lastRun.finished_at ?? lastRun.started_at, lang),
                    n: fmtNum(lastRun.tenders_new ?? 0, lang),
                  })}
                </span>
              )}
            </div>
          </div>
        </header>

        <nav className="nav-bar" aria-label="Sections">
          <div className="wrap nav-inner">
            <div className="tabs">
              {tabs.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={`tab${tab === id ? ' active' : ''}`}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="theme-group" role="group" aria-label={d.themeLabel}>
              {(['device', 'white', 'black'] as const).map((key) => {
                const pref: ThemePref =
                  key === 'white' ? 'light' : key === 'black' ? 'dark' : 'device';
                const label =
                  key === 'white' ? d.themeWhite : key === 'black' ? d.themeBlack : d.themeDevice;
                return (
                  <button
                    key={key}
                    type="button"
                    className={themePref === pref ? 'active' : ''}
                    onClick={() => setThemePref(pref)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </nav>

        <main className="main">
          <div className="wrap">
            {tab === 'tenders' && (
              <Explorer
                user={user}
                onOpenTender={openTender}
                onRefreshStats={refreshStats}
                onGoToPlans={() => setTab('plans')}
              />
            )}
            {tab === 'capability' && (
              <Capability user={user} onProfileSaved={refreshMe} onSignIn={() => setAuthOpen(true)} />
            )}
            {tab === 'jv' && (
              <JvRoom
                user={user}
                prefillTender={jvPrefill}
                onPrefillConsumed={() => setJvPrefill(null)}
                onOpenTender={openTender}
                onGoToPlans={() => setTab('plans')}
                onSignIn={() => setAuthOpen(true)}
              />
            )}
            {tab === 'alerts' && (
              <Alerts user={user} onOpenTender={openTender} onSignIn={() => setAuthOpen(true)} />
            )}
            {tab === 'consulting' && (
              <Consulting
                user={user}
                prefillTender={consultingPrefill}
                onPrefillConsumed={() => setConsultingPrefill(null)}
                onGoToPlans={() => setTab('plans')}
                onSignIn={() => setAuthOpen(true)}
              />
            )}
            {tab === 'plans' && (
              <Plans user={user} onUserChange={refreshMe} onSignIn={() => setAuthOpen(true)} />
            )}
            {tab === 'admin' && <Admin user={user} />}
          </div>
        </main>

        <footer className="footer">
          <div className="wrap">
            <p>{d.footerText}</p>
            <p className="footer-brand">TenderBD · tender.masconsultancy.org</p>
          </div>
        </footer>

        {selectedTenderId !== null && (
          <TenderDetail
            tenderId={selectedTenderId}
            user={user}
            onClose={() => setSelectedTenderId(null)}
            onFindJv={goToJv}
            onAskMas={goToConsulting}
            onSignIn={() => {
              setSelectedTenderId(null);
              setAuthOpen(true);
            }}
          />
        )}
      </div>
    </LangContext.Provider>
  );
}
