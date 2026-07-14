"""n8n outbound webhook service with exponential-backoff retry."""
import os
import asyncio
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("integrations.n8n")

MAX_ATTEMPTS = int(os.environ.get("N8N_MAX_ATTEMPTS", "3"))
BASE_BACKOFF = float(os.environ.get("N8N_BASE_BACKOFF", "1.0"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class N8nService:
    provider = "n8n"

    def __init__(self, settings: dict | None):
        settings = settings or {}
        self.url: str | None = settings.get("n8n_webhook_url") or None
        self.enabled: bool = bool(settings.get("auto_trigger_n8n", False))

    @property
    def is_configured(self) -> bool:
        return bool(self.url)

    async def test_connection(self) -> dict:
        if not self.is_configured:
            return {"provider": self.provider, "status": "mocked",
                    "message": "No n8n webhook configured — running in Mock Mode.",
                    "at": _now()}
        return await self.trigger({"test": True, "source": "sdr-agent"}, action="test_connection", max_attempts=1)

    async def trigger(self, payload: dict, action: str = "trigger", max_attempts: int | None = None) -> dict:
        if not self.is_configured:
            return {"provider": self.provider, "action": action, "status": "mocked",
                    "message": "[MOCK] n8n webhook not configured.", "attempts": 0, "data": None, "at": _now()}
        attempts = max_attempts if max_attempts is not None else MAX_ATTEMPTS
        last_err = ""
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.post(self.url, json=payload)
                if r.status_code < 300:
                    return {
                        "provider": self.provider, "action": action, "status": "success",
                        "message": f"n8n webhook fired (HTTP {r.status_code}) in {attempt} attempt(s)",
                        "attempts": attempt, "data": {"status_code": r.status_code}, "at": _now(),
                    }
                last_err = f"HTTP {r.status_code}: {r.text[:150]}"
                logger.warning(f"n8n attempt {attempt}/{attempts} → {last_err}")
            except Exception as e:
                last_err = str(e)
                logger.warning(f"n8n attempt {attempt}/{attempts} exception: {e}")
            if attempt < attempts:
                await asyncio.sleep(BASE_BACKOFF * (2 ** (attempt - 1)))
        return {
            "provider": self.provider, "action": action, "status": "error",
            "message": f"n8n failed after {attempts} attempts — {last_err}",
            "attempts": attempts, "data": None, "at": _now(),
        }
