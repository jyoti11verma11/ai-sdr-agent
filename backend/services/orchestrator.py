"""Integration orchestrator + persistence layer.

Ties HubSpotService, SlackService and N8nService together, records every
attempt in the `integration_logs` collection, and returns activity dicts
ready to append to a lead's timeline.
"""
import logging
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .hubspot_service import HubSpotService
from .slack_service import SlackService, HIGH_PRIORITY_SCORE
from .n8n_service import N8nService

logger = logging.getLogger("integrations.orchestrator")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntegrationOrchestrator:
    """Runs all downstream integrations for a lead and persists logs."""

    def __init__(self, db: AsyncIOMotorDatabase, settings: dict, owner_id: str):
        self.db = db
        self.settings = settings or {}
        self.owner_id = owner_id
        self.hubspot = HubSpotService(settings)
        self.slack = SlackService(settings)
        self.n8n = N8nService(settings)

    # ---------- Public: run full pipeline ----------
    async def run_for_lead(self, lead: dict, qualification: dict, *, lead_id: str) -> list[dict]:
        """Runs all enabled integrations for a qualified lead.

        Returns a list of activity dicts (already logged) to append to the lead.
        """
        activities: list[dict] = []

        # HubSpot: contact → company → deal
        contact_id = company_id = None
        if self.settings.get("auto_sync_hubspot", True):
            contact_res = await self.hubspot.create_contact(lead, qualification)
            activities.append(await self._log(contact_res, lead_id=lead_id, activity_type="hubspot_contact"))
            contact_id = (contact_res.get("data") or {}).get("id")

            company_res = await self.hubspot.create_company(lead, qualification)
            activities.append(await self._log(company_res, lead_id=lead_id, activity_type="hubspot_company"))
            company_id = (company_res.get("data") or {}).get("id")

            deal_res = await self.hubspot.create_deal(lead, qualification, contact_id, company_id)
            activities.append(await self._log(deal_res, lead_id=lead_id, activity_type="hubspot_deal"))

        # Slack
        score = qualification.get("score") or 0
        if self.settings.get("auto_notify_slack", True):
            slack_res = await self.slack.notify_qualified(lead, qualification)
            activities.append(await self._log(slack_res, lead_id=lead_id, activity_type="slack_notified"))
            if score >= HIGH_PRIORITY_SCORE:
                hp_res = await self.slack.notify_high_priority(lead, qualification)
                activities.append(await self._log(hp_res, lead_id=lead_id, activity_type="slack_high_priority"))

        # n8n
        if self.settings.get("auto_trigger_n8n", False):
            n8n_res = await self.n8n.trigger({"lead": lead, "qualification": qualification},
                                              action="lead_qualified")
            activities.append(await self._log(n8n_res, lead_id=lead_id, activity_type="n8n_triggered"))

        return activities

    async def notify_qualification_failure(self, lead: dict, error: str, *, lead_id: str) -> dict:
        if not self.settings.get("auto_notify_slack", True):
            return {}
        res = await self.slack.notify_qualification_failed(lead, error)
        return await self._log(res, lead_id=lead_id, activity_type="slack_qualification_failed")

    async def test_provider(self, provider: str) -> dict:
        svc = self._get_service(provider)
        result = await svc.test_connection()
        await self._log(result, lead_id=None, activity_type=f"{provider}_test")
        return result

    async def status(self) -> dict:
        """Returns configuration + last-sync status per provider."""
        out = {}
        for name, svc in [("hubspot", self.hubspot), ("slack", self.slack), ("n8n", self.n8n)]:
            out[name] = {
                "configured": svc.is_configured,
                "enabled": bool(getattr(svc, "enabled", True)),
                "mode": "live" if svc.is_configured else "mock",
                "last_sync": None,
                "last_status": None,
                "last_message": None,
            }
            last = await self.db.integration_logs.find_one(
                {"owner_id": self.owner_id, "provider": name},
                sort=[("created_at", -1)],
                projection={"_id": 0},
            )
            if last:
                out[name]["last_sync"] = last.get("created_at")
                out[name]["last_status"] = last.get("status")
                out[name]["last_message"] = last.get("message")
        return out

    async def recent_logs(self, provider: str | None = None, limit: int = 30) -> list[dict]:
        q: dict = {"owner_id": self.owner_id}
        if provider:
            q["provider"] = provider
        return await self.db.integration_logs.find(q, {"_id": 0}) \
            .sort("created_at", -1).to_list(limit)

    # ---------- helpers ----------
    def _get_service(self, provider: str):
        if provider == "hubspot": return self.hubspot
        if provider == "slack": return self.slack
        if provider == "n8n": return self.n8n
        raise ValueError(f"Unknown provider: {provider}")

    async def _log(self, result: dict, *, lead_id: str | None, activity_type: str) -> dict:
        """Persist to integration_logs and return an Activity-shaped dict."""
        doc = {
            "id": uuid.uuid4().hex,
            "owner_id": self.owner_id,
            "provider": result.get("provider"),
            "action": result.get("action"),
            "status": result.get("status"),
            "message": result.get("message"),
            "lead_id": lead_id,
            "attempts": result.get("attempts"),
            "data": result.get("data"),
            "created_at": result.get("at") or _now_iso(),
        }
        try:
            await self.db.integration_logs.insert_one(dict(doc))
        except Exception:
            logger.exception("Failed to persist integration log")
        return {
            "id": doc["id"],
            "type": activity_type,
            "message": doc["message"],
            "metadata": {k: doc[k] for k in ("provider", "action", "status", "attempts", "data")},
            "at": doc["created_at"],
        }
