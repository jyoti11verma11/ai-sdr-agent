"""AI SDR Agent — FastAPI backend."""
import os
import uuid
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    UserCreate, UserLogin, UserPublic, AuthResponse,
    LeadCreate, Lead, LeadStatusUpdate, Qualification, GeneratedEmail, Outreach, Activity,
    IntegrationSettings, PromptUpdate, PromptTestInput,
)
from auth import hash_password, verify_password, create_access_token, get_current_user
from services.ai_service import AIService
from services.prompt_store import PromptStore
from services.orchestrator import IntegrationOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("sdr")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db: AsyncIOMotorDatabase = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI SDR Agent API", version="1.2.0")
api = APIRouter(prefix="/api")


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


def _serialize(doc):
    if isinstance(doc, dict): return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, list): return [_serialize(v) for v in doc]
    if isinstance(doc, datetime): return doc.isoformat()
    return doc


# ---------- Dependencies ----------
async def _get_settings_doc(owner_id: str) -> dict:
    doc = await db.settings.find_one({"owner_id": owner_id}, {"_id": 0})
    return doc or {"owner_id": owner_id, **IntegrationSettings().model_dump()}


async def get_orchestrator(current=Depends(get_current_user)) -> IntegrationOrchestrator:
    settings = await _get_settings_doc(current["id"])
    return IntegrationOrchestrator(db, settings, current["id"])


def get_ai_service_for(owner_id: str) -> AIService:
    return AIService(db, owner_id)


# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "AI SDR Agent", "version": "1.2.0", "status": "ok", "time": _now_iso()}


# ---------- Auth ----------
@api.post("/auth/signup", response_model=AuthResponse)
async def signup(payload: UserCreate):
    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "id": uuid.uuid4().hex, "email": payload.email.lower(),
        "full_name": payload.full_name, "password_hash": hash_password(payload.password),
        "created_at": _now_iso(),
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(token=token, user=UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        created_at=datetime.fromisoformat(user["created_at"])))


@api.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(token=token, user=UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"]))


@api.get("/auth/me", response_model=UserPublic)
async def me(current=Depends(get_current_user)):
    user = await db.users.find_one({"id": current["id"]}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"])


# ---------- Settings ----------
@api.get("/settings")
async def get_settings(current=Depends(get_current_user)):
    return await _get_settings_doc(current["id"])


@api.put("/settings")
async def update_settings(payload: IntegrationSettings, current=Depends(get_current_user)):
    data = payload.model_dump()
    data["owner_id"] = current["id"]
    await db.settings.update_one({"owner_id": current["id"]}, {"$set": data}, upsert=True)
    return data


# ---------- Integrations ----------
@api.get("/integrations/status")
async def integrations_status(orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    return await orch.status()


@api.post("/integrations/{provider}/test")
async def integrations_test(provider: str, orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    if provider not in ("hubspot", "slack", "n8n"):
        raise HTTPException(status_code=400, detail="Unknown provider")
    return await orch.test_provider(provider)


@api.get("/integrations/logs")
async def integrations_logs(provider: Optional[str] = Query(None), limit: int = 50,
                            orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    return await orch.recent_logs(provider, limit)


# ---------- Prompts (AI Playground) ----------
@api.get("/prompts")
async def list_prompts(current=Depends(get_current_user)):
    return await PromptStore(db, current["id"]).list_all()


@api.get("/prompts/{name}")
async def get_prompt(name: str, current=Depends(get_current_user)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    return await PromptStore(db, current["id"]).get(name)


@api.put("/prompts/{name}")
async def update_prompt(name: str, payload: PromptUpdate, current=Depends(get_current_user)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    return await PromptStore(db, current["id"]).update(name, payload.template)


@api.post("/prompts/{name}/reset")
async def reset_prompt(name: str, current=Depends(get_current_user)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    return await PromptStore(db, current["id"]).reset(name)


@api.post("/prompts/{name}/test")
async def test_prompt(name: str, payload: PromptTestInput, current=Depends(get_current_user)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    ai = get_ai_service_for(current["id"])
    lead = payload.lead.model_dump()
    qual = payload.qualification.model_dump() if payload.qualification else None
    if name == "qualification":
        return await ai.qualify(lead, lead_id=None)
    return await ai.generate_outreach(lead, qual or {}, lead_id=None, decision_type="test")


# ---------- Leads pipeline (background) ----------
async def _run_pipeline(lead_id: str, owner_id: str):
    """Background task: qualify → outreach → integrations. Updates lead in-place."""
    try:
        doc = await db.leads.find_one({"id": lead_id, "owner_id": owner_id}, {"_id": 0})
        if not doc:
            logger.warning(f"pipeline: lead {lead_id} vanished")
            return
        lead = Lead(**doc)
        lead.processing_status = "analyzing"
        lead.status = "qualifying"
        await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))

        ai = get_ai_service_for(owner_id)
        settings = await _get_settings_doc(owner_id)
        orch = IntegrationOrchestrator(db, settings, owner_id)

        # Qualify
        try:
            qual = await ai.qualify(lead.model_dump(), lead_id=lead.id)
            lead.qualification = Qualification(**qual)
            lead.status = "qualified" if (qual.get("score") or 0) >= 50 else "disqualified"
            lead.activities.append(Activity(
                type="qualified",
                message=f"AI qualified with score {qual.get('score')}/100 — {qual.get('recommended_action')}",
                metadata={"score": qual.get("score"), "action": qual.get("recommended_action")},
            ))
        except Exception as e:
            logger.exception("pipeline qualify failed")
            lead.processing_status = "failed"
            lead.activities.append(Activity(type="qualified", message=f"Qualification failed: {e}"))
            try:
                fail_act = await orch.notify_qualification_failure(lead.model_dump(), str(e), lead_id=lead.id)
                if fail_act: lead.activities.append(Activity(**fail_act))
            except Exception: pass
            lead.updated_at = datetime.now(timezone.utc)
            await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
            return

        # Outreach kit
        try:
            out = await ai.generate_outreach(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
            lead.outreach = Outreach(
                subject=out.get("subject"),
                first_email=out.get("first_email") or out.get("body"),
                linkedin_message=out.get("linkedin_message"),
                followup_email=out.get("followup_email"),
                generated_at=datetime.now(timezone.utc),
            )
            # legacy field for older UI
            lead.generated_email = GeneratedEmail(
                subject=lead.outreach.subject, body=lead.outreach.first_email,
                generated_at=lead.outreach.generated_at,
            )
            lead.activities.append(Activity(
                type="email_generated",
                message=f"AI drafted outreach kit: '{(lead.outreach.subject or '')[:60]}'",
            ))
        except Exception as e:
            logger.exception("outreach failed")
            lead.activities.append(Activity(type="email_generated", message=f"Outreach gen failed: {e}"))

        # Integrations
        try:
            acts = await orch.run_for_lead(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
            for a in acts: lead.activities.append(Activity(**a))
        except Exception as e:
            logger.exception("integrations failed")
            lead.activities.append(Activity(type="integration_error", message=str(e)))

        lead.processing_status = "qualified" if lead.qualification.score is not None else "failed"
        lead.updated_at = datetime.now(timezone.utc)
        await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
        logger.info(f"pipeline: lead {lead_id} done, status={lead.processing_status}, score={lead.qualification.score}")
    except Exception as e:
        logger.exception(f"pipeline unhandled: {e}")


@api.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate, bg: BackgroundTasks, current=Depends(get_current_user)):
    lead = Lead(owner_id=current["id"], **payload.model_dump())
    lead.status = "qualifying"
    lead.processing_status = "pending"
    lead.activities.append(Activity(type="created", message=f"Lead captured from {lead.source}"))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    bg.add_task(_run_pipeline, lead.id, current["id"])
    return lead


@api.post("/leads/public", response_model=Lead)
async def create_lead_public(payload: LeadCreate, bg: BackgroundTasks, owner_email: str = Query(...)):
    owner = await db.users.find_one({"email": owner_email.lower()}, {"_id": 0})
    if not owner: raise HTTPException(status_code=404, detail="Account not found")
    lead = Lead(owner_id=owner["id"], **payload.model_dump())
    lead.status = "qualifying"
    lead.processing_status = "pending"
    lead.activities.append(Activity(type="created", message=f"Public lead captured from {lead.source}"))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    bg.add_task(_run_pipeline, lead.id, owner["id"])
    return lead


@api.get("/leads", response_model=List[Lead])
async def list_leads(current=Depends(get_current_user), status: Optional[str] = None,
                     q: Optional[str] = None, limit: int = 200):
    query: dict = {"owner_id": current["id"]}
    if status: query["status"] = status
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"company": {"$regex": q, "$options": "i"}},
        ]
    return await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)


@api.get("/leads/status-counts")
async def status_counts(current=Depends(get_current_user)):
    cur = db.leads.aggregate([
        {"$match": {"owner_id": current["id"]}},
        {"$group": {"_id": "$processing_status", "n": {"$sum": 1}}},
    ])
    counts = {"pending": 0, "analyzing": 0, "qualified": 0, "failed": 0}
    async for row in cur:
        k = row["_id"] or "pending"
        if k in counts: counts[k] = row["n"]
        else: counts["qualified"] += row["n"]  # legacy leads
    return counts


@api.get("/leads/{lead_id}", response_model=Lead)
async def get_lead(lead_id: str, current=Depends(get_current_user)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    return doc


@api.get("/leads/{lead_id}/decisions")
async def lead_decisions(lead_id: str, current=Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 1})
    if not lead: raise HTTPException(status_code=404, detail="Lead not found")
    return await db.ai_decisions.find(
        {"owner_id": current["id"], "lead_id": lead_id}, {"_id": 0}
    ).sort("at", -1).to_list(100)


@api.patch("/leads/{lead_id}/status", response_model=Lead)
async def update_status(lead_id: str, payload: LeadStatusUpdate,
                        current=Depends(get_current_user),
                        orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    old = lead.status
    lead.status = payload.status
    lead.activities.append(Activity(type="status_change", message=f"Status changed from {old} to {payload.status}"))

    contact_id = _extract_contact_id(lead)
    if contact_id and orch.hubspot.is_configured:
        res = await orch.hubspot.sync_status(contact_id, payload.status)
        act = await orch._log(res, lead_id=lead.id, activity_type="hubspot_status_sync")
        lead.activities.append(Activity(**act))

    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.post("/leads/{lead_id}/regenerate", response_model=Lead)
async def regenerate(lead_id: str,
                      type: str = Query("all", pattern="^(all|first_email|linkedin_message|followup_email|email)$"),
                      current=Depends(get_current_user)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    if not lead.qualification or lead.qualification.score is None:
        raise HTTPException(status_code=400, detail="Lead not qualified yet")

    ai = get_ai_service_for(current["id"])
    decision_type = {
        "first_email": "regenerate_email", "email": "regenerate_email",
        "linkedin_message": "regenerate_linkedin",
        "followup_email": "regenerate_followup",
        "all": "outreach",
    }[type]
    out = await ai.generate_outreach(lead.model_dump(), lead.qualification.model_dump(),
                                      lead_id=lead.id, decision_type=decision_type)

    if not lead.outreach: lead.outreach = Outreach()
    if type in ("all", "first_email", "email"):
        lead.outreach.subject = out.get("subject") or lead.outreach.subject
        lead.outreach.first_email = out.get("first_email") or out.get("body") or lead.outreach.first_email
    if type in ("all", "linkedin_message"):
        lead.outreach.linkedin_message = out.get("linkedin_message") or lead.outreach.linkedin_message
    if type in ("all", "followup_email"):
        lead.outreach.followup_email = out.get("followup_email") or lead.outreach.followup_email
    lead.outreach.generated_at = datetime.now(timezone.utc)

    lead.generated_email = GeneratedEmail(
        subject=lead.outreach.subject, body=lead.outreach.first_email,
        generated_at=lead.outreach.generated_at,
    )
    lead.activities.append(Activity(
        type="email_generated",
        message=f"AI regenerated {type.replace('_',' ')}",
    ))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


# Backwards-compat alias
@api.post("/leads/{lead_id}/regenerate-email", response_model=Lead)
async def regenerate_email_alias(lead_id: str, current=Depends(get_current_user)):
    return await regenerate(lead_id, type="first_email", current=current)


@api.post("/leads/{lead_id}/retry-sync", response_model=Lead)
async def retry_sync(lead_id: str,
                     current=Depends(get_current_user),
                     orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    if not lead.qualification or lead.qualification.score is None:
        raise HTTPException(status_code=400, detail="Lead has no qualification to sync")
    acts = await orch.run_for_lead(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
    for a in acts: lead.activities.append(Activity(**a))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current=Depends(get_current_user)):
    r = await db.leads.delete_one({"id": lead_id, "owner_id": current["id"]})
    if r.deleted_count == 0: raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}


def _extract_contact_id(lead: Lead) -> Optional[str]:
    for a in reversed(lead.activities or []):
        md = a.metadata or {}
        if md.get("provider") == "hubspot" and md.get("action") == "create_contact":
            data = md.get("data") or {}
            if data.get("id"): return data["id"]
    return None


# ---------- Analytics ----------
@api.get("/analytics/summary")
async def analytics_summary(current=Depends(get_current_user)):
    owner = current["id"]
    leads = await db.leads.find({"owner_id": owner}, {"_id": 0}).to_list(2000)
    total = len(leads)
    qualified = sum(1 for l in leads if l.get("status") == "qualified" or (l.get("qualification", {}).get("score") or 0) >= 50)
    converted = sum(1 for l in leads if l.get("status") == "converted")
    scores = [l.get("qualification", {}).get("score") or 0 for l in leads if l.get("qualification", {}).get("score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    conv_rate = round((converted / total) * 100, 1) if total else 0
    qualified_rate = round((qualified / total) * 100, 1) if total else 0

    buckets = {"0-39": 0, "40-64": 0, "65-84": 0, "85-100": 0}
    for s in scores:
        if s < 40: buckets["0-39"] += 1
        elif s < 65: buckets["40-64"] += 1
        elif s < 85: buckets["65-84"] += 1
        else: buckets["85-100"] += 1
    score_distribution = [{"bucket": k, "count": v} for k, v in buckets.items()]

    ind: dict = {}
    for l in leads:
        i = (l.get("qualification") or {}).get("industry") or "Unknown"
        ind[i] = ind.get(i, 0) + 1
    by_industry = [{"industry": k, "count": v} for k, v in sorted(ind.items(), key=lambda x: -x[1])[:8]]

    from collections import defaultdict
    daily = defaultdict(int)
    for l in leads:
        c = l.get("created_at")
        day = c[:10] if isinstance(c, str) else (c.date().isoformat() if c else None)
        if day: daily[day] += 1
    timeline = sorted([{"date": k, "count": v} for k, v in daily.items()], key=lambda x: x["date"])[-14:]

    recent = sorted(leads, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    insights = []
    for l in recent:
        q_ = l.get("qualification") or {}
        if q_.get("qualification_summary"):
            insights.append({
                "lead_id": l["id"], "company": l["company"], "name": l["name"],
                "score": q_.get("score"), "summary": q_.get("qualification_summary"),
                "action": q_.get("recommended_action"),
            })

    return {
        "total_leads": total, "qualified_leads": qualified,
        "conversion_rate": conv_rate, "qualified_rate": qualified_rate,
        "avg_score": avg_score, "score_distribution": score_distribution,
        "by_industry": by_industry, "timeline": timeline, "ai_insights": insights,
    }


@api.get("/analytics/activity")
async def recent_activity(current=Depends(get_current_user), limit: int = 20):
    leads = await db.leads.find({"owner_id": current["id"]}, {"_id": 0}).to_list(500)
    acts = []
    for l in leads:
        for a in l.get("activities", []):
            acts.append({**a, "lead_id": l["id"], "lead_name": l["name"], "company": l["company"]})
    acts.sort(key=lambda x: x.get("at", ""), reverse=True)
    return acts[:limit]


@api.get("/analytics/ai")
async def analytics_ai(current=Depends(get_current_user)):
    owner = current["id"]
    leads = await db.leads.find({"owner_id": owner}, {"_id": 0}).to_list(2000)
    decisions = await db.ai_decisions.find({"owner_id": owner}, {"_id": 0}).to_list(5000)

    scores = [l.get("qualification", {}).get("score") for l in leads if l.get("qualification", {}).get("score") is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    high_intent = sum(1 for l in leads if (l.get("qualification") or {}).get("buying_intent") in ("High", "Very High"))

    # Industry distribution (percentage)
    ind: dict = {}
    for l in leads:
        i = (l.get("qualification") or {}).get("industry") or "Unknown"
        ind[i] = ind.get(i, 0) + 1
    total = sum(ind.values()) or 1
    industry_distribution = sorted([
        {"industry": k, "count": v, "pct": round(v / total * 100, 1)}
        for k, v in ind.items() if k != "Unknown"
    ], key=lambda x: -x["count"])[:8]

    # Top ICP matches
    icp_leads = sorted(
        [l for l in leads if (l.get("qualification") or {}).get("icp_match") is True],
        key=lambda l: -(l.get("qualification", {}).get("score") or 0),
    )[:5]
    top_icp = [{
        "lead_id": l["id"], "name": l["name"], "company": l["company"],
        "score": l.get("qualification", {}).get("score"),
        "industry": l.get("qualification", {}).get("industry"),
        "reason": l.get("qualification", {}).get("icp_match_reasoning"),
    } for l in icp_leads]

    # Qualification success rate
    qual_decisions = [d for d in decisions if d.get("decision_type") == "qualification"]
    success = sum(1 for d in qual_decisions if d.get("status") == "success")
    total_qd = len(qual_decisions) or 0
    success_rate = round((success / total_qd) * 100, 1) if total_qd else 0

    # Avg processing time (qualification latency)
    latencies = [d.get("latency_ms") for d in qual_decisions if d.get("latency_ms")]
    avg_processing_ms = round(sum(latencies) / len(latencies)) if latencies else 0

    # Prompt versions in use
    prompt_versions = {}
    for d in qual_decisions:
        prompt_versions[d.get("prompt_name")] = max(prompt_versions.get(d.get("prompt_name"), 0), d.get("prompt_version") or 1)

    return {
        "avg_ai_score": avg,
        "high_intent_leads": high_intent,
        "industry_distribution": industry_distribution,
        "top_icp_matches": top_icp,
        "qualification_success_rate": success_rate,
        "qualification_success_count": success,
        "qualification_total": total_qd,
        "avg_processing_ms": avg_processing_ms,
        "prompt_versions": prompt_versions,
        "total_ai_decisions": len(decisions),
    }


# ---------- Register + CORS ----------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
