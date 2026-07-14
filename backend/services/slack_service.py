"""Slack integration service.

Uses an Incoming Webhook URL. Mock fallback when unconfigured.
"""
import os
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("integrations.slack")

HIGH_PRIORITY_SCORE = int(os.environ.get("HIGH_PRIORITY_SCORE", "85"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SlackService:
    provider = "slack"

    def __init__(self, settings: dict | None):
        settings = settings or {}
        self.webhook: str | None = settings.get("slack_webhook_url") or None
        self.enabled: bool = bool(settings.get("auto_notify_slack", True))

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook)

    # ---------- Test ----------
    async def test_connection(self) -> dict:
        if not self.is_configured:
            return {"provider": self.provider, "status": "mocked",
                    "message": "No Slack webhook configured — running in Mock Mode.",
                    "at": _now()}
        return await self._send(
            text=":white_check_mark: SDR Agent test connection — everything looks good.",
            action="test_connection",
        )

    # ---------- Notifications ----------
    async def notify_qualified(self, lead: dict, qualification: dict) -> dict:
        score = qualification.get("score")
        text = (
            f":rocket: *New qualified lead* — *{lead['name']}* @ {lead['company']}\n"
            f"Score: *{score}/100* · Intent: *{qualification.get('buying_intent')}* · "
            f"Action: *{qualification.get('recommended_action')}*\n"
            f"> {qualification.get('qualification_summary','')}"
        )
        return await self._send(text, action="notify_qualified")

    async def notify_high_priority(self, lead: dict, qualification: dict) -> dict:
        text = (
            f":fire: *HOT LEAD* — *{lead['name']}* @ {lead['company']}\n"
            f"Score: *{qualification.get('score')}/100* · Recommended: *{qualification.get('recommended_action')}*.\n"
            f"Reach out ASAP."
        )
        return await self._send(text, action="notify_high_priority")

    async def notify_qualification_failed(self, lead: dict, error: str) -> dict:
        text = (
            f":warning: *AI qualification failed* for lead *{lead['name']}* @ {lead['company']}\n"
            f"Reason: `{error[:250]}`"
        )
        return await self._send(text, action="notify_qualification_failed")

    # ---------- helpers ----------
    async def _send(self, text: str, action: str) -> dict:
        if not self.is_configured:
            return {"provider": self.provider, "action": action, "status": "mocked",
                    "message": f"[MOCK] {text[:120]}", "data": None, "at": _now()}
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(self.webhook, json={"text": text})
            ok = r.status_code < 300
            return {
                "provider": self.provider, "action": action,
                "status": "success" if ok else "error",
                "message": "Slack notified" if ok else f"Slack HTTP {r.status_code}: {r.text[:150]}",
                "data": None, "at": _now(),
            }
        except Exception as e:
            logger.exception("Slack send failed")
            return {"provider": self.provider, "action": action, "status": "error",
                    "message": str(e), "data": None, "at": _now()}
