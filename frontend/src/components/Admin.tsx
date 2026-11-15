import { useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import { fmtDate, fmtDateTime, fmtNum } from '../format';
import { useLang } from '../i18n';
import type { AdminOverview, Me, Plan } from '../types';

interface Props {
  user: Me | null;
}

export default function Admin({ user }: Props) {
  const { d, lang, t } = useLang();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [replies, setReplies] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.is_admin) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .adminOverview()
      .then((res) => {
        if (!cancelled) setOverview(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : d.adminActionFailed);
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

  if (!user?.is_admin) {
    return (
      <div className="card">
        <p>{d.adminDenied}</p>
      </div>
    );
  }

  if (loading) return <p>{d.loading}</p>;

  const refresh = async () => {
    try {
      setOverview(await api.adminOverview());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.adminActionFailed);
    }
  };

  const reviewPayment = async (id: number, approve: boolean) => {
    setBusy(`pay-${id}`);
    setError('');
    setNotice('');
    try {
      await api.reviewPayment(id, approve);
      await refresh();
      setNotice(d.adminPaymentDone);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.adminActionFailed);
    } finally {
      setBusy(null);
    }
  };

  const replyConsulting = async (id: number) => {
    const reply = (replies[id] ?? '').trim();
    if (!reply) return;
    setBusy(`con-${id}`);
    setError('');
    setNotice('');
    try {
      await api.replyConsulting(id, reply);
      setReplies((prev) => ({ ...prev, [id]: '' }));
      await refresh();
      setNotice(d.adminReplySent);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.adminActionFailed);
    } finally {
      setBusy(null);
    }
  };

  const setPlan = async (userId: number, plan: Plan) => {
    setBusy(`user-${userId}`);
    setError('');
    setNotice('');
    try {
      await api.setUserPlan(userId, plan);
      await refresh();
      setNotice(d.adminPlanSet);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.planUpdateFailed);
    } finally {
      setBusy(null);
    }
  };

  const totals = overview?.totals;
  const payments = overview?.payments ?? [];
  const consulting = overview?.consulting ?? [];
  const users = overview?.users ?? [];

  return (
    <div>
      <h2 className="section-title">{d.adminTitle}</h2>
      <p className="section-intro">{d.adminIntro}</p>

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

      {totals && (
        <div className="totals-row">
          <span className="total-chip">
            {fmtNum(totals.users, lang)}
            {d.adminUsers}
          </span>
          <span className="total-chip">
            {fmtNum(totals.premium, lang)} Premium
          </span>
          <span className="total-chip">
            {fmtNum(totals.pro, lang)} Pro
          </span>
          <span className="total-chip">
            {fmtNum(totals.pending_payments, lang)}
            {d.adminPendingPayments}
          </span>
          <span className="total-chip">
            {fmtNum(totals.open_consulting, lang)}
            {d.adminOpenConsulting}
          </span>
          <span className="total-chip">
            {fmtNum(totals.tenders, lang)}
            {d.tendersStored}
          </span>
        </div>
      )}

      <section className="admin-section">
        <h2 className="section-title">{d.adminPaymentsTitle}</h2>
        {payments.length === 0 ? (
          <p className="field-note">{d.adminNoPayments}</p>
        ) : (
          payments.map((p) => (
            <article className="card admin-item" key={p.id}>
              <div className="admin-item-head">
                <strong>
                  {p.plan} · {p.method} ·{' '}
                  {p.amount_bdt !== null && p.amount_bdt !== undefined
                    ? t('bdtPrice', { n: fmtNum(p.amount_bdt, lang) })
                    : ''}
                </strong>
                <span
                  className={`badge ${
                    p.status === 'Pending'
                      ? 'badge-pending'
                      : p.status === 'Rejected'
                        ? 'badge-rejected'
                        : 'badge-approved'
                  }`}
                >
                  {d.paymentStatus[p.status] ?? p.status}
                </span>
              </div>
              <p>
                <span className="mono">{p.transaction_id}</span>
              </p>
              <p>
                {p.user_name ?? p.name ?? ''}{' '}
                {p.user_email ?? p.email ? `(${p.user_email ?? p.email})` : ''}
              </p>
              {p.sender_number && (
                <p>
                  {d.adminSender}: {p.sender_number}
                </p>
              )}
              <p className="field-note">
                {p.submitted_at ? fmtDateTime(p.submitted_at, lang) : ''}
              </p>
              {p.review_note && <p className="field-note">{p.review_note}</p>}
              {p.status === 'Pending' && (
                <div className="row" style={{ marginTop: '0.6rem' }}>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy === `pay-${p.id}`}
                    onClick={() => void reviewPayment(p.id, true)}
                  >
                    {d.adminApprove}
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    disabled={busy === `pay-${p.id}`}
                    onClick={() => void reviewPayment(p.id, false)}
                  >
                    {d.adminReject}
                  </button>
                </div>
              )}
            </article>
          ))
        )}
      </section>

      <section className="admin-section">
        <h2 className="section-title">{d.adminConsultingTitle}</h2>
        {consulting.length === 0 ? (
          <p className="field-note">{d.adminNoConsulting}</p>
        ) : (
          consulting.map((c) => (
            <article className="card admin-item" key={c.id}>
              <div className="admin-item-head">
                <strong>{c.topic}</strong>
                <span className={`badge ${c.status === 'Open' ? 'badge-open' : ''}`}>
                  {d.consultStatus[c.status] ?? c.status}
                </span>
              </div>
              <p className="field-note">
                {[c.user_name ?? c.name, c.user_email ?? c.email, c.company_name, c.plan]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              <p className="field-note">
                {[c.tender_title, c.created_at ? fmtDateTime(c.created_at, lang) : '']
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              <p style={{ whiteSpace: 'pre-wrap' }}>{c.message}</p>
              {c.reply ? (
                <div className="reply-box">
                  <p className="reply-label">{d.consultReplyFrom}</p>
                  <p>{c.reply}</p>
                </div>
              ) : (
                <div style={{ marginTop: '0.75rem' }}>
                  <div className="field">
                    <label htmlFor={`reply-${c.id}`}>{d.adminReplyLabel}</label>
                    <textarea
                      id={`reply-${c.id}`}
                      placeholder={d.adminReplyPh}
                      maxLength={4000}
                      value={replies[c.id] ?? ''}
                      onChange={(e) =>
                        setReplies((prev) => ({ ...prev, [c.id]: e.target.value }))
                      }
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy === `con-${c.id}` || !(replies[c.id] ?? '').trim()}
                    onClick={() => void replyConsulting(c.id)}
                  >
                    {d.adminSendReply}
                  </button>
                </div>
              )}
            </article>
          ))
        )}
      </section>

      <section className="admin-section">
        <h2 className="section-title">{d.adminUsersTitle}</h2>
        {users.length === 0 ? (
          <p className="field-note">{d.adminNoUsers}</p>
        ) : (
          <div className="card members-wrap" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{d.adminColUser}</th>
                  <th>{d.adminColCompany}</th>
                  <th>{d.adminColJoined}</th>
                  <th>{d.adminColActivity}</th>
                  <th>{d.adminColPlan}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <strong>{u.name}</strong>
                      <br />
                      <span className="field-note">{u.email}</span>
                      {u.is_admin && (
                        <>
                          {' '}
                          <span className="badge">{d.tabAdmin}</span>
                        </>
                      )}
                    </td>
                    <td>{u.company ?? u.company_name ?? ''}</td>
                    <td>
                      {u.signed_up_at
                        ? fmtDate(u.signed_up_at, lang)
                        : u.created_at
                          ? fmtDate(u.created_at, lang)
                          : ''}
                    </td>
                    <td>
                      {t('adminActivity', {
                        favs: fmtNum(u.counts?.favourites ?? 0, lang),
                        docs: fmtNum(u.counts?.documents ?? 0, lang),
                        jv: fmtNum(u.counts?.jv_posts ?? 0, lang),
                        consult: fmtNum(u.counts?.consulting_requests ?? 0, lang),
                        alerts: Boolean(u.has_alert_prefs),
                      })}
                    </td>
                    <td>
                      <select
                        value={u.plan}
                        aria-label={t('adminPlanAria', { name: u.name })}
                        disabled={busy === `user-${u.id}`}
                        onChange={(e) => void setPlan(u.id, e.target.value as Plan)}
                      >
                        {(['Free', 'Premium', 'Pro'] as const).map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
