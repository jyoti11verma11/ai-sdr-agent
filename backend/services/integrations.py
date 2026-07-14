"""HubSpot / Slack / n8n integration service (mocked with real HTTP fallbacks).

If integration_settings has valid credentials the request is attempted;
otherwise the call is logged as a mocked activity.
"""
import httpx
from datetime import datetime, timezone


async def sync_to_hubspot(lead: dict, qualification: dict, settings: dict) -> dict:
    """Push lead to HubSpot as a contact. MOCKED unless hubspot_token provided."""
    token = (settings or {}).get("hubspot_token")
    if not token:
        return {
            "status": "mocked",
            "provider": "hubspot",
            "message": f"[MOCK] Contact '{lead['email']}' would be created in HubSpot with score {qualification.get('score')}",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "properties": {
                        "email": lead["email"],
                        "firstname": lead["name"].split(" ")[0],
                        "lastname": " ".join(lead["name"].split(" ")[1:]) or "-",
                        "company": lead.get("company"),
                        "jobtitle": lead.get("job_title") or "",
                        "hs_lead_status": qualification.get("recommended_action", ""),
                    }
                },
            )
        return {
            "status": "success" if r.status_code < 300 else "error",
            "provider": "hubspot",
            "message": f"HubSpot responded {r.status_code}",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "error", "provider": "hubspot", "message": str(e), "at": datetime.now(timezone.utc).isoformat()}


async def notify_slack(lead: dict, qualification: dict, settings: dict) -> dict:
    """Send Slack notification. MOCKED unless slack_webhook_url provided."""
    webhook = (settings or {}).get("slack_webhook_url")
    text = (
        f":rocket: *New lead qualified* — *{lead['name']}* @ {lead['company']}\n"
        f"Score: *{qualification.get('score')}/100*  •  Intent: *{qualification.get('buying_intent')}*  •  "
        f"Action: *{qualification.get('recommended_action')}*\n"
        f"> {qualification.get('qualification_summary','')}"
    )
    if not webhook:
        return {
            "status": "mocked",
            "provider": "slack",
            "message": f"[MOCK] Slack notification: {lead['name']} @ {lead['company']} scored {qualification.get('score')}",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(webhook, json={"text": text})
        return {
            "status": "success" if r.status_code < 300 else "error",
            "provider": "slack",
            "message": f"Slack responded {r.status_code}",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "error", "provider": "slack", "message": str(e), "at": datetime.now(timezone.utc).isoformat()}


async def trigger_n8n(lead: dict, qualification: dict, settings: dict) -> dict:
    """Fire n8n webhook."""
    url = (settings or {}).get("n8n_webhook_url")
    if not url:
        return {
            "status": "mocked",
            "provider": "n8n",
            "message": "[MOCK] n8n webhook not configured",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={"lead": lead, "qualification": qualification})
        return {
            "status": "success" if r.status_code < 300 else "error",
            "provider": "n8n",
            "message": f"n8n responded {r.status_code}",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "error", "provider": "n8n", "message": str(e), "at": datetime.now(timezone.utc).isoformat()}
