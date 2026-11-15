# TenderBD Production — Porting Spec

Source of truth: the Muse prototype artifact `tenderbd-platform`
(inspection 7d0c913e, 2026-11-15) plus the action schemas captured from
it. Port it faithfully. Do not redesign, do not rename features, do not
invent copy, prices, testimonials, or data e-GP does not publish.

Live site: https://tender.masconsultancy.org (Render + DNS on
Spaceship, done by the parent agent from the coordinator handoff).

## 0. Global rules (apply to every file)

- Never use em dashes (U+2014) in any user-facing writing. If a
  prototype string contains one, rewrite it with a comma, colon, or
  full stop. (Code comments and identifiers are unaffected, but
  avoid them there too.)
- Eligibility scores are ESTIMATES, labelled as such everywhere
  they appear.
- The value filter and card badge use tender security (EMD) because
  e-GP publishes no estimated contract value. Label it as EMD /
  tender security, never as contract value.
- No BOQ, winning-range, awarded-contract analysis, or any feature
  needing data e-GP does not publish.
- No bidder login anywhere. The scraper reads public e-GP pages
  only (see tenderbd_scraper/README.md in the scraper repo).
- All free tiers only. No paid service signups.

## 1. Repo layout and file ownership

```
tenderbd-production/
  SPEC.md                  (this file; coordinator owns)
  README.md                (infra)
  render.yaml              (infra)
  Dockerfile               (infra)
  .env.example             (infra)
  .gitignore, .dockerignore (infra)
  docker-compose.yml       (infra, local dev)
  requirements.txt         (infra; merges backend + scraper deps)
  .github/workflows/
    scrape.yml             (data; scheduled scraper runs)
    ci.yml                 (infra; pytest on push)
  tenderbd_scraper/        (data; extend, do not rewrite)
  tests-scraper/           (data; keep passing)
  schema/
    schema_app.sql         (backend; Postgres app tables)
    schema_app_sqlite.sql  (backend; SQLite variant for tests)
  backend/
    app/                   (backend; FastAPI application)
    tests/                 (backend; pytest)
    requirements.txt       (backend; its own deps, infra merges)
  frontend/
    (Vite + React + TypeScript SPA; frontend owns all of it)
  scripts/
    smoke_e2e.py           (coordinator; end-to-end check)
```

Rules: each area edits ONLY its own files. Backend may import from
`tendernet_scraper` (read-only use of `Store`, `fetcher`,
`config`). Frontend talks to the backend only through the API in
section 4. If two areas need the same thing changed, the coordinator
decides; do not edit another area's files.

## 2. Stack

- Backend: Python 3.12, FastAPI + Uvicorn, psycopg 3 (dict rows),
  argon2-cffi (argon2id), python-multipart (uploads), httpx
  (Resend API calls + tests), pytest. No ORM; plain SQL following
  the scraper's `Store` pattern (`%(name)s` placeholders, translated
  for SQLite in tests).
- Database: PostgreSQL in production (Supabase free tier), SQLite
  for local dev/tests. Tenders table = the scraper schema verbatim
  (`tenderbd_scraper/schema.sql`); app tables in `schema/`.
- Frontend: React 18 + Vite + TypeScript, no UI framework beyond
  plain CSS (theme tokens in section 9). The FastAPI app serves the
  built SPA statically from `frontend/dist` and the API under
  `/api/v1/`. One Render web service.
- Documents: file bytes stored as BYTEA in Postgres (Render's disk
  is ephemeral; this avoids a second service). 6 MB/file cap.

## 3. Data model

Tenders + fetch_runs: exactly `tenderbd_scraper/schema.sql`
(tender_id BIGINT PK, all notice fields, detail_fetched_at).

App tables (Postgres; TIMESTAMPTZ for timestamps; serial PKs
unless noted). Names and defaults mirror the prototype:

- users(id, email UNIQUE NOT NULL lowercase, password_hash NOT
  NULL, name NOT NULL, session_token nullable, session_expires_at
  nullable, reset_token nullable, reset_expires_at nullable,
  is_admin BOOLEAN default false, created_at)
- sign_in_attempts(email PK, fail_count default 0,
  window_started_at NOT NULL, locked_until nullable)
- subscriptions(user_id PK, plan default 'Free', payment_method,
  status default 'Active', updated_at)
- companies(id, user_id UNIQUE NOT NULL, company_name NOT NULL,
  trade_license_no, tin_no, incorporation_year int,
  annual_turnover_bdt bigint, liquid_assets_bdt bigint,
  categories text comma-separated, districts text,
  similar_works JSONB array of {title, value_bdt, category} max 30,
  key_personnel, equipment, about, updated_at)
- documents(id, user_id, doc_type, file_name, mime_type,
  size_bytes, data BYTEA, status default 'Declared', uploaded_at)
- favourites(id, user_id, tender_id, stage default
  'Shortlisted', created_at; UNIQUE(user_id, tender_id))
- alert_prefs(user_id PK, keywords, categories, districts,
  organisations, updated_at)
- jv_posts(id, user_id, tender_id nullable, tender_title nullable
  snapshot, title, need_description, looking_for, share_offered,
  status default 'Open', created_at)
- jv_interests(id, post_id, user_id, message, created_at)
- jv_rooms(id, post_id UNIQUE, title snapshot, created_at)
- jv_messages(id, room_id, user_id, sender_name snapshot, body,
  created_at)
- payment_submissions(id, user_id, plan, method, transaction_id,
  sender_number, amount_bdt, status default 'Pending',
  submitted_at, reviewed_at, review_note)
- consulting_requests(id, user_id, tender_id nullable,
  tender_title nullable, topic, message, status default 'Open',
  reply, replied_at, created_at)

No foreign keys are required (prototype had none); indexes on
user_id columns and tender_id where listed.

## 4. API contract

Base: `/api/v1/`. JSON everywhere. Auth: `Authorization: Bearer
<token>` (48-hex session token). Errors: FastAPI default
`{"detail": "..."}` with the prototype's exact message strings
where given below. Validation limits mirror the artifact action
schemas (same min/max lengths).

Public (no auth):
- GET  /health -> {"status":"ok","db":"postgres"|"sqlite"}
- GET  /stats -> {"total":n,"open_now":n,"last_run":{...}|null}
- GET  /tenders?q=&work_types[]=...&departments[]=...&division=
  &district=&value_min=&value_max=&statuses[]=...&method=&sort=
  &limit=50&offset=0 -> {"tenders":[...],"total":n,
  "work_type_counts":{...},"department_counts":{...},
  "districts":[...],"divisions":[...],"methods":[...]}
  - sort: closing (default), published, newest_id, value_high,
    value_low. statuses: active, closing_soon, closed.
    work_types: Works, Goods, Services, Consultancy.
- GET  /tenders/{tender_id} -> full tender; enriches from the
  public e-GP notice page on first open (detail_fetched_at null).
- POST /refresh (authorized two ways: header X-Refresh-Token must
  equal REFRESH_TOKEN env, for scheduled jobs; or a signed-in admin
  session Bearer token, for the Refresh button in the UI, which
  cannot carry the shared token; body {days=3, max_pages=5,
  enrich_limit=12}) -> run summary. Runs the scraper
  synchronously with the prototype's caps. The Refresh button is
  shown only to admin users; the scheduled job is the primary
  refresh path.

Auth:
- POST /auth/signup {name 2-120, email, password 8-72}
  -> {user:{id,name,email,plan,is_admin}, token}
  Duplicate email: 400 "An account with this email already exists.
  Sign in instead." New signups start Free/Active. Admin emails
  (ADMIN_EMAILS env, comma-separated, default the three MAS
  addresses) get is_admin=true.
- POST /auth/signin {email, password} -> {user, token}
  Wrong credentials (including unknown email): 401 "Email or
  password is incorrect. Check both and try again."
  Locked out: 429 "Too many failed sign-in attempts. Try again in
  a few minutes."
- POST /auth/signout (auth) -> {} (invalidates token server-side)
- GET  /auth/me (auth) -> {id,name,email,plan,is_admin,
  has_profile, pending_payment_plan}
- POST /auth/request-password-reset {email} -> always {"message":
  "If an account exists for that email, a reset link has been
  sent."} (never reveals existence). Sends a reset email via
  Resend when RESEND_API_KEY is set; token TTL 1 hour. The token
  is NEVER returned in the response.
- POST /auth/reset-password {email, reset_token, new_password 8-72}
  -> {user, token}. Bad/expired: 400 "That reset code is invalid
  or has expired. Request a new one."

Tenders (signed-in features):
- POST /tenders/{id}/evaluate (auth, Premium+) ->
  {has_profile, score|null, verdict|null, checks:[{key, status,
  points, max_points, detail}], note}. See section 7.
- POST /tenders/{id}/summarize (auth, Premium+) {lang:"en"|"bn"}
  -> {headline, scope, eligibility_points[], key_requirements[],
  watch_outs[]}. See section 8.

Profile / vault / favourites / alerts:
- GET  /profile/company (auth) -> company profile or null
- PUT  /profile/company (auth) {company_name required, plus all
  saveCompanyProfile fields} -> saved profile. NOT plan-gated.
- GET  /documents (auth) -> [{id,doc_type,file_name,mime_type,
  size_bytes,status,uploaded_at}] (NOT plan-gated for reads)
- POST /documents (auth, Premium+) multipart file + doc_type ->
  created document. 6 MB cap: 400 over cap. doc_type values:
  Trade licence, TIN / VAT certificate, Certificate of
  incorporation, Audited financial statements, Bank solvency /
  credit line letter, Work completion certificate, Key personnel
  CVs, Equipment list, Other.
- GET  /documents/{id}/download (auth, owner only) -> file bytes
- DELETE /documents/{id} (auth, owner only) -> {} (NOT gated)
- GET  /favourites (auth) -> {favourites:[{tender_id, stage,
  tender:{...}}], favourite_ids:[...]}
- POST /favourites/{tender_id}/toggle (auth) -> {favourite:bool}
  Free plan cap 3: 403 "The Free plan keeps 3 favourites.
  Upgrade to Premium for unlimited favourites."
- PATCH /favourites/{tender_id}/stage (auth, Pro) {stage} ->
  updated favourite. Stages: Watching, Shortlisted, Preparing,
  Submitted, Won, Lost.
- GET  /alerts (auth) -> {prefs, matches:[...]} (read NOT gated)
- PUT  /alerts (auth, Premium+) {keywords, categories, districts,
  organisations} -> saved prefs. Matching: AND across filled
  groups, substring, max 30 matches from the 300 soonest-closing
  stored tenders.

JV room:
- GET  /jv/posts (public) -> newest 100 posts with poster
  {name, company_name, categories, turnover}, interest_count,
  room_id (or null).
- POST /jv/posts (auth, Pro) {title 4-200, need_description
  4-2000, looking_for<=500, share_offered<=200, tender_id?}
  -> created post (tender_title snapshotted).
- POST /jv/posts/{id}/interest (auth, Pro) {message 2-1000} ->
  {}. Own post: 400 "This is your own post." No duplicate check
  (preserve prototype behavior). Interests are counted only;
  there is NO endpoint listing who expressed interest.
- POST /jv/posts/{id}/room (auth, Pro) -> room (one room per
  post; returns the existing one). No membership check (preserve
  prototype behavior).
- GET  /jv/rooms/{id}/messages (auth, Pro) -> {messages:[...]}
  oldest first, limit 200. Non-Pro or unsigned: 200
  {locked:true, messages:[]}.
- POST /jv/rooms/{id}/messages (auth, Pro) {body 1-2000} ->
  created message (sender_name = account name snapshot).

Payments / consulting:
- GET  /payments/mine (auth) -> own last 20 submissions with
  status/review_note.
- POST /payments (auth) {plan: Premium|Pro, method: bKash|Nagad,
  transaction_id 4-60, sender_number?} -> created submission
  (amount_bdt from plan prices, status Pending). Already at or
  above that plan: 400 "You are already on the <plan> plan."
  Pending submission exists: 400 "You already have a payment
  waiting for verification..."
- GET  /consulting/mine (auth) -> own requests with replies.
- POST /consulting (auth, Premium+) {topic 3-200, message 10-3000,
  tender_id?} -> created request.

Admin (is_admin only; others get 403 "Admin access only."):
- GET  /admin/overview -> {totals:{users, premium, pro,
  pending_payments, open_consulting, tenders}, users:[...newest
  first with company, plan, is_admin, signed_up_at, counts
  {favourites, documents, jv_posts, consulting_requests},
  has_alert_prefs], payments:[last 100], consulting:[last 100]}
- POST /admin/payments/{id}/review {approve:bool, note<=500} ->
  updated submission. Non-pending: 400 "That payment was already
  reviewed." On approve: upsert subscription {plan,
  payment_method, status Active}.
- POST /admin/consulting/{id}/reply {reply 2-4000} -> updated
  request (status Answered, replied_at set).
- POST /admin/users/{id}/plan {plan: Free|Premium|Pro} ->
  updated subscription (payment_method "Admin").

Plan-gate error (403): "This is a <min> feature. Your current
plan is <plan>. Upgrade from the Plans tab to unlock it."
PLAN_RANK: Free 0, Premium 1, Pro 2.

## 5. Auth rules

- Email + password only. Passwords: argon2id (argon2-cffi),
  8-72 chars. Email lowercased, unique.
- Sessions: 48-hex-char token (24 random bytes), TTL 30 days,
  stored on the user row (one session per user; a new sign-in
  invalidates the previous token). Expired tokens are cleared
  server-side on use.
- Rate limiting: per lowercase email; 5 failures within a 15-min
  window locks the email for 15 min. Failures (including unknown
  email) return the generic 401 message. Success clears attempts.
- Password reset: token TTL 1 hour; reset requires matching
  unexpired token; on success clears reset fields + sign-in
  attempts and signs in with a fresh 30-day session.

## 6. Plan gates (server-side)

- Premium+ (Premium and Pro): evaluate, summarize, upload
  document, save alert prefs, request consulting.
- Pro only: create JV post, express JV interest, open JV room,
  list/send JV messages, set bid stage.
- Free: browse/search, tender detail, JV browsing, company
  profile save, document list/download/delete, favourites reads,
  alert reads, consulting/payment reads; favourites capped at 3.
- Prices: Premium BDT 399/month, Pro BDT 799/month.
- No subscription expiry, billing period, or renewal logic.
  Plans change only via admin payment approval or admin set-plan.

## 7. Eligibility scoring (Premium+; server-side)

No profile -> {has_profile:false, score:null, verdict:null}.
Estimated contract value = EMD x 40 (EMD assumed ~2.5% of value;
labelled estimate). Four checks, max 100 points:

(a) Category match, 30 pts: no nature stated -> unknown 15; no
    profile categories -> unknown 0; substring match either way
    between profile categories and tender proc_nature -> pass 30;
    else fail 0.
(b) Turnover vs tender scale, 25 pts: EMD unknown -> unknown 12;
    turnover null -> unknown 0; turnover >= estimate -> pass 25;
    >= 50% of estimate -> partial 12; else fail 0.
(c) Liquidity for tender security, 20 pts: EMD unknown -> unknown
    10; liquid null -> unknown 0; liquid >= EMD -> pass 20; else
    fail 0.
(d) Similar work experience, 25 pts: no works -> unknown 0; with
    EMD: largest category-relevant work >= 50% of estimate ->
    pass 25; relevant works exist but smaller -> partial 12; no
    relevant work -> fail 0; without EMD but works exist ->
    partial 12.
    Relevance: category substring match vs nature (empty category
    counts as relevant).

Verdicts: score >= 70 "Eligible"; 40-69 "Eligible with a JV
partner"; below 40 "Not yet eligible". Check statuses:
pass/partial/fail/unknown, with per-check detail strings in
ENGLISH ONLY (even when the UI is Bangla).
Fixed note (include verbatim): "Estimate from the public notice
fields plus your declared profile. Full eligibility criteria live
inside the tender document on e-GP, which needs a bidder login,
check the official notice before bidding."

## 8. AI notice summary (Premium+)

DECISION (coordinator, 2026-11-15): extractive summary, no LLM.
The prototype used the host's unnamed inference; production has
no LLM key, and no new paid/free-tier account is to be created.
Build a deterministic extractive summarizer over the notice text
only (title, ministry, procuring entity, district,
nature/method, dates, document price, EMD, description sliced to
4000 chars, eligibility text sliced to 4000 chars). Output shape
matches the prototype: {headline, scope, eligibility_points[],
key_requirements[], watch_outs[]}. Rules: use ONLY facts in the
notice text; never invent figures, dates, or requirements.
Language: lang "en" -> full English; lang "bn" -> Bangla section
labels with facts (names, IDs, figures) as printed. Guards:
unsigned -> Premium plan error; description + eligibility text
under 80 chars -> 400 "This notice publishes too little text on
the public page to summarize." Tender is enriched from e-GP
first. Summaries are NOT stored; generated per request.

## 9. Theme and i18n (frontend)

- Deep ash gray like Moshnod. Fonts: Nunito (display) + Nunito
  Sans (body) via Google Fonts, weights 400/600/700/800.
  Radius 20px; soft shadows; pill buttons; charcoal accent
  buttons; min control height 2.75rem.
- LIGHT (default): --bg/#surface #ffffff, --text #222528,
  --dim #6e7379, --border #dfe1e4, --accent #34383d,
  --accent-hover #232629, --accent-soft #ebebed,
  --accent-text #fff, --masthead-bg #232629,
  --masthead-surface #2f3337, --masthead-text #f4f4f5,
  --masthead-dim #b7bbc0, --masthead-warn #e2c07c,
  --footer-bg #1d1f22, --footer-text #caccce,
  --footer-dim #969ca2, --danger #b25952,
  --danger-soft #f8edec, --warn #9c7c34, --warn-soft #f6f0dd,
  --space-surface-alt #f0f0f1.
- DARK: --bg #101112, --surface #1b1d1f, --text #eceeef,
  --dim #9fa5ab, --border #2f3337, --accent #d6d9dc,
  --accent-hover #e8eaec, --accent-soft #26292c,
  --accent-text #17191b, masthead/footer #0a0b0c,
  --danger #d99a94/soft #382a28, --warn #d3ba7c/soft #352f1e,
  --space-surface-alt #222426.
- Theme switch Device/White/Black in the nav; DEFAULT IS WHITE.
  Persist in localStorage 'tenderbd_theme' ('light'|'dark'|
  'device', anything else -> 'light'); apply via
  documentElement.dataset.theme with a pre-paint script so the
  first paint is already themed; 'device' follows
  prefers-color-scheme.
- Language: EN default, toggle EN/বাংলা in the masthead,
  persisted in localStorage 'tenderbd_lang'. Dates/numbers use
  locale bn-BD when Bangla, en-GB otherwise. Tender DATA (titles,
  ministries, districts, notice text) always stays as published
  by e-GP in English; eligibility check details stay English.
  Bangla tab labels: টেন্ডার / আমার সক্ষমতা / জেভি রুম /
  অ্যালার্ট / পরামর্শ / প্ল্যান / অ্যাডমিন; theme labels
  ডিভাইস/সাদা/কালো. The full en+bn dictionaries will be
  delivered to the frontend agent as a follow-up (verbatim from
  the prototype); build the i18n module so the dictionaries drop
  in without restructuring.
- localStorage keys: tenderbd_token, tenderbd_theme,
  tenderbd_lang.

## 10. Explorer behaviour (frontend + backend agree)

- Layout: single page, max-w-5xl; dark masthead header with
  title, tagline, stats chips; auth panel under the header;
  sticky tab nav (Tenders, My capability, JV room, Alerts,
  Consulting, Plans, Admin when is_admin); dark footer with
  BPPA/e-GP attribution + eligibility disclaimer.
- Tenders tab: 300px filter sidebar + results, limit 60.
  Sidebar: Work type checkboxes with counts; Location
  (division/district dropdowns from stored data; upazila dropdown
  DISABLED with the note "e-GP notices publish the district
  only, so upazila filtering is not available."); Tender value
  (BDT) Min/Max with the note "Filtered on the tender security
  (EMD), the value the notice publishes."; Department checkboxes
  with counts (LGED/RHD/BWDB/PWD/BREB); Status checkboxes (Active
  checked by default, Closing soon (7 days or less), Closed);
  Procurement method dropdown; "Apply filters" button. Filters
  are draft-then-apply. Keyword search + Search + "Refresh from
  e-GP" (days=3, maxPages=5, enrichLimit=12). Sort: Deadline
  (soonest) default, Recently published, Highest Tender ID,
  Security: high to low, Security: low to high.
- Tender card: title, value badge ("BDT <n> tender security",
  compacted Cr/Lakh, or "Security not published"), chips (work
  type, district/division, department, method, "Urgent" when
  closing soon), "Deadline: <date>, <n> days left", "Active"
  badge, "ID <id>, Ref <ref>, <ministry>, Doc price BDT <n>".
- Classification (backend implements; frontend mirrors for
  display): work type from proc_nature/proc_type/category
  (work->Works, good->Goods, consult->Consultancy,
  service->Services); departments by substring on
  ministry/department/organisation/procuring entity (LGED, RHD,
  BWDB, PWD, BREB); division from a static 64-district table +
  aliases (Chittagong -> Chattogram, etc.); status buckets vs
  Asia/Dhaka now: close_dt past -> closed, within 7 days ->
  closing_soon, else active; the Active filter matches any
  non-closed bucket.
- Tender detail modal: all stored fields, AI summary section,
  eligibility section, favourite toggle, "Find a JV partner for
  this tender" (prefills JV tab), "Ask MAS about this tender"
  (prefills Consulting), "View official notice on e-GP" link
  (https://eprocure.gov.bd/resources/common/ViewTender.jsp?id=<id>&h=t).
- Bid pipeline (signed in, under results): per-favourite stage
  select for Pro, read-only stage text otherwise, with the Pro
  note for non-Pro users.
- Copy: port the prototype's strings (headings, labels, buttons,
  empty states, error strings, pay steps, footer disclaimer) as
  captured in inspection 7d0c913e; the verbatim dictionaries
  follow for the frontend. Do not rewrite copy casually.

## 11. e-GP data path (data + backend)

- Refresh: POST https://eprocure.gov.bd/TenderDetailsServlet
  (funName=AllTenders, viewType=Live, publish window, 10-row
  pages), parse HTML rows, upsert by tender_id preserving
  first_seen; enrich new/pending notices via GET
  ViewTender.jsp?id=<id>&h=t (district, doc price, EMD incl.
  per-lot fallback, eligibility, description, lots, opening);
  log fetch_runs. RSS feeds are dead (404); best-effort only.
  Public pages only, polite caps (2s between requests, project
  User-Agent). See tenderbd_scraper/ for the verified code.
- Scheduled refresh: GitHub Actions every 6 hours (existing
  scrape.yml, updated for the new layout) against the production
  DATABASE_URL secret; plus the secured POST /refresh endpoint
  for on-demand runs.
- First production data load: run the scraper against the live
  portal (days=2 window, then enrich) and verify tenders land in
  the database. Never seed or fabricate tenders.

## 12. Environment variables

- DATABASE_URL (required in production; Supabase Postgres URL.
  Local dev: unset -> SQLite file)
- ADMIN_EMAILS (comma-separated; default:
  mashkursakib@gmail.com,info@masconsultancy.org,masconsultancybd@gmail.com)
- REFRESH_TOKEN (required; random secret guarding POST /refresh)
- RESEND_API_KEY (optional; enables password-reset emails.
  From: onboarding or MAS verified domain via Resend.)
- APP_BASE_URL (public base URL, e.g.
  https://tender.masconsultancy.org; used in reset links)
- TENDERBD_SQLITE_PATH (local dev only)
- PORT (provided by Render)

## 13. Decisions that differ from the prototype (documented)

1. AI summary is extractive, not LLM (section 8).
2. Reset token is emailed (Resend), never returned in-app.
3. Admin grant via ADMIN_EMAILS env, not a hardcoded list.
4. Document bytes in Postgres BYTEA, not object storage.
5. Timestamps TIMESTAMPTZ in Postgres (prototype used ms-epoch
   ints in SQLite); API serializes ISO strings.
6. Auth via Bearer header (prototype passed token in bodies).
7. JV interests have no list/read surface and rooms have no
   membership checks, exactly as in the prototype (known gaps,
   preserved deliberately, flagged for the parent).
8. Subscriptions have no expiry/renewal (as prototype).
9. Document status stays 'Declared' (no verification workflow
   in the prototype; flagged for the parent).
10. "Priority consulting replies" for Pro is copy only (no
    priority queue in the prototype; flagged for the parent).
