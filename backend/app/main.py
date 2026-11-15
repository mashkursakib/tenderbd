"""TenderBD FastAPI application.

API under /api/v1/; the built SPA is served statically from
frontend/dist when present (one Render web service). /health is
available at the root (Render health checks) and under /api/v1/.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from . import classify, db
from .db import AppStore, get_store
from .routers import (admin, alerts, auth, consulting, documents,
                      favourites, jv, payments, profile, tenders)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_store()
    store.init_all_schemas()
    log.info("TenderBD backend ready (db=%s)",
             "postgres" if store.is_postgres else "sqlite")
    yield


def _health(store: AppStore) -> dict:
    return {"status": "ok",
            "db": "postgres" if store.is_postgres else "sqlite"}


def _stats(store: AppStore) -> dict:
    tenders = store.list_all_tenders()
    now = classify.dhaka_now()
    open_now = sum(1 for t in tenders
                   if classify.status_bucket(t, now=now) != "closed")
    return {"total": len(tenders), "open_now": open_now,
            "last_run": store.last_run()}


def create_app() -> FastAPI:
    app = FastAPI(title="TenderBD", version="1.0.0", lifespan=lifespan)

    api = FastAPI(title="TenderBD API", version="1.0.0")
    api.include_router(auth.router)
    api.include_router(tenders.router)
    api.include_router(profile.router)
    api.include_router(documents.router)
    api.include_router(favourites.router)
    api.include_router(alerts.router)
    api.include_router(jv.router)
    api.include_router(payments.router)
    api.include_router(consulting.router)
    api.include_router(admin.router)

    @api.get("/health")
    def api_health(store: AppStore = Depends(get_store)):
        return _health(store)

    @api.get("/stats")
    def api_stats(store: AppStore = Depends(get_store)):
        return _stats(store)

    app.mount("/api/v1", api)

    @app.get("/health")
    def root_health(store: AppStore = Depends(get_store)):
        return _health(store)

    # Serve the built SPA when it exists. Unknown non-API paths fall
    # back to index.html (client-side routing); unknown API paths
    # stay 404s.
    if FRONTEND_DIST.is_dir():
        index_path = FRONTEND_DIST / "index.html"

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404,
                                    content={"detail": "Not Found"})
            candidate = (FRONTEND_DIST / full_path).resolve()
            if candidate.is_file() and str(candidate).startswith(
                    str(FRONTEND_DIST.resolve())):
                return FileResponse(candidate)
            if index_path.is_file():
                return FileResponse(index_path)
            return JSONResponse(status_code=404,
                                content={"detail": "Not Found"})

    return app


app = create_app()
