"""AI SDR Agent — FastAPI backend."""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    UserCreate, UserLogin, UserPublic, AuthResponse,
    LeadCreate, Lead, LeadStatusUpdate, Qualification, GeneratedEmail, Activity,
    IntegrationSettings,
)
from auth import hash_password, verify_password, create_access_token, get_current_user
from services.ai_service import qualify_lead, generate_email
from services.orchestrator import IntegrationOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("sdr")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db: AsyncIOMotorDatabase = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI SDR Agent API", version="1.1.0")
api = APIRouter(prefix="/api")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(doc):
    if isinstance(doc, dict): return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, list): return [_serialize(v) for v in doc]
    if isinstance(doc, datetime): return doc.isoformat()
    return doc


# ---------- Dependency: settings + orchestrator ----------
async def _get_settings_doc(owner_id: str) -> dict:
    doc = await db.settings.find_one({"owner_id": owner_id}, {"_id": 0})
    return doc or {"owner_id": owner_id, **IntegrationSettings().model_dump()}


async def get_orchestrator(current=Depends(get_current_user)) -> IntegrationOrchestrator:
    settings = await _get_settings_doc(current["id"])
    return IntegrationOrchestrator(db, settings, current["id"])


# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "AI SDR Agent", "version": "1.1.0", "status": "ok", "time": _now_iso()}


# ---------- Auth ----------
@api.post("/auth/signup", response_model=AuthResponse)
async def signup(payload: UserCreate):
    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "id": uuid.uuid4().hex,
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
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
async def integrations_logs(
    provider: Optional[str] = Query(None),
    limit: int = 50,
    orch: IntegrationOrchestrator = Depends(get_orchestrator),
):
    return await orch.recent_logs(provider, limit)


# ---------- Leads ----------
async def _run_ai_pipeline(lead: Lead, orch: IntegrationOrchestrator) -> Lead:
    """Qualify, draft email, fire integrations. Mutates + persists."""
    # Qualify
    try:
        qual = await qualify_lead(lead.model_dump())
        lead.qualification = Qualification(**qual)
        lead.status = "qualified" if (qual.get("score") or 0) >= 50 else "disqualified"
        lead.activities.append(Activity(
            type="qualified",
            message=f"AI qualified with score {qual.get('score')}/100 — {qual.get('recommended_action')}",
            metadata={"score": qual.get("score")},
        ))
    except Exception as e:
        logger.exception("qualify failed")
        lead.activities.append(Activity(type="qualified", message=f"Qualification failed: {e}"))
        # Slack heads-up
        try:
            fail_act = await orch.notify_qualification_failure(lead.model_dump(), str(e), lead_id=lead.id)
            if fail_act: lead.activities.append(Activity(**fail_act))
        except Exception:
            logger.exception("Slack qualification-failure notify itself failed")

    # Email
    try:
        if lead.qualification and lead.qualification.score is not None:
            em = await generate_email(lead.model_dump(), lead.qualification.model_dump())
            lead.generated_email = GeneratedEmail(
                subject=em.get("subject"), body=em.get("body"),
                generated_at=datetime.now(timezone.utc),
            )
            lead.activities.append(Activity(
                type="email_generated",
                message=f"AI drafted personalized email: '{em.get('subject','')[:60]}'",
            ))
    except Exception as e:
        logger.exception("email gen failed")
        lead.activities.append(Activity(type="email_generated", message=f"Email gen failed: {e}"))

    # Integrations (only if qualified successfully)
    if lead.qualification and lead.qualification.score is not None:
        acts = await orch.run_for_lead(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
        for a in acts:
            lead.activities.append(Activity(**a))

    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()), upsert=True)
    return lead


@api.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate,
                      current=Depends(get_current_user),
                      orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    lead = Lead(owner_id=current["id"], **payload.model_dump())
    lead.status = "qualifying"
    lead.activities.append(Activity(type="created", message=f"Lead captured from {lead.source}"))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    return await _run_ai_pipeline(lead, orch)


@api.post("/leads/public", response_model=Lead)
async def create_lead_public(payload: LeadCreate, owner_email: str = Query(...)):
    owner = await db.users.find_one({"email": owner_email.lower()}, {"_id": 0})
    if not owner: raise HTTPException(status_code=404, detail="Account not found")
    lead = Lead(owner_id=owner["id"], **payload.model_dump())
    lead.status = "qualifying"
    lead.activities.append(Activity(type="created", message=f"Public lead captured from {lead.source}"))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    settings = await _get_settings_doc(owner["id"])
    orch = IntegrationOrchestrator(db, settings, owner["id"])
    return await _run_ai_pipeline(lead, orch)


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


@api.get("/leads/{lead_id}", response_model=Lead)
async def get_lead(lead_id: str, current=Depends(get_current_user)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    return doc


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

    # sync status to HubSpot if we have a contact_id
    contact_id = _extract_contact_id(lead)
    if contact_id and orch.hubspot.is_configured:
        res = await orch.hubspot.sync_status(contact_id, payload.status)
        act = await orch._log(res, lead_id=lead.id, activity_type="hubspot_status_sync")
        lead.activities.append(Activity(**act))

    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.post("/leads/{lead_id}/regenerate-email", response_model=Lead)
async def regen_email(lead_id: str, current=Depends(get_current_user)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    if not lead.qualification or lead.qualification.score is None:
        raise HTTPException(status_code=400, detail="Lead not qualified yet")
    em = await generate_email(lead.model_dump(), lead.qualification.model_dump())
    lead.generated_email = GeneratedEmail(
        subject=em.get("subject"), body=em.get("body"),
        generated_at=datetime.now(timezone.utc),
    )
    lead.activities.append(Activity(type="email_generated", message="AI regenerated personalized email"))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


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
    for a in acts:
        lead.activities.append(Activity(**a))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current=Depends(get_current_user)):
    r = await db.leads.delete_one({"id": lead_id, "owner_id": current["id"]})
    if r.deleted_count == 0: raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}


def _extract_contact_id(lead: Lead) -> Optional[str]:
    """Walk recent activities to find the HubSpot contact_id from the create_contact log."""
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
