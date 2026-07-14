"""AI service — qualification, outreach kit + AIDecision recording.

Uses GPT-5.2 via Emergent Universal Key with a deterministic heuristic
fallback so the app remains functional if the LLM is down.
Prompt templates are versioned in Mongo via PromptStore.
"""
import os
import re
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from emergentintegrations.llm.chat import LlmChat, UserMessage

from .prompt_store import PromptStore

logger = logging.getLogger("ai_service")

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
MODEL = os.environ.get("SDR_LLM_MODEL", "gpt-5.2")


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m: raise ValueError(f"No JSON in: {text[:200]}")
    return json.loads(m.group(0))


# ---------- Heuristic fallback (unchanged, kept for resilience) ----------
INTENT_HIGH = ["budget", "approved", "purchase", "buy", "urgent", "asap", "q1", "q2", "q3", "q4",
               "next month", "soc2", "compliance", "vendor evaluation", "rfp", "demo"]
INTENT_MED = ["interested", "learn more", "pricing", "evaluating", "considering", "trial", "curious"]
INDUSTRY_HINTS = {
    "fintech": "Fintech", "bank": "Fintech", "finance": "Fintech", "payments": "Fintech",
    "health": "Healthcare", "clinic": "Healthcare", "medical": "Healthcare", "pharma": "Healthcare",
    "shop": "E-commerce", "commerce": "E-commerce", "retail": "E-commerce",
    "school": "Education", "university": "Education", "edtech": "Education",
    "media": "Media", "news": "Media", "real estate": "Real Estate", "property": "Real Estate",
    "consult": "Consulting", "manufactur": "Manufacturing", "saas": "SaaS", "software": "SaaS",
}
SENIOR = ["ceo", "cto", "cfo", "coo", "vp", "chief", "head", "director", "founder", "president"]


def _heuristic_qualify(lead: dict) -> dict:
    text = " ".join([str(lead.get(k) or "") for k in ("company", "message", "job_title", "website")]).lower()
    industry = "Other"
    for k, v in INDUSTRY_HINTS.items():
        if k in text: industry = v; break
    size = "51-200"
    m = re.search(r"(\d[\d,]*)\s*(?:employees|people|staff)", text)
    if m:
        n = int(m.group(1).replace(",", ""))
        size = ("1-10" if n < 11 else "11-50" if n < 51 else "51-200" if n < 201
                else "201-500" if n < 501 else "501-1000" if n < 1001 else "1000+")
    elif lead.get("company_size_hint"): size = lead["company_size_hint"]

    hi = sum(1 for w in INTENT_HIGH if w in text)
    md = sum(1 for w in INTENT_MED if w in text)
    intent = "Very High" if hi >= 3 else "High" if hi >= 1 else "Medium" if md >= 1 else "Low"
    urgency = "Immediate" if hi >= 3 else "High" if hi >= 1 else "Medium" if md >= 1 else "Low"

    senior = any(t in (lead.get("job_title") or "").lower() for t in SENIOR)
    dm_prob = 85 if senior else 55 if lead.get("job_title") else 30

    base = {"Very High": 88, "High": 72, "Medium": 55, "Low": 32}[intent]
    if senior: base += 8
    if size in ("201-500", "501-1000", "1000+"): base += 4
    score = max(0, min(100, base))
    action = ("Call Immediately" if score >= 90 else "Book Demo" if score >= 75
              else "Send Personalized Email" if score >= 55 else
              "Add to Nurture Campaign" if score >= 35 else "Reject Lead")
    icp = intent in ("High", "Very High") and industry != "Other"
    signals = []
    if senior: signals.append(f"Senior title detected: {lead.get('job_title')}")
    if hi: signals.append(f"{hi} explicit buying signal(s) in message")
    if size in ("201-500", "501-1000", "1000+"): signals.append(f"Mid/large company ({size})")
    if industry != "Other": signals.append(f"Industry match: {industry}")
    if not signals: signals.append("No strong signals — nurture recommended")

    return {
        "industry": industry, "company_size": size,
        "business_type": "B2B SaaS" if industry == "SaaS" else "Other",
        "icp_match": icp,
        "icp_match_reasoning": f"{'Strong' if icp else 'Weak'} fit based on industry+intent heuristics",
        "buying_intent": intent, "urgency": urgency,
        "decision_maker_probability": dm_prob,
        "score": score,
        "score_explanation": f"Heuristic: {intent} intent (+base {base}), {'senior' if senior else 'no-senior'} bonus, size {size}.",
        "qualification_summary": f"{lead.get('name')} at {lead.get('company')} — {industry}/{size}, {intent} intent. Recommended: {action.lower()}.",
        "key_signals": signals[:5],
        "recommended_action": action,
        "action_reasoning": f"Score {score} + {intent.lower()} intent → {action}.",
        "_fallback": True,
    }


def _heuristic_outreach(lead: dict, qual: dict) -> dict:
    first = (lead.get("name") or "there").split(" ")[0]
    company = lead.get("company") or "your team"
    subject = f"Quick idea for {company}"
    body = (f"Hi {first},\n\nSaw your inquiry — as a {qual.get('company_size','growing')} team in "
            f"{qual.get('industry','your space')}, you're likely dealing with slow inbound follow-up. "
            f"We've helped similar teams cut response time from hours to under 60 seconds using an AI SDR.\n\n"
            f"Open to a 15-min call this week to see if it's a fit for {company}?")
    return {
        "subject": subject,
        "first_email": body,
        "linkedin_message": f"Hi {first} — noticed {company} is in {qual.get('industry','your space')}. "
                             f"We help teams like yours qualify inbound in seconds. Worth a chat?",
        "followup_email": f"Hi {first},\n\nCircling back on my note about {company}. "
                          f"Sharing a quick case study of a similar team that saved 12 hours/week — happy to send.\n\nWorth 10 mins?",
        "_fallback": True,
    }


# ---------- Public API ----------
class AIService:
    """Encapsulates LLM calls + AIDecision persistence."""

    def __init__(self, db: AsyncIOMotorDatabase, owner_id: str):
        self.db = db
        self.owner_id = owner_id
        self.prompts = PromptStore(db, owner_id)

    async def _record_decision(self, *, lead_id, decision_type, prompt_name, prompt_version,
                                input_summary, output, latency_ms, status, error=None,
                                score=None, action=None, reasoning=None):
        doc = {
            "id": uuid.uuid4().hex,
            "owner_id": self.owner_id,
            "lead_id": lead_id,
            "decision_type": decision_type,
            "prompt_name": prompt_name,
            "prompt_version": prompt_version,
            "model": MODEL,
            "input_summary": input_summary[:400],
            "output": output or {},
            "reasoning": reasoning,
            "score": score, "action": action,
            "latency_ms": latency_ms,
            "status": status, "error": error,
            "at": _now_iso(),
        }
        try: await self.db.ai_decisions.insert_one(dict(doc))
        except Exception: logger.exception("Failed to record AIDecision")
        return doc

    def _lead_context(self, lead: dict) -> str:
        return (
            f"Name: {lead.get('name')}\nEmail: {lead.get('email')}\nCompany: {lead.get('company')}\n"
            f"Job Title: {lead.get('job_title') or 'N/A'}\nWebsite: {lead.get('website') or 'N/A'}\n"
            f"Reported Size: {lead.get('company_size_hint') or 'N/A'}\n"
            f"Message:\n{lead.get('message') or 'N/A'}\nSource: {lead.get('source') or 'website'}"
        )

    async def qualify(self, lead: dict, *, lead_id: str | None = None) -> dict:
        prompt = await self.prompts.get("qualification")
        chat = LlmChat(api_key=EMERGENT_LLM_KEY,
                       session_id=f"qualify-{uuid.uuid4()}",
                       system_message=prompt["template"]).with_model("openai", MODEL)
        input_summary = f"lead={lead.get('name')} @ {lead.get('company')}"
        started = time.perf_counter()
        try:
            response = await chat.send_message(UserMessage(text=self._lead_context(lead)))
            data = _extract_json(response)
            latency = int((time.perf_counter() - started) * 1000)
            await self._record_decision(
                lead_id=lead_id, decision_type="qualification",
                prompt_name="qualification", prompt_version=prompt["version"],
                input_summary=input_summary, output=data, latency_ms=latency,
                status="success",
                score=data.get("score"),
                action=data.get("recommended_action"),
                reasoning=data.get("score_explanation"),
            )
            return data
        except Exception as e:
            logger.warning(f"LLM qualify fallback: {e}")
            data = _heuristic_qualify(lead)
            latency = int((time.perf_counter() - started) * 1000)
            await self._record_decision(
                lead_id=lead_id, decision_type="qualification",
                prompt_name="qualification", prompt_version=prompt["version"],
                input_summary=input_summary, output=data, latency_ms=latency,
                status="fallback", error=str(e),
                score=data.get("score"),
                action=data.get("recommended_action"),
                reasoning=data.get("score_explanation"),
            )
            return data

    async def generate_outreach(self, lead: dict, qualification: dict,
                                 *, lead_id: str | None = None,
                                 decision_type: str = "outreach") -> dict:
        prompt = await self.prompts.get("outreach")
        chat = LlmChat(api_key=EMERGENT_LLM_KEY,
                       session_id=f"outreach-{uuid.uuid4()}",
                       system_message=prompt["template"]).with_model("openai", MODEL)
        ctx = (
            f"Recipient: {lead.get('name')} ({lead.get('job_title') or 'buyer'}) at {lead.get('company')}\n"
            f"Industry: {qualification.get('industry')}\nCompany Size: {qualification.get('company_size')}\n"
            f"Business Type: {qualification.get('business_type')}\n"
            f"Buying Intent: {qualification.get('buying_intent')}, Urgency: {qualification.get('urgency')}\n"
            f"Their message: {lead.get('message') or ''}\n"
            f"Key signals: {', '.join(qualification.get('key_signals', []))}\n"
            f"Recommended action: {qualification.get('recommended_action')}\n"
            f"You represent an AI SDR Agent SaaS."
        )
        started = time.perf_counter()
        input_summary = f"outreach for {lead.get('name')} @ {lead.get('company')} (score {qualification.get('score')})"
        try:
            response = await chat.send_message(UserMessage(text=ctx))
            data = _extract_json(response)
            latency = int((time.perf_counter() - started) * 1000)
            await self._record_decision(
                lead_id=lead_id, decision_type=decision_type,
                prompt_name="outreach", prompt_version=prompt["version"],
                input_summary=input_summary, output=data, latency_ms=latency,
                status="success",
            )
            return data
        except Exception as e:
            logger.warning(f"LLM outreach fallback: {e}")
            data = _heuristic_outreach(lead, qualification)
            latency = int((time.perf_counter() - started) * 1000)
            await self._record_decision(
                lead_id=lead_id, decision_type=decision_type,
                prompt_name="outreach", prompt_version=prompt["version"],
                input_summary=input_summary, output=data, latency_ms=latency,
                status="fallback", error=str(e),
            )
            return data

    async def test_prompt(self, name: str, lead: dict, qualification: dict | None = None) -> dict:
        """Dry-run a prompt without persisting a lead. Records an AIDecision of type 'test'."""
        if name == "qualification":
            return await self.qualify(lead, lead_id=None)
        if name == "outreach":
            if not qualification:
                raise ValueError("qualification is required for outreach test")
            return await self.generate_outreach(lead, qualification, lead_id=None, decision_type="test")
        raise ValueError(f"Unknown prompt: {name}")


# ---------- Backwards-compat wrappers for older imports ----------
async def qualify_lead(lead: dict) -> dict:
    """Deprecated: use AIService.qualify()."""
    raise RuntimeError("Use AIService.qualify() instead — this shim was removed in Phase 3.")


async def generate_email(lead: dict, qualification: dict) -> dict:
    raise RuntimeError("Use AIService.generate_outreach() instead.")
