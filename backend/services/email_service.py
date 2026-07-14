"""Resend email service — real API when configured, mock otherwise.

Supports draft / send-now / schedule. Tracks status via delivery webhooks.
"""
import os
import logging
import uuid
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("email")

RESEND_BASE = "https://api.resend.com"


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


class EmailService:
    provider = "resend"

    def __init__(self, settings: dict | None):
        settings = settings or {}
        self.api_key: str | None = settings.get("resend_api_key") or os.environ.get("RESEND_API_KEY")
        self.from_email: str = (
            settings.get("resend_from_email")
            or os.environ.get("RESEND_FROM_EMAIL")
            or "AI SDR <onboarding@resend.dev>"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def test_connection(self) -> dict:
        if not self.is_configured:
            return {"provider": self.provider, "status": "mocked",
                    "message": "No Resend API key configured — running in Mock Mode.",
                    "at": _now_iso()}
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(f"{RESEND_BASE}/domains",
                                 headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code < 300:
                return {"provider": self.provider, "status": "success",
                        "message": "Connected to Resend.", "at": _now_iso()}
            if r.status_code == 401:
                return {"provider": self.provider, "status": "error",
                        "message": "Invalid Resend API key (401).", "at": _now_iso()}
            return {"provider": self.provider, "status": "error",
                    "message": f"Resend HTTP {r.status_code}: {r.text[:150]}", "at": _now_iso()}
        except Exception as e:
            return {"provider": self.provider, "status": "error", "message": str(e), "at": _now_iso()}

    async def send(self, *, to: str, subject: str, body: str) -> dict:
        """Send an email. Returns {status, provider_message_id, error}."""
        if not self.is_configured:
            return {
                "status": "sent", "provider_message_id": f"mock-{uuid.uuid4().hex[:12]}",
                "error": None, "mocked": True,
                "message": f"[MOCK] would email {to} — subject: '{subject[:60]}'"
            }
        # Convert plain text newlines to <br> for HTML preview
        html_body = body.replace("\n", "<br>")
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{RESEND_BASE}/emails",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "from": self.from_email, "to": [to],
                        "subject": subject, "text": body, "html": html_body,
                    })
            if r.status_code < 300:
                data = r.json()
                return {"status": "sent", "provider_message_id": data.get("id"), "error": None}
            return {"status": "failed", "provider_message_id": None,
                    "error": f"Resend HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            logger.exception("Resend send failed")
            return {"status": "failed", "provider_message_id": None, "error": str(e)}
