"""Official e-GP RSS feeds — best-effort change signal.

The portal links Daily / Weekly RSS feeds from SubscribeToRSS.jsp, but
as of 2026-11-14 every feed URL returned HTTP 404 ("e-GP Invalid Page")
on the live portal, so RSS is NOT the reliable path — the scheduled
search poll in fetcher.py is. This module keeps RSS as a cheap first
check: if the feeds come back, new Tender IDs found here can skip the
search poll; if they fail, the run continues without them.

Never raises on feed failure — it logs and returns what it found.
"""

from __future__ import annotations

import logging
import re

import feedparser

from .config import SETTINGS
from .http import FetchError, PoliteSession

log = logging.getLogger(__name__)

_TENDER_ID_RE = re.compile(r"\b(\d{6,8})\b")


def _tender_id_from_text(text: str) -> int | None:
    """Best-effort Tender ID extraction from an RSS item title/link."""
    if not text:
        return None
    m = _TENDER_ID_RE.search(text)
    return int(m.group(1)) if m else None


def fetch_rss_items(session: PoliteSession,
                    settings: Settings = SETTINGS) -> list[dict]:
    """Fetch all configured RSS feeds; return items with tender ids.

    Each item: {"tender_id": int | None, "title": str, "link": str,
    "published": str}. Feeds that fail (404, DNS, parse errors) are
    logged and skipped — RSS is a hint, not a dependency.
    """
    items: list[dict] = []
    for feed_url in settings.rss_feeds:
        try:
            resp = session.get(feed_url)
        except FetchError as exc:
            log.warning("RSS feed unavailable (%s): %s", feed_url, exc)
            continue
        except Exception as exc:  # noqa: BLE001 - RSS must never break a run
            log.warning("RSS feed error (%s): %s", feed_url, exc)
            continue
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            log.warning("RSS feed did not parse as a feed: %s", feed_url)
            continue
        for entry in parsed.entries:
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            tender_id = (_tender_id_from_text(link)
                         or _tender_id_from_text(title))
            items.append({
                "tender_id": tender_id,
                "title": title,
                "link": link,
                "published": getattr(entry, "published", "") or "",
            })
        log.info("RSS feed %s: %d entries", feed_url, len(parsed.entries))
    # Dedupe by tender id (keep first), keep id-less items at the end.
    seen: set[int] = set()
    unique: list[dict] = []
    for item in items:
        tid = item["tender_id"]
        if tid is None or tid not in seen:
            unique.append(item)
            if tid is not None:
                seen.add(tid)
    return unique
