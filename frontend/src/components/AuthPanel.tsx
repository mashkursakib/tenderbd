import { useState } from 'react';
import { ApiError, api, setToken } from '../api';
import { useLang } from '../i18n';
import type { Me } from '../types';

type Mode = 'signin' | 'signup' | 'forgot' | 'reset';

interface Props {
  onAuth: (me: Me) => void;
  onClose: () => void;
  initialMode?: 'signin' | 'reset';
  resetEmail?: string;
  resetToken?: string;
}

export default function AuthPanel({ onAuth, onClose, initialMode, resetEmail, resetToken }: Props) {
  const { d } = useLang();
  const [mode, setMode] = useState<Mode>(initialMode ?? 'signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState(resetEmail ?? '');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const fail = (err: unknown, fallback: string) => {
    setError(err instanceof ApiError ? err.message : fallback);
  };

  const finishAuth = async (token: string) => {
    setToken(token);
    const me = await api.me();
    onAuth(me);
  };

  const submitSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await api.signin(email.trim(), password);
      await finishAuth(res.token);
    } catch (err) {
      fail(err, d.authSignInFailed);
    } finally {
      setBusy(false);
    }
  };

  const submitSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await api.signup(name.trim(), email.trim(), password);
      await finishAuth(res.token);
    } catch (err) {
      fail(err, d.authSignUpFailed);
    } finally {
      setBusy(false);
    }
  };

  // Production reset flow: the server emails a reset link (1-hour TTL).
  // There is no on-screen code; the link opens this panel in 'reset' mode.
  const submitForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setBusy(true);
    try {
      const res = await api.requestPasswordReset(email.trim());
      setNotice(res.message);
    } catch (err) {
      fail(err, d.authTryAgain);
    } finally {
      setBusy(false);
    }
  };

  const submitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetToken) return;
    setError('');
    setBusy(true);
    try {
      const res = await api.resetPassword(email.trim(), resetToken, newPassword);
      await finishAuth(res.token);
    } catch (err) {
      fail(err, d.authTryAgain);
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setError('');
    setNotice('');
  };

  return (
    <div className="auth-panel">
      {mode !== 'reset' && (
        <div className="auth-tabs">
          <button
            type="button"
            className={mode === 'signin' ? 'active' : ''}
            onClick={() => switchMode('signin')}
          >
            {d.authSignIn}
          </button>
          <button
            type="button"
            className={mode === 'signup' ? 'active' : ''}
            onClick={() => switchMode('signup')}
          >
            {d.authCreateAccount}
          </button>
        </div>
      )}

      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {notice && <p className="notice notice-info" role="status">{notice}</p>}

      {mode === 'signin' && (
        <form onSubmit={submitSignIn}>
          <div className="field">
            <label htmlFor="auth-email">{d.authEmail}</label>
            <input
              id="auth-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="auth-password">{d.authPassword}</label>
            <input
              id="auth-password"
              type="password"
              required
              minLength={8}
              maxLength={72}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
            <p className="field-note">{d.authPasswordHint}</p>
          </div>
          <div className="row">
            <button type="submit" className="btn btn-light" disabled={busy}>
              {d.authSignIn}
            </button>
            <button type="button" className="link-btn" onClick={() => switchMode('forgot')}>
              {d.authForgot}
            </button>
            <button type="button" className="link-btn" onClick={onClose}>
              {d.close}
            </button>
          </div>
        </form>
      )}

      {mode === 'signup' && (
        <form onSubmit={submitSignUp}>
          <div className="field">
            <label htmlFor="auth-name">{d.authName}</label>
            <input
              id="auth-name"
              type="text"
              required
              minLength={2}
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
            />
          </div>
          <div className="field">
            <label htmlFor="auth-email2">{d.authEmail}</label>
            <input
              id="auth-email2"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="auth-password2">{d.authPassword}</label>
            <input
              id="auth-password2"
              type="password"
              required
              minLength={8}
              maxLength={72}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <p className="field-note">{d.authPasswordHint}</p>
          </div>
          <div className="row">
            <button type="submit" className="btn btn-light" disabled={busy}>
              {d.authSubmitCreate}
            </button>
            <button type="button" className="link-btn" onClick={onClose}>
              {d.close}
            </button>
          </div>
        </form>
      )}

      {mode === 'forgot' && (
        <form onSubmit={submitForgot}>
          <p>{d.authForgotIntro}</p>
          <div className="field">
            <label htmlFor="auth-email3">{d.authEmail}</label>
            <input
              id="auth-email3"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="row">
            <button type="submit" className="btn btn-light" disabled={busy}>
              {d.authSendReset}
            </button>
            <button type="button" className="link-btn" onClick={() => switchMode('signin')}>
              {d.authBackToSignIn}
            </button>
          </div>
        </form>
      )}

      {mode === 'reset' && (
        <form onSubmit={submitReset}>
          <div className="field">
            <label htmlFor="auth-email4">{d.authEmail}</label>
            <input
              id="auth-email4"
              type="email"
              required
              readOnly
              value={email}
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="auth-new-password">{d.authNewPassword}</label>
            <input
              id="auth-new-password"
              type="password"
              required
              minLength={8}
              maxLength={72}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
            <p className="field-note">{d.authPasswordHint}</p>
          </div>
          <div className="row">
            <button type="submit" className="btn btn-light" disabled={busy || !resetToken}>
              {d.authResetSubmit}
            </button>
            <button type="button" className="link-btn" onClick={() => switchMode('signin')}>
              {d.authBackToSignIn}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
