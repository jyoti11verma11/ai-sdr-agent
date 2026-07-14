"""Versioned prompt storage with defaults.

Prompts live in the `prompts` collection, keyed by (owner_id, name).
`get()` seeds defaults on first read so the app is functional out of the box.
"""
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("prompt_store")

QUALIFY_PROMPT_DEFAULT = """You are an expert B2B AI SDR at a top enterprise SaaS company.
Analyse the inbound lead below and return ONLY valid JSON (no markdown fences, no prose) matching EXACTLY this schema:

{
  "industry": "one of: SaaS, Fintech, Healthcare, E-commerce, Manufacturing, Education, Media, Real Estate, Consulting, Other",
  "company_size": "one of: 1-10, 11-50, 51-200, 201-500, 501-1000, 1000+",
  "business_type": "one of: B2B SaaS, Enterprise SaaS, B2C, Marketplace, Agency, Consulting, Non-profit, Other",
  "icp_match": true or false,
  "icp_match_reasoning": "1-2 sentence explanation",
  "buying_intent": "one of: Low, Medium, High, Very High",
  "urgency": "one of: Low, Medium, High, Immediate",
  "decision_maker_probability": integer 0-100 (probability this contact can approve the purchase),
  "score": integer 0-100,
  "score_explanation": "2-3 sentences explaining exactly how you weighted signals to arrive at this score",
  "qualification_summary": "2-3 sentence executive summary",
  "key_signals": ["3-5 short bullets < 80 chars each"],
  "recommended_action": "one of: Book Demo, Call Immediately, Send Personalized Email, Add to Nurture Campaign, Reject Lead",
  "action_reasoning": "1-2 sentences explaining WHY this action beats the alternatives"
}

Scoring rubric:
- 90-100: perfect ICP + explicit budget/urgency + decision maker
- 75-89: strong ICP + high intent, decision maker or influencer
- 55-74: mid-market or exploratory, warm intent
- 35-54: peripheral fit, low urgency
- 0-34: poor fit, spam, or wrong ICP

The recommended_action must be internally consistent with the score:
- 85+ → Book Demo or Call Immediately
- 60-84 → Send Personalized Email
- 40-59 → Add to Nurture Campaign
- <40 → Reject Lead"""


OUTREACH_PROMPT_DEFAULT = """You are an expert B2B sales copywriter. Given the qualified lead below, produce a personalised outreach kit.
Return ONLY valid JSON matching EXACTLY:

{
  "subject": "email subject, max 60 chars, no clickbait, no all-caps",
  "first_email": "cold email body, 90-140 words, warm+professional, mentions their company + one specific pain from the message, ends with a soft CTA, plain text with \\n\\n paragraph breaks, no signature",
  "linkedin_message": "LinkedIn connection request or first DM, 40-70 words, conversational, references one specific detail from their profile/company",
  "followup_email": "polite follow-up email to send 3 days after the first, 60-100 words, adds new value (case study, resource) rather than repeating"
}"""


class PromptStore:
    def __init__(self, db: AsyncIOMotorDatabase, owner_id: str):
        self.db = db
        self.owner_id = owner_id

    async def get(self, name: str) -> dict:
        """Returns {template, version} — seeds default on first read."""
        doc = await self.db.prompts.find_one(
            {"owner_id": self.owner_id, "name": name}, {"_id": 0}
        )
        if doc:
            return doc
        default = QUALIFY_PROMPT_DEFAULT if name == "qualification" else OUTREACH_PROMPT_DEFAULT
        doc = {
            "owner_id": self.owner_id,
            "name": name,
            "template": default,
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.prompts.insert_one(dict(doc))
        return doc

    async def list_all(self) -> list[dict]:
        # ensure both are seeded
        await self.get("qualification")
        await self.get("outreach")
        docs = await self.db.prompts.find(
            {"owner_id": self.owner_id}, {"_id": 0}
        ).to_list(20)
        docs.sort(key=lambda d: d["name"])
        return docs

    async def update(self, name: str, template: str) -> dict:
        current = await self.get(name)
        new_version = current["version"] + 1
        updated = {
            "owner_id": self.owner_id,
            "name": name,
            "template": template,
            "version": new_version,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.prompts.replace_one(
            {"owner_id": self.owner_id, "name": name}, updated, upsert=True
        )
        return updated

    async def reset(self, name: str) -> dict:
        default = QUALIFY_PROMPT_DEFAULT if name == "qualification" else OUTREACH_PROMPT_DEFAULT
        return await self.update(name, default)
