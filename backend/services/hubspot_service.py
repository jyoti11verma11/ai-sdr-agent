"""HubSpot integration service.

Real API when a private-app token is configured; mock fallback otherwise.
"""
import os
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("integrations.hubspot")

HUBSPOT_BASE = os.environ.get("HUBSPOT_BASE_URL", "https://api.hubapi.com")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HubSpotService:
    provider = "hubspot"

    def __init__(self, settings: dict | None):
        settings = settings or {}
        self.token: str | None = settings.get("hubspot_token") or None
        self.enabled: bool = bool(settings.get("auto_sync_hubspot", True))

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    # ---------- Test ----------
    async def test_connection(self) -> dict:
        if not self.is_configured:
            return {
                "provider": self.provider, "status": "mocked",
                "message": "No HubSpot token configured — running in Mock Mode.",
                "at": _now(),
            }
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{HUBSPOT_BASE}/crm/v3/objects/contacts?limit=1", headers=self._headers())
            if r.status_code == 200:
                return {"provider": self.provider, "status": "success", "message": "Connected to HubSpot.", "at": _now()}
            if r.status_code == 401:
                return {"provider": self.provider, "status": "error", "message": "Invalid HubSpot token (401).", "at": _now()}
            return {"provider": self.provider, "status": "error", "message": f"HubSpot HTTP {r.status_code}: {r.text[:200]}", "at": _now()}
        except Exception as e:
            logger.exception("HubSpot test_connection failed")
            return {"provider": self.provider, "status": "error", "message": f"Network error: {e}", "at": _now()}

    # ---------- Contact ----------
    async def create_contact(self, lead: dict, qualification: dict) -> dict:
        if not self.is_configured:
            return self._mock("create_contact", f"Contact '{lead['email']}' would be created in HubSpot.")
        payload = {
            "properties": {
                "email": lead["email"],
                "firstname": (lead.get("name") or "").split(" ")[0] or "-",
                "lastname": " ".join((lead.get("name") or "").split(" ")[1:]) or "-",
                "company": lead.get("company"),
                "jobtitle": lead.get("job_title") or "",
                "website": lead.get("website") or "",
                "hs_lead_status": qualification.get("recommended_action", ""),
            }
        }
        return await self._post_object("contacts", payload, "create_contact", label=f"contact '{lead['email']}'")

    # ---------- Company ----------
    async def create_company(self, lead: dict, qualification: dict) -> dict:
        if not self.is_configured:
            return self._mock("create_company", f"Company '{lead.get('company')}' would be created in HubSpot.")
        payload = {
            "properties": {
                "name": lead.get("company") or "-",
                "domain": (lead.get("website") or "").replace("https://", "").replace("http://", "").strip("/"),
                "industry": qualification.get("industry") or "",
                "numberofemployees": _size_to_number(qualification.get("company_size")),
            }
        }
        return await self._post_object("companies", payload, "create_company", label=f"company '{lead.get('company')}'")

    # ---------- Deal ----------
    async def create_deal(self, lead: dict, qualification: dict, contact_id: str | None = None, company_id: str | None = None) -> dict:
        if not self.is_configured:
            return self._mock("create_deal", f"Deal for '{lead.get('company')}' (score {qualification.get('score')}) would be created.")
        score = qualification.get("score") or 0
        stage = "appointmentscheduled" if score >= 85 else "qualifiedtobuy" if score >= 65 else "presentationscheduled"
        payload = {
            "properties": {
                "dealname": f"{lead.get('company')} — Inbound ({score}/100)",
                "dealstage": stage,
                "pipeline": "default",
                "hubspot_owner_id": "",
                "amount": "",
            }
        }
        result = await self._post_object("deals", payload, "create_deal", label=f"deal for '{lead.get('company')}'")
        # Associate deal with contact + company (best-effort, ignore failures)
        deal_id = (result.get("data") or {}).get("id")
        if deal_id and (contact_id or company_id):
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    if contact_id:
                        await c.put(f"{HUBSPOT_BASE}/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/3", headers=self._headers())
                    if company_id:
                        await c.put(f"{HUBSPOT_BASE}/crm/v3/objects/deals/{deal_id}/associations/companies/{company_id}/5", headers=self._headers())
            except Exception:
                logger.exception("Deal association failed")
        return result

    # ---------- Status sync ----------
    async def sync_status(self, contact_id: str, status: str) -> dict:
        if not self.is_configured:
            return self._mock("sync_status", f"Contact status '{status}' would be synced.")
        if not contact_id:
            return {"provider": self.provider, "action": "sync_status", "status": "error",
                    "message": "Missing HubSpot contact_id", "data": None, "at": _now()}
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.patch(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts/{contact_id}",
                    headers=self._headers(),
                    json={"properties": {"hs_lead_status": status}},
                )
            ok = r.status_code < 300
            return {
                "provider": self.provider, "action": "sync_status",
                "status": "success" if ok else "error",
                "message": f"Status synced ({status})" if ok else f"HTTP {r.status_code}",
                "data": {"contact_id": contact_id, "status": status}, "at": _now(),
            }
        except Exception as e:
            logger.exception("HubSpot sync_status failed")
            return {"provider": self.provider, "action": "sync_status", "status": "error",
                    "message": str(e), "data": None, "at": _now()}

    # ---------- helpers ----------
    def _mock(self, action: str, msg: str) -> dict:
        return {
            "provider": self.provider, "action": action, "status": "mocked",
            "message": f"[MOCK] {msg}", "data": None, "at": _now(),
        }

    async def _post_object(self, obj: str, payload: dict, action: str, label: str = "") -> dict:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{HUBSPOT_BASE}/crm/v3/objects/{obj}", headers=self._headers(), json=payload)
            if r.status_code < 300:
                data = r.json()
                return {
                    "provider": self.provider, "action": action, "status": "success",
                    "message": f"HubSpot {obj[:-1]} created — {label}".strip(),
                    "data": {"id": data.get("id")}, "at": _now(),
                }
            if r.status_code == 409:
                return {
                    "provider": self.provider, "action": action, "status": "success",
                    "message": f"HubSpot {obj[:-1]} already exists ({label})",
                    "data": None, "at": _now(),
                }
            logger.warning(f"HubSpot {action} failed: {r.status_code} {r.text[:200]}")
            return {
                "provider": self.provider, "action": action, "status": "error",
                "message": f"HubSpot HTTP {r.status_code}: {r.text[:200]}",
                "data": None, "at": _now(),
            }
        except Exception as e:
            logger.exception(f"HubSpot {action} exception")
            return {"provider": self.provider, "action": action, "status": "error",
                    "message": str(e), "data": None, "at": _now()}


def _size_to_number(size: str | None) -> str:
    if not size: return ""
    m = {"1-10": "5", "11-50": "30", "51-200": "125", "201-500": "350", "501-1000": "750", "1000+": "1500"}
    return m.get(size, "")
