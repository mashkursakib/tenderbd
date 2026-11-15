import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, api } from '../api';
import { fmtDateTime } from '../format';
import { useLang } from '../i18n';
import type { ConsultingRequest, Me, Tender } from '../types';

interface Props {
  user: Me | null;
  prefillTender: Tender | null;
  onPrefillConsumed: () => void;
  onGoToPlans: () => void;
  onSignIn: () => void;
}

export default function Consulting({
  user,
  prefillTender,
  onPrefillConsumed,
  onGoToPlans,
  onSignIn,
}: Props) {
  const { d, lang, t } = useLang();
  const [topic, setTopic] = useState('');
  const [message, setMessage] = useState('');
  const [linkedTender, setLinkedTender] = useState<Tender | null>(null);
  const [requests, setRequests] = useState<ConsultingRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const isPaid = user?.plan === 'Premium' || user?.plan === 'Pro';

  useEffect(() => {
    if (!prefillTender) return;
    setLinkedTender(prefillTender);
    setTopic((prev) =>
      prev === '' ? t('consultPrefillTopic', { id: prefillTender.tender_id }) : prev,
    );
    onPrefillConsumed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillTender]);

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .listMyConsulting()
      .then((res) => {
        if (!cancelled) setRequests(res);
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
        <h2 className="section-title">{d.consultTitle}</h2>
        <p className="section-intro">{d.consultSignInPrompt}</p>
        <button type="button" className="btn" onClick={onSignIn}>
          {d.signInJoin}
        </button>
      </div>
    );
  }

  if (loading) return <p>{d.loading}</p>;

  const send = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError('');
    setNotice('');
    try {
      await api.createConsulting({
        topic: topic.trim(),
        message: message.trim(),
        tender_id: linkedTender?.tender_id ?? null,
      });
      setTopic('');
      setMessage('');
      setLinkedTender(null);
      setRequests(await api.listMyConsulting());
      setNotice(d.consultSent);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.consultFailed);
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">{d.consultTitle}</h2>
        <p className="section-intro">{d.consultIntro}</p>
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
        {!isPaid ? (
          <div className="notice notice-warn">
            {d.consultPaidNote}{' '}
            <button type="button" className="link-btn" onClick={onGoToPlans}>
              {d.viewPlans}
            </button>
          </div>
        ) : (
          <form onSubmit={send}>
            {linkedTender && (
              <p className="field-note" style={{ marginBottom: '0.9rem' }}>
                {d.linkedTender}: {linkedTender.title ?? `${d.tenderWord} ${linkedTender.tender_id}`}{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => setLinkedTender(null)}
                >
                  {d.unlink}
                </button>
              </p>
            )}
            <div className="field">
              <label htmlFor="co-topic">{d.consultTopic}</label>
              <input
                id="co-topic"
                type="text"
                required
                minLength={3}
                maxLength={200}
                placeholder={d.consultTopicPh}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="co-message">{d.consultMessage}</label>
              <textarea
                id="co-message"
                required
                minLength={10}
                maxLength={3000}
                placeholder={d.consultMessagePh}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
            <button type="submit" className="btn" disabled={sending}>
              {d.consultSend}
            </button>
          </form>
        )}
      </section>

      <section>
        <h2 className="section-title">{d.consultMineTitle}</h2>
        {requests.length === 0 ? (
          <p className="field-note">{d.consultNone}</p>
        ) : (
          requests.map((req) => (
            <article className="card request-card" key={req.id}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h3>{req.topic}</h3>
                <span className={`badge ${req.status === 'Open' ? 'badge-open' : ''}`}>
                  {d.consultStatus[req.status] ?? req.status}
                </span>
              </div>
              <p className="field-note">
                {req.created_at ? fmtDateTime(req.created_at, lang) : ''}
                {req.tender_title ? ` · ${req.tender_title}` : ''}
              </p>
              <p style={{ whiteSpace: 'pre-wrap' }}>{req.message}</p>
              {req.reply && (
                <div className="reply-box">
                  <p className="reply-label">{d.consultReplyFrom}</p>
                  <p>{req.reply}</p>
                </div>
              )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
