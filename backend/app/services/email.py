"""Password-reset email via the Resend API (httpx).

No-op with a logged warning when RESEND_API_KEY is unset. The reset
token is NEVER returned in any API response; it travels only inside
the emailed link.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx

from .. import config

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 15.0


def reset_link(email: str, token: str) -> str:
    query = urlencode({"token": token, "email": email})
    return f"{config.app_base_url()}/reset-password?{query}"


def send_password_reset_email(email: str, token: str) -> bool:
    """Send the reset link. Returns True on success, False otherwise."""
    api_key = config.resend_api_key()
    if not api_key:
        log.warning("RESEND_API_KEY is not set; password-reset email "
                    "for %s was not sent.", email)
        return False
    link = reset_link(email, token)
    html = (
        "<p>You asked to reset your TenderBD password.</p>"
        f'<p><a href="{link}">Reset your password</a></p>'
        "<p>This link works for 1 hour. If you did not ask for a "
        "reset, ignore this email.</p>"
    )
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"from": config.resend_from(),
                  "to": [email],
                  "subject": "Reset your TenderBD password",
                  "html": html},
            timeout=TIMEOUT_SECONDS)
        if resp.status_code >= 400:
            log.warning("Resend rejected the reset email for %s "
                        "(HTTP %s): %s", email, resp.status_code,
                        resp.text[:200])
            return False
    except httpx.HTTPError as exc:
        log.warning("Failed to send reset email to %s: %s", email, exc)
        return False
    return True
