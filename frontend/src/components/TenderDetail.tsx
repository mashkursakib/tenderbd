import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import { fmtDate, fmtNum } from '../format';
import { useLang } from '../i18n';
import type { Evaluation, Me, Summary, Tender } from '../types';

// Eligibility check names are not in the UI dictionaries; the
// evaluation surface (names, details, verdicts, note) stays English,
// per SPEC section 9.
const CHECK_NAMES: Record<string, string> = {
  category: 'Category match',
  turnover: 'Turnover vs tender scale',
  liquidity: 'Liquidity for tender security',
  experience: 'Similar work experience',
};

interface Props {
  tenderId: number;
  user: Me | null;
  onClose: () => void;
  onFindJv: (tender: Tender) => void;
  onAskMas: (tender: Tender) => void;
  onSignIn: () => void;
}

export default function TenderDetail({
  tenderId,
  user,
  onClose,
  onFindJv,
  onAskMas,
  onSignIn,
}: Props) {
  const { d, lang, t } = useLang();
  const [tender, setTender] = useState<Tender | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isFav, setIsFav] = useState(false);
  const [favBusy, setFavBusy] = useState(false);
  const [favError, setFavError] = useState('');
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState('');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState('');

  const isPremium = user?.plan === 'Premium' || user?.plan === 'Pro';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .getTender(tenderId)
      .then((res) => {
        if (!cancelled) setTender(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : d.loadTenderError);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenderId, d.loadTenderError]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api
      .listFavourites()
      .then((res) => {
        if (!cancelled) setIsFav(res.favourite_ids.includes(tenderId));
      })
      .catch(() => {
        // Favourite state is secondary; the toggle still works.
      });
    return () => {
      cancelled = true;
    };
  }, [user, tenderId]);

  // Eligibility is scored automatically for Premium+ members.
  useEffect(() => {
    if (!user || !isPremium) return;
    let cancelled = false;
    setEvalLoading(true);
    setEvalError('');
    api
      .evaluate(tenderId)
      .then((res) => {
        if (!cancelled) setEvaluation(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setEvalError(err instanceof ApiError ? err.message : d.saveFailed);
        }
      })
      .finally(() => {
        if (!cancelled) setEvalLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, tenderId]);

  // Close on Escape; lock body scroll while open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const toggleFav = useCallback(async () => {
    if (!user) {
      onSignIn();
      return;
    }
    setFavBusy(true);
    setFavError('');
    try {
      const res = await api.toggleFavourite(tenderId);
      setIsFav(res.favourite);
    } catch (err) {
      setFavError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setFavBusy(false);
    }
  }, [user, tenderId, onSignIn, d.saveFailed]);

  const runSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError('');
    try {
      setSummary(await api.summarize(tenderId, lang));
    } catch (err) {
      setSummaryError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setSummaryLoading(false);
    }
  }, [tenderId, lang, d.saveFailed]);

  const officialUrl = `https://eprocure.gov.bd/resources/common/ViewTender.jsp?id=${tenderId}&h=t`;

  const field = (label: string, value: string | null | undefined) =>
    value ? (
      <div className="detail-field">
        <dt>{label}</dt>
        <dd>{value}</dd>
      </div>
    ) : null;

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={tender?.title ?? `${d.tenderWord} ${tenderId}`}
    >
      <div className="modal">
        <div className="modal-head">
          <h2>{tender?.title ?? `${d.tenderWord} ${tenderId}`}</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            {d.close}
          </button>
        </div>

        {loading && <p>{d.loadingNotice}</p>}
        {error && (
          <p className="notice notice-error" role="alert">
            {error}
          </p>
        )}

        {tender && (
          <>
            <dl className="detail-grid">
              {field(d.tenderId, String(tender.tender_id))}
              {field(d.refNo, tender.ref_no)}
              {field(
                d.status,
                tender.status ??
                  (tender.status_bucket === 'closed'
                    ? d.statusClosed
                    : tender.status_bucket === 'closing_soon'
                      ? d.statusClosingSoon
                      : d.statusActive),
              )}
              {field(
                d.natureMethod,
                [tender.proc_nature, tender.method].filter(Boolean).join(' / ') || null,
              )}
              {field(d.district, tender.district)}
              {field(d.division, tender.computed_division ?? tender.division)}
              {field(d.ministry, tender.ministry)}
              {field(d.procuringEntity, tender.procuring_entity)}
              {field(d.organisation, tender.organisation)}
              {field(d.published, tender.publish_dt ? fmtDate(tender.publish_dt, lang) : null)}
              {field(d.closing, tender.close_dt ? fmtDate(tender.close_dt, lang) : null)}
              {field(
                d.docPrice,
                tender.document_price_bdt !== null && tender.document_price_bdt !== undefined
                  ? t('bdtPrice', { n: fmtNum(tender.document_price_bdt, lang) })
                  : null,
              )}
              {field(
                d.emd,
                tender.emd_bdt !== null && tender.emd_bdt !== undefined
                  ? t('bdtPrice', { n: fmtNum(tender.emd_bdt, lang) })
                  : d.securityNotPublished,
              )}
            </dl>

            {tender.description && (
              <div className="detail-block">
                <h3>{d.description}</h3>
                <p>{tender.description}</p>
              </div>
            )}

            {tender.eligibility_text && (
              <div className="detail-block">
                <h3>{d.eligibilityFromNotice}</h3>
                <p>{tender.eligibility_text}</p>
              </div>
            )}

            {isPremium && (
              <div className="detail-block">
                <h3>{d.aiSummaryTitle}</h3>
                <p className="field-note">{d.aiSummaryIntro}</p>
                {summaryError && (
                  <p className="notice notice-error" role="alert">
                    {summaryError}
                  </p>
                )}
                {summary ? (
                  <>
                    <p>
                      <strong>{summary.headline}</strong>
                    </p>
                    <p>{summary.scope}</p>
                    {summary.eligibility_points.length > 0 && (
                      <>
                        <h3>{d.aiWhoCanBid}</h3>
                        <ul>
                          {summary.eligibility_points.map((pt, i) => (
                            <li key={i}>{pt}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {summary.key_requirements.length > 0 && (
                      <>
                        <h3>{d.aiWhatToPrepare}</h3>
                        <ul>
                          {summary.key_requirements.map((pt, i) => (
                            <li key={i}>{pt}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {summary.watch_outs.length > 0 && (
                      <>
                        <h3>{d.aiWatchOut}</h3>
                        <ul>
                          {summary.watch_outs.map((pt, i) => (
                            <li key={i}>{pt}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </>
                ) : null}
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={runSummary}
                  disabled={summaryLoading}
                >
                  {summaryLoading
                    ? d.aiSummarizing
                    : summary
                      ? d.aiSummarizeAgain
                      : d.aiSummarize}
                </button>
              </div>
            )}

            {isPremium && (
              <div className="detail-block">
                <h3>{d.yourEligibility}</h3>
                {evalLoading && <p>{d.scoringProfile}</p>}
                {evalError && (
                  <p className="notice notice-error" role="alert">
                    {evalError}
                  </p>
                )}
                {evaluation && (
                  <div className="score-box">
                    {evaluation.score !== null && (
                      <p className="score-line">
                        {evaluation.score} / 100
                        {evaluation.verdict ? ` · ${evaluation.verdict}` : ''}
                      </p>
                    )}
                    {evaluation.checks.length > 0 && (
                      <ul className="check-list">
                        {evaluation.checks.map((check) => (
                          <li key={check.key}>
                            <div className="check-item">
                              <span className="check-name">
                                {CHECK_NAMES[check.key] ?? check.key}
                              </span>
                              <span className={`check-status ${check.status}`}>
                                {check.status} · {check.points}/{check.max_points}
                              </span>
                            </div>
                            <p className="check-detail">{check.detail}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="estimate-note">{evaluation.note}</p>
                  </div>
                )}
              </div>
            )}

            {favError && (
              <p className="notice notice-error" role="alert">
                {favError}
              </p>
            )}

            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={toggleFav}
                disabled={favBusy}
                aria-label={
                  isFav
                    ? t('removeFavAria', { id: tenderId })
                    : t('addFavAria', { id: tenderId })
                }
              >
                {isFav ? d.savedFav : d.saveFav}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => onFindJv(tender)}>
                {d.findJvPartner}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => onAskMas(tender)}>
                {d.askMasAbout}
              </button>
              <a
                className="btn btn-outline"
                href={officialUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
              >
                {d.viewOfficialNotice}
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
