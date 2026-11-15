# TenderBD production image: FastAPI backend + built React SPA in one
# container, served by a single Render web service.
#
# Contract (per SPEC.md): the backend agent owns backend/app/main.py
# and exposes the FastAPI application as `backend.app.main:app`. The
# app serves the API under /api/v1/ and the built SPA statically from
# frontend/dist. This Dockerfile is written to that contract.
#
# Build context is the repo root. Requires backend/, frontend/ (with
# package.json and package-lock.json), schema/, tenderbd_scraper/ and
# requirements.txt to be present; those are owned by other agents and
# land in parallel with this file.

# ---- Stage 1: build the frontend SPA ----
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend

# Install dependencies first so this layer is cached when only source
# files change. npm ci requires package-lock.json to be committed.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code. schema/ holds the SQL the app applies at startup
# (backend-owned); tenderbd_scraper/ is the data package the /refresh
# endpoint imports; frontend/dist is the SPA built in stage 1.
COPY backend/ ./backend/
COPY tenderbd_scraper/ ./tenderbd_scraper/
COPY schema/ ./schema/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# Render injects PORT at runtime; default to 8000 for local runs.
# Shell form so $PORT expands.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
