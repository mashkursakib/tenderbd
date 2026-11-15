import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, api } from '../api';
import { fmtDateTime, fmtNum } from '../format';
import { useLang } from '../i18n';
import type { JvMessage, JvPost, Me, Tender } from '../types';

interface Props {
  user: Me | null;
  prefillTender: Tender | null;
  onPrefillConsumed: () => void;
  onOpenTender: (id: number) => void;
  onGoToPlans: () => void;
  onSignIn: () => void;
}

interface ActiveRoom {
  post: JvPost;
  roomId: number;
}

export default function JvRoom({
  user,
  prefillTender,
  onPrefillConsumed,
  onOpenTender,
  onGoToPlans,
  onSignIn,
}: Props) {
  const { d, lang, t } = useLang();
  const [posts, setPosts] = useState<JvPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [title, setTitle] = useState('');
  const [need, setNeed] = useState('');
  const [lookingFor, setLookingFor] = useState('');
  const [share, setShare] = useState('');
  const [linkedTender, setLinkedTender] = useState<Tender | null>(null);
  const [posting, setPosting] = useState(false);

  const [interestDrafts, setInterestDrafts] = useState<Record<number, string>>({});
  const [interestBusy, setInterestBusy] = useState<number | null>(null);

  const [activeRoom, setActiveRoom] = useState<ActiveRoom | null>(null);
  const [messages, setMessages] = useState<JvMessage[]>([]);
  const [roomLocked, setRoomLocked] = useState(false);
  const [roomLoading, setRoomLoading] = useState(false);
  const [roomBody, setRoomBody] = useState('');
  const [roomBusy, setRoomBusy] = useState(false);
  const [roomError, setRoomError] = useState('');

  const isPro = user?.plan === 'Pro';

  const loadPosts = async () => {
    try {
      setPosts(await api.listJvPosts());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.saveFailed);
    }
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listJvPosts()
      .then((res) => {
        if (!cancelled) setPosts(res);
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
  }, []);

  useEffect(() => {
    if (!prefillTender) return;
    setLinkedTender(prefillTender);
    setTitle((prev) =>
      prev === '' ? t('jvPrefillTitle', { id: prefillTender.tender_id }) : prev,
    );
    setNeed((prev) =>
      prev === ''
        ? t('jvPrefillNeed', {
            title: prefillTender.title ?? `${d.tenderWord} ${prefillTender.tender_id}`,
            ministry: prefillTender.ministry ?? '',
          })
        : prev,
    );
    onPrefillConsumed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillTender]);

  const postRequest = async (e: FormEvent) => {
    e.preventDefault();
    setPosting(true);
    setError('');
    setNotice('');
    try {
      await api.createJvPost({
        title: title.trim(),
        need_description: need.trim(),
        looking_for: lookingFor.trim() || undefined,
        share_offered: share.trim() || undefined,
        tender_id: linkedTender?.tender_id ?? null,
      });
      setTitle('');
      setNeed('');
      setLookingFor('');
      setShare('');
      setLinkedTender(null);
      await loadPosts();
      setNotice(d.postedMsg);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.couldNotPost);
    } finally {
      setPosting(false);
    }
  };

  const expressInterest = async (post: JvPost) => {
    const message = (interestDrafts[post.id] ?? '').trim();
    if (!message) return;
    setInterestBusy(post.id);
    setError('');
    setNotice('');
    try {
      await api.expressInterest(post.id, message);
      setInterestDrafts((prev) => ({ ...prev, [post.id]: '' }));
      await loadPosts();
      setNotice(d.interestSent);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.couldNotInterest);
    } finally {
      setInterestBusy(null);
    }
  };

  const loadRoom = async (roomId: number) => {
    setRoomLoading(true);
    setRoomError('');
    try {
      const res = await api.getRoomMessages(roomId);
      setRoomLocked(Boolean(res.locked));
      setMessages(res.messages ?? []);
    } catch (err) {
      setRoomError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setRoomLoading(false);
    }
  };

  const openRoom = async (post: JvPost) => {
    setError('');
    if (post.room_id) {
      setActiveRoom({ post, roomId: post.room_id });
      await loadRoom(post.room_id);
      return;
    }
    setRoomLoading(true);
    try {
      const room = await api.openRoom(post.id);
      setPosts((prev) =>
        prev.map((p) => (p.id === post.id ? { ...p, room_id: room.id } : p)),
      );
      setActiveRoom({ post: { ...post, room_id: room.id }, roomId: room.id });
      await loadRoom(room.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : d.couldNotRoom);
      setRoomLoading(false);
    }
  };

  const sendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeRoom || !roomBody.trim()) return;
    setRoomBusy(true);
    setRoomError('');
    try {
      const msg = await api.sendRoomMessage(activeRoom.roomId, roomBody.trim());
      setMessages((prev) => [...prev, msg]);
      setRoomBody('');
    } catch (err) {
      setRoomError(err instanceof ApiError ? err.message : d.saveFailed);
    } finally {
      setRoomBusy(false);
    }
  };

  if (loading) return <p>{d.loading}</p>;

  if (activeRoom) {
    const { post } = activeRoom;
    return (
      <div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ marginBottom: '1rem' }}
          onClick={() => {
            setActiveRoom(null);
            setMessages([]);
            setRoomLocked(false);
          }}
        >
          ← {d.openRequests}
        </button>
        <section className="card room-view">
          <h2 className="section-title">{t('roomTitle', { title: post.title })}</h2>
          {roomError && (
            <p className="notice notice-error" role="alert">
              {roomError}
            </p>
          )}
          {roomLoading ? (
            <p>{d.loading}</p>
          ) : roomLocked ? (
            <div className="notice notice-warn">
              {d.jvLockedNote}{' '}
              <button type="button" className="link-btn" onClick={onGoToPlans}>
                {d.upgradeToPro}
              </button>
            </div>
          ) : (
            <>
              {messages.length === 0 ? (
                <p className="field-note">{d.noMessages}</p>
              ) : (
                <div className="messages">
                  {messages.map((msg) => (
                    <div className="message" key={msg.id}>
                      <span className="sender">{msg.sender_name ?? ''}</span>
                      <span className="time">
                        {msg.created_at ? fmtDateTime(msg.created_at, lang) : ''}
                      </span>
                      <p>{msg.body}</p>
                    </div>
                  ))}
                </div>
              )}
              {user ? (
                <form className="send-row" onSubmit={sendMessage}>
                  <textarea
                    placeholder={d.writeToRoomPh}
                    aria-label={d.messageAria}
                    maxLength={2000}
                    value={roomBody}
                    onChange={(e) => setRoomBody(e.target.value)}
                  />
                  <button type="submit" className="btn" disabled={roomBusy || !roomBody.trim()}>
                    {d.send}
                  </button>
                </form>
              ) : (
                <p className="field-note">{d.signInToPostRoom}</p>
              )}
            </>
          )}
        </section>
      </div>
    );
  }

  return (
    <div>
      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">{d.jvPostTitle}</h2>
        <p className="section-intro">{d.jvIntro}</p>
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
        {!user ? (
          <>
            <p className="field-note">{d.jvSignInNote}</p>
            <button type="button" className="btn" onClick={onSignIn}>
              {d.signInJoin}
            </button>
          </>
        ) : !isPro ? (
          <div className="notice notice-warn">
            {d.jvProNote}{' '}
            <button type="button" className="link-btn" onClick={onGoToPlans}>
              {d.upgradeToPro}
            </button>
          </div>
        ) : (
          <form onSubmit={postRequest}>
            {linkedTender && (
              <div className="field">
                <span>
                  {d.linkedTender}:{' '}
                  {linkedTender.title ?? `${d.tenderWord} ${linkedTender.tender_id}`}{' '}
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => setLinkedTender(null)}
                  >
                    {d.unlink}
                  </button>
                </span>
              </div>
            )}
            <div className="field">
              <label htmlFor="jv-title">{d.postTitleLabel}</label>
              <input
                id="jv-title"
                type="text"
                required
                minLength={4}
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="jv-need">{d.needLabel}</label>
              <textarea
                id="jv-need"
                required
                minLength={4}
                maxLength={2000}
                value={need}
                onChange={(e) => setNeed(e.target.value)}
              />
            </div>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="jv-looking">{d.lookingForLabel}</label>
                <input
                  id="jv-looking"
                  type="text"
                  maxLength={500}
                  placeholder={d.lookingForPh}
                  value={lookingFor}
                  onChange={(e) => setLookingFor(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="jv-share">{d.shareLabel}</label>
                <input
                  id="jv-share"
                  type="text"
                  maxLength={200}
                  placeholder={d.sharePh}
                  value={share}
                  onChange={(e) => setShare(e.target.value)}
                />
              </div>
            </div>
            <button type="submit" className="btn" disabled={posting}>
              {d.postToRoom}
            </button>
          </form>
        )}
      </section>

      <section>
        <h2 className="section-title">{d.openRequests}</h2>
        {posts.length === 0 ? (
          <div className="empty-state">
            <p>{d.noRequests}</p>
          </div>
        ) : (
          posts.map((post) => {
            const posterBits: string[] = [];
            if (post.poster?.name) posterBits.push(post.poster.name);
            if (post.poster?.company_name) posterBits.push(post.poster.company_name);
            if (post.poster?.categories) posterBits.push(post.poster.categories);
            if (post.poster?.turnover !== null && post.poster?.turnover !== undefined) {
              posterBits.push(
                `${d.turnoverWord}: ${t('bdtPrice', { n: fmtNum(post.poster.turnover, lang) })}`,
              );
            }
            return (
              <article className="card jv-post" key={post.id}>
                <div className="jv-post-head">
                  <h3>{post.title}</h3>
                  <span className="chip">
                    {t('interested', { n: fmtNum(post.interest_count ?? 0, lang) })}
                  </span>
                </div>
                {posterBits.length > 0 && <p className="jv-poster">{posterBits.join(' · ')}</p>}
                {post.created_at && (
                  <p className="field-note">{fmtDateTime(post.created_at, lang)}</p>
                )}
                {(post.tender_id || post.tender_title) && (
                  <p>
                    {d.tenderWord}:{' '}
                    {post.tender_id ? (
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => onOpenTender(post.tender_id!)}
                      >
                        {post.tender_title ?? `${d.tenderWord} ${post.tender_id}`}
                      </button>
                    ) : (
                      post.tender_title
                    )}
                  </p>
                )}
                <p style={{ whiteSpace: 'pre-wrap' }}>{post.need_description}</p>
                {post.looking_for && (
                  <p>
                    {d.lookingForPrefix} {post.looking_for}
                  </p>
                )}
                {post.share_offered && (
                  <p>
                    {d.shareOfferedPrefix} {post.share_offered}
                  </p>
                )}

                {isPro && (
                  <div className="jv-interest-row">
                    <textarea
                      placeholder={d.introPh}
                      aria-label={t('interestAria', { title: post.title })}
                      maxLength={1000}
                      value={interestDrafts[post.id] ?? ''}
                      onChange={(e) =>
                        setInterestDrafts((prev) => ({ ...prev, [post.id]: e.target.value }))
                      }
                    />
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={interestBusy === post.id || !(interestDrafts[post.id] ?? '').trim()}
                      onClick={() => void expressInterest(post)}
                    >
                      {d.expressInterest}
                    </button>
                  </div>
                )}
                {user && !isPro && <p className="field-note">{d.jvProNoteShort}</p>}

                <div className="row" style={{ marginTop: '0.8rem' }}>
                  {post.room_id ? (
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openRoom(post)}>
                      {d.readRoom}
                    </button>
                  ) : isPro ? (
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openRoom(post)}>
                      {d.openARoom}
                    </button>
                  ) : (
                    <span className="field-note">{d.noRoomYet}</span>
                  )}
                </div>
              </article>
            );
          })
        )}
      </section>
    </div>
  );
}
