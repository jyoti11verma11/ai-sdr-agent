"""AI qualification and email generation service using GPT-5.2 via Emergent LLM Key.
Falls back to a deterministic heuristic scorer if the LLM call fails
(e.g. budget exceeded, network error) so the product remains functional end-to-end.
"""
import os
import json
import re
import uuid
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger("ai_service")

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

QUALIFY_SYSTEM = """You are an expert B2B AI SDR at a top enterprise SaaS company.
Return ONLY valid JSON (no markdown, no prose) with EXACTLY this schema:

{
  "industry": "one of: SaaS, Fintech, Healthcare, E-commerce, Manufacturing, Education, Media, Real Estate, Consulting, Other",
  "company_size": "one of: 1-10, 11-50, 51-200, 201-500, 501-1000, 1000+",
  "buying_intent": "one of: Low, Medium, High, Very High",
  "score": integer 0-100,
  "qualification_summary": "2-3 sentence executive summary",
  "key_signals": ["3-5 short bullets, < 80 chars each"],
  "recommended_action": "one of: Schedule Demo, Send Nurture Email, Assign to AE, Disqualify, Request More Info",
  "next_step_reason": "1 sentence"
}

Score rubric: 85-100 enterprise fit + explicit intent; 65-84 good fit; 40-64 mid; 0-39 poor."""

EMAIL_SYSTEM = """You are an expert B2B sales copywriter. Return ONLY JSON:
{"subject":"max 60 chars","body":"90-140 words, warm+professional, mentions their company + pain + soft CTA, plain text with \\n\\n breaks, no signature"}"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in: {text[:200]}")
    return json.loads(m.group(0))


# ---------- Heuristic fallback ----------
INTENT_WORDS_HIGH = ["budget", "approved", "purchase", "buy", "urgent", "asap", "q1", "q2", "q3", "q4", "next month", "soc2", "compliance", "vendor evaluation", "rfp", "demo"]
INTENT_WORDS_MED = ["interested", "learn more", "pricing", "evaluating", "considering", "trial", "considering", "curious"]
INDUSTRY_HINTS = {
    "fintech": "Fintech", "bank": "Fintech", "finance": "Fintech", "payments": "Fintech",
    "health": "Healthcare", "clinic": "Healthcare", "medical": "Healthcare", "pharma": "Healthcare",
    "shop": "E-commerce", "commerce": "E-commerce", "retail": "E-commerce",
    "school": "Education", "university": "Education", "edtech": "Education",
    "media": "Media", "news": "Media", "content": "Media",
    "real estate": "Real Estate", "property": "Real Estate",
    "consult": "Consulting", "advisory": "Consulting",
    "manufactur": "Manufacturing", "factory": "Manufacturing",
    "saas": "SaaS", "software": "SaaS", "platform": "SaaS",
}
SENIOR_TITLES = ["ceo", "cto", "cfo", "coo", "vp", "chief", "head", "director", "founder", "president"]


def _heuristic_qualify(lead: dict) -> dict:
    text = " ".join([str(lead.get("company") or ""), str(lead.get("message") or ""),
                     str(lead.get("job_title") or ""), str(lead.get("website") or "")]).lower()
    # Industry
    industry = "Other"
    for k, v in INDUSTRY_HINTS.items():
        if k in text: industry = v; break
    # Company size — extract number
    size = "51-200"
    m = re.search(r"(\d[\d,]*)\s*(?:employees|people|staff|ppl)", text)
    if m:
        n = int(m.group(1).replace(",", ""))
        if n < 11: size = "1-10"
        elif n < 51: size = "11-50"
        elif n < 201: size = "51-200"
        elif n < 501: size = "201-500"
        elif n < 1001: size = "501-1000"
        else: size = "1000+"
    elif lead.get("company_size_hint"):
        size = lead["company_size_hint"]
    # Intent
    high_hits = sum(1 for w in INTENT_WORDS_HIGH if w in text)
    med_hits = sum(1 for w in INTENT_WORDS_MED if w in text)
    if high_hits >= 3: intent = "Very High"
    elif high_hits >= 1: intent = "High"
    elif med_hits >= 1: intent = "Medium"
    else: intent = "Low"
    # Seniority bonus
    senior = any(t in (lead.get("job_title") or "").lower() for t in SENIOR_TITLES)
    # Score
    base = {"Very High": 88, "High": 72, "Medium": 55, "Low": 32}[intent]
    if senior: base += 8
    if size in ("501-1000", "1000+", "201-500"): base += 4
    score = max(0, min(100, base))
    action = ("Assign to AE" if score >= 80 else
              "Schedule Demo" if score >= 65 else
              "Send Nurture Email" if score >= 40 else "Disqualify")
    signals = []
    if senior: signals.append(f"Senior title detected: {lead.get('job_title')}")
    if high_hits: signals.append(f"{high_hits} explicit buying signal(s) in message")
    if size in ("201-500", "501-1000", "1000+"): signals.append(f"Mid/large company ({size})")
    if industry != "Other": signals.append(f"Industry match: {industry}")
    if not signals: signals.append("No strong signals detected — nurture recommended")
    return {
        "industry": industry, "company_size": size, "buying_intent": intent, "score": score,
        "qualification_summary": (
            f"{lead.get('name')} ({lead.get('job_title') or 'contact'}) at {lead.get('company')} — "
            f"{industry} • {size}. Intent classified as {intent} based on message signals. "
            f"Recommended: {action.lower()}."
        ),
        "key_signals": signals[:5],
        "recommended_action": action,
        "next_step_reason": f"Score {score} with {intent.lower()} intent supports this next step.",
        "_fallback": True,
    }


def _heuristic_email(lead: dict, qual: dict) -> dict:
    first = (lead.get("name") or "there").split(" ")[0]
    company = lead.get("company") or "your team"
    subject = f"Quick idea for {company}"
    body = (
        f"Hi {first},\n\n"
        f"Saw your inquiry — as {qual.get('company_size','a growing team')} in {qual.get('industry','your space')}, "
        f"you're likely dealing with slow inbound follow-up. We've helped similar teams cut response time from hours to under 60 seconds using an AI SDR.\n\n"
        f"Open to a 15-min call this week to see if it's a fit for {company}?\n\n"
        f"— The SDR Agent team"
    )
    return {"subject": subject, "body": body, "_fallback": True}


# ---------- Public API ----------
async def qualify_lead(lead: dict) -> dict:
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"qualify-{uuid.uuid4()}",
            system_message=QUALIFY_SYSTEM,
        ).with_model("openai", "gpt-5.2")
        ctx = (
            f"Name: {lead.get('name')}\nEmail: {lead.get('email')}\nCompany: {lead.get('company')}\n"
            f"Job Title: {lead.get('job_title') or 'N/A'}\nWebsite: {lead.get('website') or 'N/A'}\n"
            f"Reported Size: {lead.get('company_size_hint') or 'N/A'}\n"
            f"Message:\n{lead.get('message') or 'N/A'}\nSource: {lead.get('source') or 'website'}"
        )
        response = await chat.send_message(UserMessage(text=ctx))
        return _extract_json(response)
    except Exception as e:
        logger.warning(f"LLM qualify fell back to heuristic: {e}")
        return _heuristic_qualify(lead)


async def generate_email(lead: dict, qualification: dict) -> dict:
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"email-{uuid.uuid4()}",
            system_message=EMAIL_SYSTEM,
        ).with_model("openai", "gpt-5.2")
        ctx = (
            f"Recipient: {lead.get('name')} ({lead.get('job_title') or 'buyer'}) at {lead.get('company')}\n"
            f"Industry: {qualification.get('industry')}\nCompany Size: {qualification.get('company_size')}\n"
            f"Buying Intent: {qualification.get('buying_intent')}\nTheir message: {lead.get('message') or ''}\n"
            f"Key signals: {', '.join(qualification.get('key_signals', []))}\n"
            f"Recommended action: {qualification.get('recommended_action')}\n"
            f"You represent an AI SDR Agent SaaS that auto-qualifies inbound leads."
        )
        response = await chat.send_message(UserMessage(text=ctx))
        return _extract_json(response)
    except Exception as e:
        logger.warning(f"LLM email fell back to heuristic: {e}")
        return _heuristic_email(lead, qualification)
