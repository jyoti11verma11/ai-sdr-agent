import os
import re
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI

from .prompt_store import PromptStore

logger = logging.getLogger("ai_service")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("SDR_LLM_MODEL", "gpt-4o-mini")

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON found in response: {text[:200]}")
    return json.loads(m.group(0))


# ------------------ Heuristic fallback ------------------
INTENT_HIGH = ["budget", "approved", "purchase", "buy", "urgent", "asap", "demo"]
INTENT_MED = ["interested", "learn more", "pricing", "evaluating", "trial"]

INDUSTRY_HINTS = {
    "fintech": "Fintech",
    "bank": "Fintech",
    "health": "Healthcare",
    "medical": "Healthcare",
    "retail": "E-commerce",
    "edtech": "Education",
    "saas": "SaaS",
    "software": "SaaS",
}

SENIOR = ["ceo", "cto", "vp", "director", "head", "founder"]


def _heuristic_qualify(lead: dict) -> dict:
    text = " ".join([str(lead.get(k) or "") for k in ("company", "message", "job_title", "website")]).lower()

    industry = "Other"
    for k, v in INDUSTRY_HINTS.items():
        if k in text:
            industry = v
            break

    hi = sum(1 for w in INTENT_HIGH if w in text)
    md = sum(1 for w in INTENT_MED if w in text)

    intent = "Very High" if hi >= 2 else "High" if hi == 1 else "Medium" if md else "Low"
    urgency = "Immediate" if hi >= 2 else "High" if hi == 1 else "Medium" if md else "Low"

    senior = any(t in (lead.get("job_title") or "").lower() for t in SENIOR)

    score = {"Very High": 90, "High": 75, "Medium": 55, "Low": 30}[intent]
    if senior:
        score += 5
    score = min(score, 100)

    action = (
        "Call Immediately" if score >= 90 else
        "Book Demo" if score >= 75 else
        "Send Personalized Email" if score >= 55 else
        "Add to Nurture Campaign" if score >= 35 else
        "Reject Lead"
    )

    return {
        "industry": industry,
        "company_size": lead.get("company_size_hint") or "51-200",
        "business_type": "B2B SaaS" if industry == "SaaS" else "Other",
        "icp_match": industry != "Other" and intent in ("High", "Very High"),
        "icp_match_reasoning": "Based on industry and buying intent",
        "buying_intent": intent,
        "urgency": urgency,
        "decision_maker_probability": 85 if senior else 45,
        "score": score,
        "score_explanation": f"Intent={intent}, Senior={senior}",
        "qualification_summary": f"{lead.get('name')} at {lead.get('company')} shows {intent.lower()} intent.",
        "key_signals": [f"Industry: {industry}", f"Intent: {intent}"],
        "recommended_action": action,
        "action_reasoning": f"Lead scored {score}",
        "_fallback": True,
    }


def _heuristic_outreach(lead: dict, qual: dict) -> dict:
    first = (lead.get("name") or "there").split(" ")[0]
    company = lead.get("company") or "your team"

    return {
        "subject": f"Quick idea for {company}",
        "first_email": f"Hi {first},\n\nWe help companies like {company} qualify inbound leads automatically using AI SDR workflows. Open to a 15-minute demo this week?",
        "linkedin_message": f"Hi {first}, noticed {company} is growing in {qual.get('industry')}. We help teams automate lead qualification. Worth a quick chat?",
        "followup_email": f"Hi {first}, following up on my earlier note about helping {company} automate inbound qualification. Happy to share a quick case study.",
        "_fallback": True,
    }


class AIService:
    def __init__(self, db: AsyncIOMotorDatabase, owner_id: str):
        self.db = db
        self.owner_id = owner_id
        self.prompts = PromptStore(db, owner_id)

    async def _record_decision(self, **kwargs):
        try:
            await self.db.ai_decisions.insert_one({
                "id": uuid.uuid4().hex,
                "owner_id": self.owner_id,
                "at": _now_iso(),
                **kwargs
            })
        except Exception:
            logger.exception("Failed to record AI decision")

    async def qualify(self, lead: dict, *, lead_id: str | None = None) -> dict:
        started = time.perf_counter()

        if not client:
            data = _heuristic_qualify(lead)
            await self._record_decision(lead_id=lead_id, decision_type="qualification", output=data, status="fallback")
            return data

        try:
            prompt = await self.prompts.get("qualification")
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt["template"]},
                    {"role": "user", "content": json.dumps(lead)}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            await self._record_decision(
                lead_id=lead_id,
                decision_type="qualification",
                output=data,
                latency_ms=int((time.perf_counter() - started) * 1000),
                status="success",
                score=data.get("score"),
                action=data.get("recommended_action"),
            )
            return data
        except Exception as e:
            logger.warning(f"LLM fallback: {e}")
            data = _heuristic_qualify(lead)
            await self._record_decision(lead_id=lead_id, decision_type="qualification", output=data, status="fallback", error=str(e))
            return data

    async def generate_outreach(self, lead: dict, qualification: dict, *, lead_id: str | None = None, decision_type: str = "outreach") -> dict:
        started = time.perf_counter()

        if not client:
            data = _heuristic_outreach(lead, qualification)
            await self._record_decision(lead_id=lead_id, decision_type=decision_type, output=data, status="fallback")
            return data

        try:
            prompt = await self.prompts.get("outreach")
            ctx = {
                "lead": lead,
                "qualification": qualification,
            }
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt["template"]},
                    {"role": "user", "content": json.dumps(ctx)}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            await self._record_decision(
                lead_id=lead_id,
                decision_type=decision_type,
                output=data,
                latency_ms=int((time.perf_counter() - started) * 1000),
                status="success",
            )
            return data
        except Exception as e:
            logger.warning(f"Outreach fallback: {e}")
            data = _heuristic_outreach(lead, qualification)
            await self._record_decision(lead_id=lead_id, decision_type=decision_type, output=data, status="fallback", error=str(e))
            return data

    async def test_prompt(self, name: str, lead: dict, qualification: dict | None = None) -> dict:
        if name == "qualification":
            return await self.qualify(lead, lead_id=None)
        if name == "outreach":
            if not qualification:
                raise ValueError("qualification is required for outreach test")
            return await self.generate_outreach(lead, qualification, lead_id=None, decision_type="test")
        raise ValueError(f"Unknown prompt: {name}")


async def qualify_lead(lead: dict) -> dict:
    raise RuntimeError("Use AIService.qualify() instead.")


async def generate_email(lead: dict, qualification: dict) -> dict:
    raise RuntimeError("Use AIService.generate_outreach() instead.")
