"""Polite HTTP layer for the TenderBD scraper.

Rules enforced here:
- Every request identifies the project in the User-Agent.
- A delay is kept between requests (default 2s).
- Transient failures retry with exponential backoff (2s, 4s, 8s).
- robots.txt is fetched once per session and honoured when present.
  (eprocure.gov.bd returned HTTP 401 for /robots.txt on 2026-11-14, i.e.
  effectively no robots file; the scraper still stays polite.)
- Only public, login-free URLs are ever requested. There is no login
  code path anywhere in this package.
"""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from .config import SETTINGS

log = logging.getLogger(__name__)


class FetchError(Exception):
    """A fetch failed after all retries, or the response was unusable."""


class PoliteSession:
    """A requests session with delays, retries and robots.txt support."""

    def __init__(self, settings: Settings = SETTINGS) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._robots: urllib.robotparser.RobotFileParser | None = None
        self._robots_checked = False
        self._last_request_at = 0.0

    # -- robots.txt -----------------------------------------------------
    def _load_robots(self) -> None:
        if self._robots_checked:
            return
        self._robots_checked = True
        # Fetch with requests (not robotparser.read()): robotparser
        # treats a 401/403 on robots.txt as "disallow everything", but
        # eprocure.gov.bd answers /robots.txt with HTTP 401 + a JSON
        # error body, which is not a robots file at all. Only a real
        # HTTP 200 text response is honoured as robots.txt; anything
        # else means "no usable robots file" (politeness rules below
        # still apply).
        try:
            resp = self.session.get(
                self.settings.robots_url,
                timeout=self.settings.request_timeout_seconds)
            if resp.status_code == 200 and "user-agent" in resp.text.lower():
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots = rp
                log.info("robots.txt loaded from %s",
                         self.settings.robots_url)
            else:
                log.info("No usable robots.txt at %s (HTTP %s); "
                         "continuing with built-in politeness rules.",
                         self.settings.robots_url, resp.status_code)
                self._robots = None
        except Exception as exc:  # noqa: BLE001 - robots failure is non-fatal
            log.warning("Could not read robots.txt (%s); continuing politely: %s",
                        self.settings.robots_url, exc)
            self._robots = None

    def allowed_by_robots(self, url: str) -> bool:
        self._load_robots()
        if self._robots is None:
            return True  # no usable robots file; politeness rules still apply
        return bool(self._robots.can_fetch(self.settings.user_agent, url))

    # -- request plumbing ----------------------------------------------
    def _wait_for_delay(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        delay = self.settings.request_delay_seconds
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Request with delay, retries and exponential backoff.

        Retries on network errors and HTTP 429 / 5xx. Raises FetchError
        after all retries, or immediately on other HTTP errors.
        """
        if not self.allowed_by_robots(url):
            raise FetchError(f"Blocked by robots.txt: {url}")

        kwargs.setdefault("timeout", self.settings.request_timeout_seconds)
        last_exc: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            self._wait_for_delay()
            try:
                resp = self.session.request(method, url, **kwargs)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("Request failed (%s %s, attempt %d/%d): %s",
                            method, url, attempt, self.settings.max_retries, exc)
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = FetchError(f"HTTP {resp.status_code} for {url}")
                    retry_after = resp.headers.get("Retry-After")
                    wait = self._backoff(attempt, retry_after)
                    log.warning("HTTP %s for %s (attempt %d/%d); retrying in %.1fs",
                                resp.status_code, url, attempt,
                                self.settings.max_retries, wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code} for {url}")
                return resp
            if attempt < self.settings.max_retries:
                wait = self._backoff(attempt)
                log.warning("Retrying %s in %.1fs (attempt %d/%d)",
                            url, wait, attempt + 1, self.settings.max_retries)
                time.sleep(wait)
        raise FetchError(f"Failed after {self.settings.max_retries} attempts: "
                         f"{method} {url}: {last_exc}")

    def _backoff(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return max(float(retry_after), 1.0)
            except ValueError:
                pass
        return self.settings.backoff_base_seconds * (2 ** (attempt - 1))

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        self.session.close()


def is_egp_public_url(url: str) -> bool:
    """Guard: only eprocure.gov.bd public pages are ever fetched."""
    host = urlparse(url).netloc.lower()
    return host in {"eprocure.gov.bd", "www.eprocure.gov.bd"}
