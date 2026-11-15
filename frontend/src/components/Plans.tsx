import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, api } from '../api';
import { fmtDateTime, fmtNum } from '../format';
import { useLang } from '../i18n';
import type { Me, PaymentSubmission, Plan } from '../types';

const PLAN_PRICES: Record<string, number> = { Premium: 399, Pro: 799 };

// Market table data (from the task copy; site names, years and prices
// are data, not UI chrome). "about 2011" has no dictionary key, so the
// two language forms are written here.
const MARKET_ROWS = [
  { site: 'BDTender', url: 'https://bdtender.com', since: '2003', price: 'BDT 1,050/mo, 8,190/yr' },
  { site: 'TenderBazar', url: 'https://tenderbazar.com', since: 'about2011', price: 'BDT 1,050/mo, 8,190/yr' },
  { site: 'alltender', url: 'https://alltender.com', since: '2000', price: 'BDT 1,000 + VAT/mo, 7,800/yr' },
];

interface Props {
  user: Me | null;
  onUserChange: () => void;
  onSignIn: () => void;
}

export default function Plans({ user, onUserChange, onSignIn }: Props) {
  const { d, lang, t } = useLang();
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [method, setMethod] = useState<'bKash' | 'Nagad'>('bKash');
  const [txnId, setTxnId] = useState('');
  const [sender, setSender] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [payments, setPayments] = useState<PaymentSubmission[]>([]);

  useEffect(() => {
    if (!user) {
      setPayments([]);
      return;
    }
    let cancelled = false;
    api
      .listMyPayments()
      .then((res) => {
        if (!cancelled) setPayments(res);
      })
      .catch(() => {
        // Payment history is secondary.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const hasPending =
    Boolean(user?.pending_payment_plan) ||
    payments.some((p) => p.status === 'Pending');

  const submitPayment = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedPlan) return;
    setSubmitting(true);
    setError('');
    setNotice('');
    try {
      await api.submitPayment({
        plan: selectedPlan,
        method,
        transaction_id: txnId.trim(),
        sender_number: sender.trim() || undefined,
      });
      setTxnId('');
      setSender('');
      setSelectedPlan(null);
      setPayments(await api.listMyPayments());
      onUserChange();
      setNotice(d.paymentSubmitted);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setSubmitting(false);
    }
  };

  const plans: { name: Plan; price: string; features: readonly string[] }[] = [
    { name: 'Free', price: d.freePrice, features: d.planFeatures.Free },
    {
      name: 'Premium',
      price: `${t('bdtPrice', { n: fmtNum(PLAN_PRICES.Premium, lang) })}${d.perMonth}`,
      features: d.planFeatures.Premium,
    },
    {
      name: 'Pro',
      price: `${t('bdtPrice', { n: fmtNum(PLAN_PRICES.Pro, lang) })}${d.perMonth}`,
      features: d.planFeatures.Pro,
    },
  ];

  return (
    <div>
      <h2 className="section-title">{d.plansTitle}</h2>
      <p className="section-intro">{d.plansIntro}</p>

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

      {!user && (
        <p className="notice notice-info">
          {d.plansSignInNote}{' '}
          <button type="button" className="link-btn" onClick={onSignIn}>
            {d.signInJoin}
          </button>
        </p>
      )}

      <div className="plan-grid">
        {plans.map((plan) => {
          const isCurrent = user?.plan === plan.name;
          const isPending = user?.pending_payment_plan === plan.name;
          return (
            <article
              className={`card plan-card${plan.name === 'Premium' ? ' highlight' : ''}`}
              key={plan.name}
            >
              <h3>{plan.name}</h3>
              <p className="plan-price">{plan.price}</p>
              <ul className="plan-features">
                {plan.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              {isCurrent ? (
                <span className="badge">{d.currentPlan}</span>
              ) : isPending ? (
                <span className="badge badge-pending">{d.paymentPendingBadge}</span>
              ) : plan.name === 'Free' ? null : user ? (
                <button
                  type="button"
                  className="btn"
                  onClick={() => setSelectedPlan(plan.name)}
                >
                  {t('choosePlan', { name: plan.name })}
                </button>
              ) : (
                <button type="button" className="btn" onClick={onSignIn}>
                  {t('choosePlan', { name: plan.name })}
                </button>
              )}
            </article>
          );
        })}
      </div>

      {selectedPlan && user && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="section-title">{t('payTitle', { plan: selectedPlan })}</h2>
          <ol className="pay-steps">
            {d.paySteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="field-note" style={{ marginBottom: '1rem' }}>
            {d.payVerifyNote}
          </p>
          <form onSubmit={submitPayment}>
            <div className="field">
              <span>{d.payWith}</span>
              <div className="method-toggle" role="group" aria-label={d.payWith}>
                {(['bKash', 'Nagad'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={method === m ? 'active' : ''}
                    onClick={() => setMethod(m)}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <span>{d.payAmount}</span>
              <div className="amount-readonly">
                {t('bdtPrice', { n: fmtNum(PLAN_PRICES[selectedPlan], lang) })}
              </div>
            </div>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="pay-txn">{d.payTxnId}</label>
                <input
                  id="pay-txn"
                  type="text"
                  required
                  minLength={4}
                  maxLength={60}
                  placeholder={d.payTxnPh}
                  value={txnId}
                  onChange={(e) => setTxnId(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="pay-sender">{d.paySender}</label>
                <input
                  id="pay-sender"
                  type="tel"
                  placeholder="01XXXXXXXXX"
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                />
              </div>
            </div>
            <div className="row">
              <button type="submit" className="btn" disabled={submitting || hasPending}>
                {d.paySubmit}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setSelectedPlan(null)}
              >
                {d.close}
              </button>
            </div>
            {hasPending && (
              <p className="field-note" style={{ marginTop: '0.75rem' }}>
                {d.paymentPendingBadge}
              </p>
            )}
          </form>
        </section>
      )}

      {user && (
        <section style={{ marginBottom: '1.5rem' }}>
          <h2 className="section-title">{d.myPaymentsTitle}</h2>
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
                  {p.sender_number ? ` · ${d.paySender}: ${p.sender_number}` : ''}
                </p>
                {p.review_note && <p className="field-note">{p.review_note}</p>}
                <p className="field-note">
                  {p.submitted_at ? fmtDateTime(p.submitted_at, lang) : ''}
                </p>
              </article>
            ))
          )}
        </section>
      )}

      <section className="card">
        <h2 className="section-title">{d.marketTitle}</h2>
        <div className="market-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{d.tableSite}</th>
                <th>{d.tableSince}</th>
                <th>{d.tableBasePrice}</th>
                <th>{d.tableJv}</th>
              </tr>
            </thead>
            <tbody>
              {MARKET_ROWS.map((row) => (
                <tr key={row.site}>
                  <td>
                    <a href={row.url} target="_blank" rel="noopener noreferrer">
                      {row.site}
                    </a>
                  </td>
                  <td>
                    {row.since === 'about2011'
                      ? lang === 'bn'
                        ? 'প্রায় ২০১১'
                        : 'about 2011'
                      : row.since}
                  </td>
                  <td>{row.price}</td>
                  <td>{d.noWord}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="field-note" style={{ marginTop: '0.9rem' }}>
          {d.marketNote}
        </p>
      </section>
    </div>
  );
}
