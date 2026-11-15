import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, api } from '../api';
import { useLang } from '../i18n';
import type { Me, Tender } from '../types';
import { TenderCard } from './Explorer';

interface Props {
  user: Me | null;
  onOpenTender: (id: number) => void;
  onSignIn: () => void;
}

export default function Alerts({ user, onOpenTender, onSignIn }: Props) {
  const { d } = useLang();
  const [keywords, setKeywords] = useState('');
  const [categories, setCategories] = useState('');
  const [districts, setDistricts] = useState('');
  const [organisations, setOrganisations] = useState('');
  const [matches, setMatches] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .getAlerts()
      .then((res) => {
        if (cancelled) return;
        setKeywords(res.prefs?.keywords ?? '');
        setCategories(res.prefs?.categories ?? '');
        setDistricts(res.prefs?.districts ?? '');
        setOrganisations(res.prefs?.organisations ?? '');
        setMatches(res.matches ?? []);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : d.saveFailed);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (!user) {
    return (
      <div className="card">
        <h2 className="section-title">{d.alertsTitle}</h2>
        <p className="section-intro">{d.alertsSignInPrompt}</p>
        <button type="button" className="btn" onClick={onSignIn}>
          {d.signInJoin}
        </button>
      </div>
    );
  }

  if (loading) return <p>{d.loading}</p>;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await api.saveAlerts({
        keywords: keywords.trim() || null,
        categories: categories.trim() || null,
        districts: districts.trim() || null,
        organisations: organisations.trim() || null,
      });
      const res = await api.getAlerts();
      setMatches(res.matches ?? []);
      setNotice(d.prefsSaved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">{d.alertsTitle}</h2>
        <p className="section-intro">{d.alertsIntro}</p>
        {error && (
          <p className="notice notice-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="notice notice-success" role="status">
            {notice}
          </p>
        )}
        <form onSubmit={save}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="al-kw">{d.kwLabel}</label>
              <input
                id="al-kw"
                type="text"
                placeholder={d.kwPh}
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="al-cat">{d.catLabel}</label>
              <input
                id="al-cat"
                type="text"
                placeholder={d.catPh}
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="al-dist">{d.distLabel}</label>
              <input
                id="al-dist"
                type="text"
                placeholder={d.distPh}
                value={districts}
                onChange={(e) => setDistricts(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="al-org">{d.orgLabel}</label>
              <input
                id="al-org"
                type="text"
                placeholder={d.orgPh}
                value={organisations}
                onChange={(e) => setOrganisations(e.target.value)}
              />
            </div>
          </div>
          <button type="submit" className="btn" disabled={saving}>
            {d.savePrefs}
          </button>
        </form>
      </section>

      <section>
        <h2 className="section-title">{d.matchesTitle}</h2>
        {matches.length === 0 ? (
          <div className="empty-state">
            <p>{d.noMatches}</p>
          </div>
        ) : (
          <div className="tender-list">
            {matches.map((tender) => (
              <TenderCard key={tender.tender_id} tender={tender} onOpen={onOpenTender} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
