# TenderBD

A portal for Bangladesh e-GP tenders: searchable public tender
notices from the e-GP portal, with eligibility estimates, a JV
partner room, alerts, and MAS consulting requests. Deploys to
https://tender.masconsultancy.org.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI + Uvicorn, psycopg 3, argon2id |
| Frontend | React 18 + Vite + TypeScript, plain CSS |
| Database | PostgreSQL (Supabase free tier) in production, SQLite locally |
| Hosting | One Render web service (free tier), Docker |
| Scraper | Python, requests + BeautifulSoup, scheduled by GitHub Actions |

One Render service serves both the API (under `/api/v1/`) and the
built SPA (from `frontend/dist`). See `SPEC.md` for the full
specification.

## Local development

Prerequisites: Python 3.12 and Node 20.

```bash
# 1. Clone and enter the repo
git clone https://github.com/mashkursakib/tenderbd.git
cd tenderbd

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Environment (SQLite is the default when DATABASE_URL is unset)
cp .env.example .env
# Edit .env: set REFRESH_TOKEN to a random string. Leave DATABASE_URL
# unset for local SQLite, or point it at a local Postgres.

# 4. Initialise the database (optional for local dev)
# The server creates every table automatically on its first start,
# so this step is only needed if you want to run the scraper before
# starting the server:
python -m tenderbd_scraper.scrape init-db

# 5. Build the frontend
cd frontend
npm install
npm run build
cd ..

# 6. Run the server
uvicorn backend.app.main:app --reload
```

The portal is then at http://localhost:8000, with API docs at
http://localhost:8000/docs. For iterative frontend work, run
`npm run dev` in `frontend/` instead of step 5 (Vite dev server).

### Docker alternative

```bash
docker compose up --build
```

This starts a local Postgres 15 database and the app container
built from the production Dockerfile. See `docker-compose.yml`
for first-run database initialisation.

### Running the scraper

```bash
# Incremental run: last 2 days of notices, then enrich new ones
python -m tenderbd_scraper.scrape run --days 2

# Search poll only, no detail enrichment
python -m tenderbd_scraper.scrape run --days 2 --no-enrich
```

The scraper reads public e-GP pages only. It needs no login and no
credentials. It is polite by design: 2 seconds between requests,
retries with backoff, project User-Agent.

### Running the tests

```bash
python -m pytest backend/tests -q
python -m pytest tests-scraper -q
```

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Production | Supabase Postgres URL. Unset locally means SQLite. |
| `ADMIN_EMAILS` | No | Comma-separated admin emails. Default: the three MAS addresses. |
| `REFRESH_TOKEN` | Yes | Random secret guarding `POST /api/v1/refresh`. |
| `RESEND_API_KEY` | No | Enables password-reset emails via Resend. |
| `APP_BASE_URL` | Yes | Public base URL, used in reset links. |
| `TENDERBD_SQLITE_PATH` | No | Local SQLite file path. Default: `tenderbd.db`. |
| `PORT` | No | Provided by Render. Locally defaults to 8000. |

See `.env.example` for placeholders and the optional scraper
tuning variables.

## Deployment

1. **Database.** Create a Supabase project (free tier) and copy
   its Postgres connection URL. The app creates every table
   (scraper + app schemas) automatically on its first start, so
   no manual schema step is needed. Load the first tenders after
   the deploy with `POST /api/v1/refresh` (see below), or before
   it with `python -m tenderbd_scraper.scrape run --days 2`
   against the production `DATABASE_URL`.
2. **Render.** In the Render dashboard, New, Blueprint, select
   this repo. Render reads `render.yaml` and creates the
   `tenderbd` web service (Singapore, free, Docker). Set the
   dashboard variables: `DATABASE_URL` (Supabase URL),
   `REFRESH_TOKEN` (a long random string),
   `RESEND_API_KEY` (optional). Then deploy.
3. **DNS.** On Spaceship, add a CNAME record for the
   `masconsultancy.org` zone: host `tender`, value the Render
   service URL (`tenderbd.onrender.com`). In Render, add the
   custom domain `tender.masconsultancy.org` to the service.
4. **Scraper schedule.** In the GitHub repo, Settings, Secrets
   and variables, Actions, add the secret `DATABASE_URL` with
   the same Supabase URL. The scheduled workflow
   (`.github/workflows/scrape.yml`) then refreshes tenders
   automatically.

## Refresh schedule

- GitHub Actions runs the scraper every 6 hours (04:00, 10:00,
  16:00, 22:00 UTC), polling the last 2 days of notices.
- On demand: `POST /api/v1/refresh` with header
  `X-Refresh-Token` (body defaults: days 3, max 5 pages,
  enrich up to 12 notices). A signed-in admin can also trigger
  it from the Refresh button in the explorer; the button is
  shown only to admins.

## Honesty notes

- **Public data only.** TenderBD reads public e-GP notice pages.
  It has no bidder login and publishes nothing e-GP does not
  publish.
- **Eligibility is an estimate.** Scores are computed from the
  public notice fields plus the user's declared profile. Full
  eligibility criteria live inside the tender document on e-GP,
  which needs a bidder login. The estimate is labelled as such
  everywhere it appears.
- **EMD, not contract value.** e-GP publishes no estimated
  contract value. The value filter and card badge use the tender
  security (EMD) and are labelled as such, never as contract
  value.
