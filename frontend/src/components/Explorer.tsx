import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ApiError, api, type TenderQuery } from '../api';
import { compactBdt, daysUntil, fmtDate, fmtNum } from '../format';
import { useLang } from '../i18n';
import type {
  BidStage,
  Favourite,
  Me,
  Tender,
  TenderListResponse,
} from '../types';

export const WORK_TYPES = ['Works', 'Goods', 'Services', 'Consultancy'];
export const DEPARTMENTS = ['LGED', 'RHD', 'BWDB', 'PWD', 'BREB'];
export const STAGES: BidStage[] = [
  'Watching',
  'Shortlisted',
  'Preparing',
  'Submitted',
  'Won',
  'Lost',
];
const LIMIT = 60;

interface Filters {
  workTypes: string[];
  departments: string[];
  division: string;
  district: string;
  valueMin: string;
  valueMax: string;
  statuses: string[];
  method: string;
}

const DEFAULT_FILTERS: Filters = {
  workTypes: [],
  departments: [],
  division: '',
  district: '',
  valueMin: '',
  valueMax: '',
  statuses: ['active'],
  method: '',
};

interface Props {
  user: Me | null;
  onOpenTender: (id: number) => void;
  onRefreshStats: () => void;
  onGoToPlans: () => void;
}

export function TenderCard({
  tender,
  onOpen,
}: {
  tender: Tender;
  onOpen: (id: number) => void;
}) {
  const { d, lang, t } = useLang();
  const days = daysUntil(tender.close_dt);
  const bucket = tender.status_bucket ?? 'active';
  const division = tender.computed_division ?? tender.division ?? null;

  let deadline: string | null = null;
  if (tender.close_dt) {
    const date = fmtDate(tender.close_dt, lang);
    if (bucket === 'closed' || (days !== null && days < 0)) {
      deadline = `${d.deadline}: ${date} · ${d.closedWord}`;
    } else if (days === 0) {
      deadline = `${d.deadline}: ${date} · ${d.closesToday}`;
    } else if (days !== null) {
      deadline = `${d.deadline}: ${date} · ${t('daysLeft', { n: fmtNum(days, lang) })}`;
    }
  }

  const metaParts: string[] = [`${d.idShort} ${tender.tender_id}`];
  if (tender.ref_no) metaParts.push(`${d.refShort} ${tender.ref_no}`);
  if (tender.ministry) metaParts.push(tender.ministry);
  if (tender.document_price_bdt !== null && tender.document_price_bdt !== undefined) {
    metaParts.push(
      `${d.docPriceShort} ${t('bdtPrice', { n: fmtNum(tender.document_price_bdt, lang) })}`,
    );
  }

  const workTypeLabel =
    tender.work_type && tender.work_type in d.workTypes
      ? d.workTypes[tender.work_type as keyof typeof d.workTypes]
      : tender.work_type;

  return (
    <article className="tender-card">
      <div className="tender-card-top">
        <button
          type="button"
          className="card-title"
          onClick={() => onOpen(tender.tender_id)}
          aria-label={t('openTenderAria', { id: tender.tender_id })}
        >
          {tender.title || `${d.tenderWord} ${tender.tender_id}`}
        </button>
        {tender.emd_bdt !== null && tender.emd_bdt !== undefined ? (
          <span className="value-badge">
            {t('bdtPrice', { n: compactBdt(tender.emd_bdt, lang) })} {d.tenderSecurity}
          </span>
        ) : (
          <span className="value-badge muted">{d.securityNotPublished}</span>
        )}
      </div>
      <div className="chip-row">
        {workTypeLabel && <span className="chip">{workTypeLabel}</span>}
        {tender.district && <span className="chip">{tender.district}</span>}
        {division && division !== tender.district && (
          <span className="chip">{division}</span>
        )}
        {(tender.departments ?? []).map((dept) => (
          <span className="chip" key={dept}>
            {dept}
          </span>
        ))}
        {tender.method && <span className="chip">{tender.method}</span>}
        {bucket === 'closing_soon' && (
          <span className="chip chip-urgent">{d.urgent}</span>
        )}
        <span className={`chip ${bucket === 'closed' ? 'chip-closed' : 'chip-active'}`}>
          {bucket === 'closed'
            ? d.statusClosed
            : bucket === 'closing_soon'
              ? d.statusClosingSoon
              : d.statusActive}
        </span>
      </div>
      {deadline && <p className="deadline-line">{deadline}</p>}
      <p className="tender-meta">{metaParts.join(' · ')}</p>
    </article>
  );
}

export default function Explorer({ user, onOpenTender, onRefreshStats, onGoToPlans }: Props) {
  const { d, lang, t } = useLang();
  const [applied, setApplied] = useState<Filters>(DEFAULT_FILTERS);
  const [draft, setDraft] = useState<Filters>(DEFAULT_FILTERS);
  const [query, setQuery] = useState('');
  const [queryDraft, setQueryDraft] = useState('');
  const [sort, setSort] = useState('closing');
  const [data, setData] = useState<TenderListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState('');
  const [favourites, setFavourites] = useState<Favourite[]>([]);
  const [stageError, setStageError] = useState('');

  const fetchTenders = useCallback(
    async (filters: Filters, q: string, sortValue: string) => {
      setLoading(true);
      setError('');
      const params: TenderQuery = {
        q: q || undefined,
        work_types: filters.workTypes.length ? filters.workTypes : undefined,
        departments: filters.departments.length ? filters.departments : undefined,
        division: filters.division || undefined,
        district: filters.district || undefined,
        value_min: filters.valueMin ? Number(filters.valueMin) : undefined,
        value_max: filters.valueMax ? Number(filters.valueMax) : undefined,
        statuses: filters.statuses.length ? filters.statuses : undefined,
        method: filters.method || undefined,
        sort: sortValue,
        limit: LIMIT,
      };
      try {
        setData(await api.listTenders(params));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : d.loadTendersError);
      } finally {
        setLoading(false);
      }
    },
    [d.loadTendersError],
  );

  useEffect(() => {
    void fetchTenders(applied, query, sort);
  }, [applied, query, sort, fetchTenders]);

  useEffect(() => {
    if (!user) {
      setFavourites([]);
      return;
    }
    let cancelled = false;
    api
      .listFavourites()
      .then((res) => {
        if (!cancelled) setFavourites(res.favourites);
      })
      .catch(() => {
        // Pipeline is secondary; the explorer works without it.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const toggleIn = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const applyDraft = () => setApplied(draft);

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    setQuery(queryDraft);
    setApplied(draft);
  };

  const clearAll = () => {
    setDraft(DEFAULT_FILTERS);
    setApplied(DEFAULT_FILTERS);
    setQuery('');
    setQueryDraft('');
  };

  const doRefresh = async () => {
    setRefreshing(true);
    setRefreshError('');
    try {
      await api.refresh({ days: 3, max_pages: 5, enrich_limit: 12 });
      await fetchTenders(applied, query, sort);
      onRefreshStats();
    } catch (err) {
      setRefreshError(
        err instanceof ApiError ? `${d.refreshFailed} ${err.message}` : d.refreshFailed,
      );
    } finally {
      setRefreshing(false);
    }
  };

  const setStage = async (tenderId: number, stage: BidStage) => {
    setStageError('');
    try {
      await api.setStage(tenderId, stage);
      setFavourites((prev) =>
        prev.map((f) => (f.tender_id === tenderId ? { ...f, stage } : f)),
      );
    } catch (err) {
      setStageError(err instanceof ApiError ? err.message : d.saveFailed);
    }
  };

  const isPro = user?.plan === 'Pro';
  const tenders = data?.tenders ?? [];

  return (
    <div>
      <div className="explorer">
        <aside className="sidebar" aria-label={d.filterTenders}>
          <div className="sidebar-head">
            <h2>{d.filterTenders}</h2>
            <button type="button" className="link-btn" onClick={clearAll}>
              {d.clearAll}
            </button>
          </div>

          <div className="filter-group">
            <h3>{d.workType}</h3>
            {WORK_TYPES.map((wt) => (
              <label className="check-row" key={wt}>
                <input
                  type="checkbox"
                  checked={draft.workTypes.includes(wt)}
                  onChange={() =>
                    setDraft({ ...draft, workTypes: toggleIn(draft.workTypes, wt) })
                  }
                />
                {d.workTypes[wt as keyof typeof d.workTypes]}
                <span className="count">
                  {fmtNum(data?.work_type_counts?.[wt] ?? 0, lang)}
                </span>
              </label>
            ))}
          </div>

          <div className="filter-group">
            <h3>{d.location}</h3>
            <div className="field">
              <select
                value={draft.division}
                onChange={(e) => setDraft({ ...draft, division: e.target.value })}
                aria-label={d.division}
              >
                <option value="">{d.allDivisions}</option>
                {(data?.divisions ?? []).map((div) => (
                  <option key={div} value={div}>
                    {div}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <select
                value={draft.district}
                onChange={(e) => setDraft({ ...draft, district: e.target.value })}
                aria-label={d.district}
              >
                <option value="">{d.allDistricts}</option>
                {(data?.districts ?? []).map((dist) => (
                  <option key={dist} value={dist}>
                    {dist}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <select disabled aria-label={d.allUpazilas}>
                <option>{d.allUpazilas}</option>
              </select>
              <p className="field-note">{d.upazilaNote}</p>
            </div>
          </div>

          <div className="filter-group">
            <h3>{d.tenderValue}</h3>
            <div className="minmax">
              <div className="field">
                <label htmlFor="value-min">{d.min}</label>
                <input
                  id="value-min"
                  type="number"
                  min={0}
                  value={draft.valueMin}
                  onChange={(e) => setDraft({ ...draft, valueMin: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="value-max">{d.max}</label>
                <input
                  id="value-max"
                  type="number"
                  min={0}
                  value={draft.valueMax}
                  onChange={(e) => setDraft({ ...draft, valueMax: e.target.value })}
                />
              </div>
            </div>
            <p className="field-note">{d.valueNote}</p>
          </div>

          <div className="filter-group">
            <h3>{d.department}</h3>
            {DEPARTMENTS.map((dept) => (
              <label className="check-row" key={dept}>
                <input
                  type="checkbox"
                  checked={draft.departments.includes(dept)}
                  onChange={() =>
                    setDraft({ ...draft, departments: toggleIn(draft.departments, dept) })
                  }
                />
                {dept}
                <span className="count">
                  {fmtNum(data?.department_counts?.[dept] ?? 0, lang)}
                </span>
              </label>
            ))}
          </div>

          <div className="filter-group">
            <h3>{d.statusLabel}</h3>
            {(
              [
                ['active', d.statusActive],
                ['closing_soon', d.statusClosingSoon],
                ['closed', d.statusClosed],
              ] as const
            ).map(([value, label]) => (
              <label className="check-row" key={value}>
                <input
                  type="checkbox"
                  checked={draft.statuses.includes(value)}
                  onChange={() =>
                    setDraft({ ...draft, statuses: toggleIn(draft.statuses, value) })
                  }
                />
                {label}
              </label>
            ))}
          </div>

          <div className="filter-group">
            <h3>{d.procMethod}</h3>
            <div className="field">
              <select
                value={draft.method}
                onChange={(e) => setDraft({ ...draft, method: e.target.value })}
                aria-label={d.procMethod}
              >
                <option value="">{d.anyMethod}</option>
                {(data?.methods ?? []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button type="button" className="btn" style={{ width: '100%' }} onClick={applyDraft}>
            {d.applyFilters}
          </button>
        </aside>

        <section>
          <form className="results-head" onSubmit={submitSearch}>
            <input
              className="search-input"
              type="search"
              placeholder={d.searchPlaceholder}
              value={queryDraft}
              onChange={(e) => setQueryDraft(e.target.value)}
              aria-label={d.searchPlaceholder}
            />
            <button type="submit" className="btn">
              {d.searchBtn}
            </button>
            {user?.is_admin && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={doRefresh}
                disabled={refreshing}
              >
                {refreshing ? d.refreshing : d.refresh}
              </button>
            )}
          </form>

          <div className="results-meta">
            <span>
              {fmtNum(data?.total ?? 0, lang)}
              {d.tendersFound}
            </span>
            <label className="sort-row">
              {d.sortBy}
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="closing">{d.sortClosing}</option>
                <option value="published">{d.sortPublished}</option>
                <option value="newest_id">{d.sortNewestId}</option>
                <option value="value_high">{d.sortValueHigh}</option>
                <option value="value_low">{d.sortValueLow}</option>
              </select>
            </label>
          </div>

          <p className="field-note" style={{ marginBottom: '0.9rem' }}>
            {d.sourceNote}
          </p>

          {refreshError && (
            <p className="notice notice-error" role="alert">
              {refreshError}
            </p>
          )}
          {error && (
            <div className="notice notice-error" role="alert">
              {error}{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => void fetchTenders(applied, query, sort)}
              >
                {d.authTryAgain}
              </button>
            </div>
          )}

          {loading ? (
            <p>{d.loadingTenders}</p>
          ) : error ? null : tenders.length === 0 ? (
            <div className="empty-state">
              <p>{d.emptyTenders}</p>
              <div className="row">
                <button type="button" className="btn btn-ghost" onClick={clearAll}>
                  {d.clearAllFilters}
                </button>
                {user?.is_admin && (
                  <button
                    type="button"
                    className="btn"
                    onClick={doRefresh}
                    disabled={refreshing}
                  >
                    {refreshing ? d.refreshing : d.refresh}
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="tender-list">
              {tenders.map((tender) => (
                <TenderCard key={tender.tender_id} tender={tender} onOpen={onOpenTender} />
              ))}
            </div>
          )}
        </section>
      </div>

      {user && favourites.length > 0 && (
        <section className="pipeline">
          <h2 className="section-title">{d.pipelineTitle}</h2>
          <p className="section-intro">{d.pipelineIntro}</p>
          {!isPro && (
            <p className="notice notice-warn">
              {d.pipelineProNote}{' '}
              <button type="button" className="link-btn" onClick={onGoToPlans}>
                {d.upgradeToPro}
              </button>
            </p>
          )}
          {stageError && (
            <p className="notice notice-error" role="alert">
              {stageError}
            </p>
          )}
          <div className="pipeline-list">
            {favourites.map((fav) => (
              <div className="card pipeline-row" key={fav.tender_id}>
                <button
                  type="button"
                  className="tender-link"
                  onClick={() => onOpenTender(fav.tender_id)}
                >
                  {fav.tender?.title || `${d.tenderWord} ${fav.tender_id}`}
                </button>
                {isPro ? (
                  <label className="sort-row">
                    {d.bidStage}
                    <select
                      value={fav.stage}
                      aria-label={t('bidStageAria', { id: fav.tender_id })}
                      onChange={(e) => void setStage(fav.tender_id, e.target.value as BidStage)}
                    >
                      {STAGES.map((stage) => (
                        <option key={stage} value={stage}>
                          {d.stages[stage]}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <span className="stage-text">
                    {d.bidStage}: {d.stages[fav.stage] ?? fav.stage}
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
