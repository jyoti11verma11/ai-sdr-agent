"""AI SDR Agent — FastAPI backend v1.3.0 (Phase 4 team + pipeline + email + meetings)."""
import os
import re
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    UserCreate, UserLogin, UserPublic, AuthResponse, Workspace,
    InviteCreate, MemberRoleUpdate,
    LeadCreate, Lead, LeadStatusUpdate, LeadStageUpdate, LeadAssignUpdate,
    Qualification, GeneratedEmail, Outreach, Activity, StageChange, Note, NoteCreate,
    EmailMessage, EmailSendInput, Meeting, MeetingProposeInput, MeetingConfirmInput,
    IntegrationSettings, AssignmentRuleInput, PromptUpdate, PromptTestInput,
    PIPELINE_STAGES, ROLE_HIERARCHY,
)
from auth import hash_password, verify_password, create_access_token, get_current_user, require_role
from services.ai_service import AIService
from services.prompt_store import PromptStore
from services.orchestrator import IntegrationOrchestrator
from services.assignment import AssignmentEngine
from services.notify import NotificationService, AuditService
from services.email_service import EmailService
from services.meetings import recommend_slots, google_calendar_url, build_ics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("sdr")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db: AsyncIOMotorDatabase = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI SDR Agent API", version="1.3.0",
              description="Production-grade AI SDR platform — team, pipeline, email, meetings, RBAC.")
api = APIRouter(prefix="/api")


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


def _serialize(doc):
    if isinstance(doc, dict): return {k: _serialize(v) for k, v in doc.items()}
    if isinstance(doc, list): return [_serialize(v) for v in doc]
    if isinstance(doc, datetime): return doc.isoformat()
    return doc


def _parse_dt(v):
    if isinstance(v, datetime): return v
    if isinstance(v, str):
        try: return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception: return None
    return None


# ---------- Dependencies ----------
async def _get_settings_doc(workspace_id: str) -> dict:
    doc = await db.settings.find_one({"owner_id": workspace_id}, {"_id": 0})
    return doc or {"owner_id": workspace_id, **IntegrationSettings().model_dump()}


async def get_orchestrator(current=Depends(get_current_user)) -> IntegrationOrchestrator:
    return IntegrationOrchestrator(db, await _get_settings_doc(current["workspace_id"]), current["workspace_id"])


def get_ai_service_for(workspace_id: str) -> AIService:
    return AIService(db, workspace_id)


def get_audit(current=Depends(get_current_user)) -> AuditService:
    return AuditService(db, current["workspace_id"], current)


def get_notify(current=Depends(get_current_user)) -> NotificationService:
    return NotificationService(db, current["workspace_id"])


# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "AI SDR Agent", "version": "1.3.0", "status": "ok", "time": _now_iso()}


# ---------- Auth + workspace ----------
@api.post("/auth/signup", response_model=AuthResponse)
async def signup(payload: UserCreate):
    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = uuid.uuid4().hex
    role = "admin"
    workspace_id = user_id
    workspace_name = f"{payload.full_name.split(' ')[0]}'s workspace"

    if payload.invite_token:
        inv = await db.invites.find_one({"token": payload.invite_token, "accepted": False}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=400, detail="Invalid or used invite token")
        if inv["email"].lower() != payload.email.lower():
            raise HTTPException(status_code=400, detail="Invite email doesn't match")
        workspace_id = inv["workspace_id"]
        role = inv["role"]
        ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
        workspace_name = ws.get("name") if ws else workspace_name
        await db.invites.update_one({"token": payload.invite_token}, {"$set": {"accepted": True, "accepted_at": _now_iso()}})
    else:
        await db.workspaces.insert_one({
            "id": workspace_id, "name": workspace_name,
            "owner_user_id": user_id, "rr_index": 0,
            "created_at": _now_iso(),
        })

    user = {
        "id": user_id, "email": payload.email.lower(),
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
        "workspace_id": workspace_id, "role": role,
        "created_at": _now_iso(),
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], user["email"], workspace_id, role)
    return AuthResponse(token=token, user=UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        role=role, workspace_id=workspace_id, workspace_name=workspace_name,
        created_at=datetime.fromisoformat(user["created_at"])))


@api.post("/auth/login", response_model=AuthResponse)
async def login(payload: UserLogin):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    workspace_id = user.get("workspace_id") or user["id"]
    role = user.get("role") or "admin"
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    ws_name = ws.get("name") if ws else "Workspace"
    token = create_access_token(user["id"], user["email"], workspace_id, role)
    return AuthResponse(token=token, user=UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        role=role, workspace_id=workspace_id, workspace_name=ws_name,
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"]))


@api.get("/auth/me", response_model=UserPublic)
async def me(current=Depends(get_current_user)):
    user = await db.users.find_one({"id": current["id"]}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(status_code=404, detail="User not found")
    ws = await db.workspaces.find_one({"id": current["workspace_id"]}, {"_id": 0})
    return UserPublic(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        role=user.get("role") or "admin",
        workspace_id=current["workspace_id"],
        workspace_name=(ws or {}).get("name"),
        created_at=datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"])


# ---------- Workspace / Team ----------
@api.get("/workspace/members")
async def list_members(current=Depends(get_current_user)):
    users = await db.users.find(
        {"workspace_id": current["workspace_id"]},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", 1).to_list(500)
    return [{"user_id": u["id"], "email": u["email"], "full_name": u["full_name"],
             "role": u.get("role") or "admin"} for u in users]


@api.post("/workspace/invites")
async def create_invite(payload: InviteCreate,
                         current=Depends(require_role("admin", "sales_manager")),
                         audit: AuditService = Depends(get_audit)):
    if await db.users.find_one({"email": payload.email.lower(), "workspace_id": current["workspace_id"]}):
        raise HTTPException(status_code=400, detail="User already in workspace")
    inv = {
        "id": uuid.uuid4().hex, "workspace_id": current["workspace_id"],
        "email": payload.email.lower(), "role": payload.role,
        "invited_by": current["id"], "token": uuid.uuid4().hex,
        "accepted": False, "created_at": _now_iso(),
    }
    await db.invites.insert_one(dict(inv))
    await audit.log(action="create.invite", resource_type="invite", resource_id=inv["id"],
                     new_value={"email": inv["email"], "role": inv["role"]})
    return inv


@api.get("/workspace/invites")
async def list_invites(current=Depends(require_role("admin", "sales_manager"))):
    return await db.invites.find({"workspace_id": current["workspace_id"], "accepted": False},
                                   {"_id": 0}).sort("created_at", -1).to_list(50)


@api.delete("/workspace/invites/{invite_id}")
async def revoke_invite(invite_id: str, current=Depends(require_role("admin", "sales_manager")),
                          audit: AuditService = Depends(get_audit)):
    r = await db.invites.delete_one({"id": invite_id, "workspace_id": current["workspace_id"]})
    if r.deleted_count == 0: raise HTTPException(status_code=404, detail="Invite not found")
    await audit.log(action="delete.invite", resource_type="invite", resource_id=invite_id)
    return {"ok": True}


@api.patch("/workspace/members/{user_id}")
async def update_member_role(user_id: str, payload: MemberRoleUpdate,
                               current=Depends(require_role("admin")),
                               audit: AuditService = Depends(get_audit)):
    if user_id == current["id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    old = await db.users.find_one({"id": user_id, "workspace_id": current["workspace_id"]}, {"_id": 0})
    if not old: raise HTTPException(status_code=404, detail="Member not found")
    await db.users.update_one({"id": user_id}, {"$set": {"role": payload.role}})
    await audit.log(action="update.member_role", resource_type="user", resource_id=user_id,
                     old_value={"role": old.get("role")}, new_value={"role": payload.role})
    return {"ok": True}


# ---------- Settings ----------
@api.get("/settings")
async def get_settings(current=Depends(get_current_user)):
    return await _get_settings_doc(current["workspace_id"])


@api.put("/settings")
async def update_settings(payload: IntegrationSettings,
                            current=Depends(require_role("admin", "sales_manager")),
                            audit: AuditService = Depends(get_audit)):
    old = await _get_settings_doc(current["workspace_id"])
    data = payload.model_dump()
    data["owner_id"] = current["workspace_id"]
    await db.settings.update_one({"owner_id": current["workspace_id"]}, {"$set": data}, upsert=True)
    await audit.log(action="update.settings", resource_type="settings",
                     old_value={k: bool(v) if "token" in k or "key" in k or "webhook" in k else v for k, v in old.items() if k != "_id"},
                     new_value={k: bool(v) if "token" in k or "key" in k or "webhook" in k else v for k, v in data.items()})
    return data


# ---------- Integrations ----------
@api.get("/integrations/status")
async def integrations_status(orch: IntegrationOrchestrator = Depends(get_orchestrator),
                                current=Depends(get_current_user)):
    base = await orch.status()
    email_svc = EmailService(await _get_settings_doc(current["workspace_id"]))
    base["resend"] = {
        "configured": email_svc.is_configured,
        "enabled": True,
        "mode": "live" if email_svc.is_configured else "mock",
        "last_sync": None, "last_status": None, "last_message": None,
    }
    return base


@api.post("/integrations/{provider}/test")
async def integrations_test(provider: str, current=Depends(require_role("admin", "sales_manager")),
                              orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    if provider == "resend":
        settings = await _get_settings_doc(current["workspace_id"])
        return await EmailService(settings).test_connection()
    if provider not in ("hubspot", "slack", "n8n"):
        raise HTTPException(status_code=400, detail="Unknown provider")
    return await orch.test_provider(provider)


@api.get("/integrations/logs")
async def integrations_logs(provider: Optional[str] = Query(None), limit: int = 50,
                              orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    return await orch.recent_logs(provider, limit)


# ---------- Prompts ----------
@api.get("/prompts")
async def list_prompts(current=Depends(get_current_user)):
    return await PromptStore(db, current["workspace_id"]).list_all()


@api.get("/prompts/{name}")
async def get_prompt(name: str, current=Depends(get_current_user)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    return await PromptStore(db, current["workspace_id"]).get(name)


@api.put("/prompts/{name}")
async def update_prompt(name: str, payload: PromptUpdate,
                          current=Depends(require_role("admin", "sales_manager")),
                          audit: AuditService = Depends(get_audit)):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    old = await PromptStore(db, current["workspace_id"]).get(name)
    new = await PromptStore(db, current["workspace_id"]).update(name, payload.template)
    await audit.log(action="update.prompt", resource_type="prompt", resource_id=name,
                     old_value={"version": old["version"]}, new_value={"version": new["version"]})
    return new


@api.post("/prompts/{name}/reset")
async def reset_prompt(name: str, current=Depends(require_role("admin", "sales_manager"))):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    return await PromptStore(db, current["workspace_id"]).reset(name)


@api.post("/prompts/{name}/test")
async def test_prompt(name: str, payload: PromptTestInput,
                        current=Depends(require_role("admin", "sales_manager"))):
    if name not in ("qualification", "outreach"):
        raise HTTPException(status_code=404, detail="Unknown prompt")
    ai = get_ai_service_for(current["workspace_id"])
    lead = payload.lead.model_dump()
    qual = payload.qualification.model_dump() if payload.qualification else None
    if name == "qualification": return await ai.qualify(lead, lead_id=None)
    if not qual: qual = await ai.qualify(lead, lead_id=None)
    return await ai.generate_outreach(lead, qual, lead_id=None, decision_type="test")


# ---------- Assignment rules ----------
@api.get("/assignment/rules")
async def list_rules(current=Depends(get_current_user)):
    return await db.assignment_rules.find({"workspace_id": current["workspace_id"]}, {"_id": 0}) \
        .sort("priority", 1).to_list(200)


@api.post("/assignment/rules")
async def create_rule(payload: AssignmentRuleInput,
                        current=Depends(require_role("admin", "sales_manager")),
                        audit: AuditService = Depends(get_audit)):
    r = payload.model_dump()
    r["id"] = uuid.uuid4().hex
    r["workspace_id"] = current["workspace_id"]
    await db.assignment_rules.insert_one(dict(r))
    await audit.log(action="create.assignment_rule", resource_type="assignment_rule",
                     resource_id=r["id"], new_value=r)
    return r


@api.delete("/assignment/rules/{rule_id}")
async def delete_rule(rule_id: str, current=Depends(require_role("admin", "sales_manager")),
                        audit: AuditService = Depends(get_audit)):
    d = await db.assignment_rules.delete_one({"id": rule_id, "workspace_id": current["workspace_id"]})
    if d.deleted_count == 0: raise HTTPException(status_code=404, detail="Rule not found")
    await audit.log(action="delete.assignment_rule", resource_type="assignment_rule", resource_id=rule_id)
    return {"ok": True}


# ---------- Lead pipeline (background) ----------
async def _run_pipeline(lead_id: str, workspace_id: str, creator_id: str | None):
    try:
        doc = await db.leads.find_one({"id": lead_id, "owner_id": workspace_id}, {"_id": 0})
        if not doc: return
        lead = Lead(**doc)
        lead.processing_status = "analyzing"; lead.status = "qualifying"
        await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))

        ai = get_ai_service_for(workspace_id)
        settings = await _get_settings_doc(workspace_id)
        orch = IntegrationOrchestrator(db, settings, workspace_id)
        notify = NotificationService(db, workspace_id)

        # Qualify
        try:
            qual = await ai.qualify(lead.model_dump(), lead_id=lead.id)
            lead.qualification = Qualification(**qual)
            lead.status = "qualified" if (qual.get("score") or 0) >= 50 else "disqualified"
            if lead.status == "qualified" and lead.pipeline_stage == "new":
                lead.pipeline_stage = "qualified"
                lead.stage_history.append(StageChange(from_stage="new", to_stage="qualified",
                                                       by_user_id=None, by_user_name="AI"))
            lead.activities.append(Activity(type="qualified",
                message=f"AI qualified with score {qual.get('score')}/100 — {qual.get('recommended_action')}",
                metadata={"score": qual.get("score"), "action": qual.get("recommended_action")}))
        except Exception as e:
            logger.exception("qualify failed")
            lead.processing_status = "failed"
            lead.activities.append(Activity(type="qualified", message=f"Qualification failed: {e}"))
            try:
                fail_act = await orch.notify_qualification_failure(lead.model_dump(), str(e), lead_id=lead.id)
                if fail_act: lead.activities.append(Activity(**fail_act))
            except Exception: pass
            lead.updated_at = datetime.now(timezone.utc)
            await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
            return

        # Assignment
        engine = AssignmentEngine(db, workspace_id)
        assignee_id, reason = await engine.assign(lead.model_dump())
        if assignee_id:
            lead.assigned_to = assignee_id
            lead.assignment_reason = reason
            assignee = await db.users.find_one({"id": assignee_id}, {"_id": 0})
            lead.activities.append(Activity(type="assigned", message=f"Assigned to {assignee['full_name']} — {reason}",
                                              metadata={"user_id": assignee_id}))
            await notify.push(user_id=assignee_id, kind="lead_assigned",
                title=f"New lead assigned: {lead.name}",
                body=f"{lead.company} · Score {lead.qualification.score} · {reason}",
                lead_id=lead.id)

        # Outreach
        try:
            out = await ai.generate_outreach(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
            lead.outreach = Outreach(
                subject=out.get("subject"),
                first_email=out.get("first_email") or out.get("body"),
                linkedin_message=out.get("linkedin_message"),
                followup_email=out.get("followup_email"),
                generated_at=datetime.now(timezone.utc))
            lead.generated_email = GeneratedEmail(subject=lead.outreach.subject, body=lead.outreach.first_email,
                                                     generated_at=lead.outreach.generated_at)
            lead.activities.append(Activity(type="email_generated",
                message=f"AI drafted outreach kit: '{(lead.outreach.subject or '')[:60]}'"))
        except Exception as e:
            logger.exception("outreach failed")
            lead.activities.append(Activity(type="email_generated", message=f"Outreach gen failed: {e}"))

        # Integrations
        try:
            acts = await orch.run_for_lead(lead.model_dump(), lead.qualification.model_dump(), lead_id=lead.id)
            for a in acts:
                lead.activities.append(Activity(**a))
                if (a.get("metadata") or {}).get("status") == "error":
                    kind = "webhook_failed" if "n8n" in a["type"] else ("slack_failed" if "slack" in a["type"] else "webhook_failed")
                    for m in await db.users.find({"workspace_id": workspace_id, "role": {"$in": ["admin", "sales_manager"]}}, {"_id": 0}).to_list(50):
                        await notify.push(user_id=m["id"], kind=kind,
                            title=f"Integration failed: {a['type']}", body=a["message"], lead_id=lead.id)
        except Exception as e:
            lead.activities.append(Activity(type="integration_error", message=str(e)))

        # Qualification-done notification
        if creator_id:
            await notify.push(user_id=creator_id, kind="qualification_done",
                title=f"Qualification complete: {lead.name}",
                body=f"Score {lead.qualification.score} · {lead.qualification.recommended_action}",
                lead_id=lead.id)

        lead.processing_status = "qualified" if lead.qualification.score is not None else "failed"
        lead.updated_at = datetime.now(timezone.utc)
        await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    except Exception as e:
        logger.exception(f"pipeline unhandled: {e}")


@api.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate, bg: BackgroundTasks,
                        current=Depends(require_role("admin", "sales_manager", "sdr"))):
    lead = Lead(owner_id=current["workspace_id"], created_by=current["id"], **payload.model_dump())
    lead.status = "qualifying"; lead.processing_status = "pending"; lead.pipeline_stage = "new"
    lead.activities.append(Activity(type="created", message=f"Lead captured from {lead.source}"))
    lead.stage_history.append(StageChange(to_stage="new", by_user_id=current["id"], by_user_name=current["email"]))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    bg.add_task(_run_pipeline, lead.id, current["workspace_id"], current["id"])
    return lead


@api.post("/leads/public", response_model=Lead)
async def create_lead_public(payload: LeadCreate, bg: BackgroundTasks, owner_email: str = Query(...)):
    owner = await db.users.find_one({"email": owner_email.lower()}, {"_id": 0})
    if not owner: raise HTTPException(status_code=404, detail="Account not found")
    workspace_id = owner.get("workspace_id") or owner["id"]
    lead = Lead(owner_id=workspace_id, created_by=owner["id"], **payload.model_dump())
    lead.status = "qualifying"; lead.processing_status = "pending"; lead.pipeline_stage = "new"
    lead.activities.append(Activity(type="created", message=f"Public lead captured from {lead.source}"))
    lead.stage_history.append(StageChange(to_stage="new", by_user_name="public"))
    await db.leads.insert_one(_serialize(lead.model_dump()))
    bg.add_task(_run_pipeline, lead.id, workspace_id, owner["id"])
    return lead


@api.get("/leads", response_model=List[Lead])
async def list_leads(current=Depends(get_current_user), status: Optional[str] = None,
                       q: Optional[str] = None, stage: Optional[str] = None,
                       assigned_to: Optional[str] = None, limit: int = 500):
    query: dict = {"owner_id": current["workspace_id"]}
    if status: query["status"] = status
    if stage: query["pipeline_stage"] = stage
    if assigned_to: query["assigned_to"] = assigned_to if assigned_to != "me" else current["id"]
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
        {"$match": {"owner_id": current["workspace_id"]}},
        {"$group": {"_id": "$processing_status", "n": {"$sum": 1}}},
    ])
    counts = {"pending": 0, "analyzing": 0, "qualified": 0, "failed": 0}
    async for row in cur:
        k = row["_id"] or "pending"
        if k in counts: counts[k] = row["n"]
        else: counts["qualified"] += row["n"]
    return counts


@api.get("/leads/pipeline")
async def pipeline_view(current=Depends(get_current_user)):
    leads = await db.leads.find({"owner_id": current["workspace_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(1000)
    by_stage = {s: [] for s in PIPELINE_STAGES}
    for l in leads:
        by_stage.setdefault(l.get("pipeline_stage") or "new", []).append(l)
    return {"stages": PIPELINE_STAGES, "by_stage": by_stage}


@api.get("/leads/{lead_id}", response_model=Lead)
async def get_lead(lead_id: str, current=Depends(get_current_user)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    return doc


@api.get("/leads/{lead_id}/decisions")
async def lead_decisions(lead_id: str, current=Depends(get_current_user)):
    if not await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Lead not found")
    return await db.ai_decisions.find({"owner_id": current["workspace_id"], "lead_id": lead_id}, {"_id": 0}) \
        .sort("at", -1).to_list(100)


@api.patch("/leads/{lead_id}/status", response_model=Lead)
async def update_status(lead_id: str, payload: LeadStatusUpdate,
                          current=Depends(require_role("admin", "sales_manager", "sdr")),
                          orch: IntegrationOrchestrator = Depends(get_orchestrator),
                          audit: AuditService = Depends(get_audit)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc); old = lead.status
    lead.status = payload.status
    lead.activities.append(Activity(type="status_change", message=f"Status changed from {old} to {payload.status}"))
    contact_id = _extract_contact_id(lead)
    if contact_id and orch.hubspot.is_configured:
        res = await orch.hubspot.sync_status(contact_id, payload.status)
        act = await orch._log(res, lead_id=lead.id, activity_type="hubspot_status_sync")
        lead.activities.append(Activity(**act))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    await audit.log(action="update.lead_status", resource_type="lead", resource_id=lead_id,
                     old_value={"status": old}, new_value={"status": payload.status})
    return lead


@api.patch("/leads/{lead_id}/stage", response_model=Lead)
async def update_stage(lead_id: str, payload: LeadStageUpdate,
                         current=Depends(require_role("admin", "sales_manager", "sdr")),
                         audit: AuditService = Depends(get_audit)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc); old = lead.pipeline_stage
    lead.pipeline_stage = payload.pipeline_stage
    lead.stage_history.append(StageChange(from_stage=old, to_stage=payload.pipeline_stage,
                                            by_user_id=current["id"], by_user_name=current["email"]))
    lead.activities.append(Activity(type="stage_change",
        message=f"Pipeline: {old} → {payload.pipeline_stage}"))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    await audit.log(action="update.lead_stage", resource_type="lead", resource_id=lead_id,
                     old_value={"pipeline_stage": old}, new_value={"pipeline_stage": payload.pipeline_stage})
    return lead


@api.patch("/leads/{lead_id}/assign", response_model=Lead)
async def assign_lead(lead_id: str, payload: LeadAssignUpdate,
                         current=Depends(require_role("admin", "sales_manager")),
                         audit: AuditService = Depends(get_audit),
                         notify: NotificationService = Depends(get_notify)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc); old = lead.assigned_to
    lead.assigned_to = payload.assigned_to
    lead.assignment_reason = payload.reason or ("Manually unassigned" if not payload.assigned_to else "Manual assignment")
    who_name = "unassigned"
    if payload.assigned_to:
        u = await db.users.find_one({"id": payload.assigned_to, "workspace_id": current["workspace_id"]}, {"_id": 0})
        if not u: raise HTTPException(status_code=400, detail="User not in workspace")
        who_name = u["full_name"]
        await notify.push(user_id=payload.assigned_to, kind="lead_assigned",
            title=f"Lead assigned to you: {lead.name}",
            body=f"{lead.company} · by {current['email']}", lead_id=lead_id)
    lead.activities.append(Activity(type="assigned", message=f"Assigned to {who_name} — {lead.assignment_reason}"))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    await audit.log(action="update.lead_assignment", resource_type="lead", resource_id=lead_id,
                     old_value={"assigned_to": old}, new_value={"assigned_to": payload.assigned_to})
    return lead


@api.post("/leads/{lead_id}/notes", response_model=Lead)
async def add_note(lead_id: str, payload: NoteCreate,
                     current=Depends(require_role("admin", "sales_manager", "sdr")),
                     notify: NotificationService = Depends(get_notify)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    # Detect @mentions (@email or @full.name)
    mentions_emails = re.findall(r"@([\w\.\-+]+@[\w\.\-]+\.\w+)", payload.body)
    mention_ids: list[str] = []
    for em in mentions_emails:
        u = await db.users.find_one({"email": em.lower(), "workspace_id": current["workspace_id"]}, {"_id": 0})
        if u:
            mention_ids.append(u["id"])
            await notify.push(user_id=u["id"], kind="mention",
                title=f"{current['email']} mentioned you",
                body=payload.body[:200], lead_id=lead_id)
    note = Note(author_id=current["id"], author_name=current["email"],
                 body=payload.body, mentions=mention_ids)
    lead.notes.append(note)
    lead.activities.append(Activity(type="note", message=f"Note added by {current['email']}",
                                      metadata={"note_id": note.id}))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.post("/leads/{lead_id}/regenerate", response_model=Lead)
async def regenerate(lead_id: str,
                      type: str = Query("all", pattern="^(all|first_email|linkedin_message|followup_email|email)$"),
                      current=Depends(require_role("admin", "sales_manager", "sdr"))):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    if not lead.qualification or lead.qualification.score is None:
        raise HTTPException(status_code=400, detail="Lead not qualified yet")

    ai = get_ai_service_for(current["workspace_id"])
    decision_type = {"first_email": "regenerate_email", "email": "regenerate_email",
                       "linkedin_message": "regenerate_linkedin", "followup_email": "regenerate_followup",
                       "all": "outreach"}[type]
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
    lead.generated_email = GeneratedEmail(subject=lead.outreach.subject, body=lead.outreach.first_email,
                                              generated_at=lead.outreach.generated_at)
    lead.activities.append(Activity(type="email_generated", message=f"AI regenerated {type.replace('_',' ')}"))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.post("/leads/{lead_id}/regenerate-email", response_model=Lead)
async def regenerate_email_alias(lead_id: str,
                                    current=Depends(require_role("admin", "sales_manager", "sdr"))):
    return await regenerate(lead_id, type="first_email", current=current)


@api.post("/leads/{lead_id}/retry-sync", response_model=Lead)
async def retry_sync(lead_id: str, current=Depends(require_role("admin", "sales_manager", "sdr")),
                       orch: IntegrationOrchestrator = Depends(get_orchestrator)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
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
async def delete_lead(lead_id: str, current=Depends(require_role("admin", "sales_manager")),
                        audit: AuditService = Depends(get_audit)):
    r = await db.leads.delete_one({"id": lead_id, "owner_id": current["workspace_id"]})
    if r.deleted_count == 0: raise HTTPException(status_code=404, detail="Lead not found")
    await audit.log(action="delete.lead", resource_type="lead", resource_id=lead_id)
    return {"ok": True}


# ---------- Emails on a lead ----------
@api.post("/leads/{lead_id}/emails", response_model=Lead)
async def send_email(lead_id: str, payload: EmailSendInput, bg: BackgroundTasks,
                       current=Depends(require_role("admin", "sales_manager", "sdr")),
                       notify: NotificationService = Depends(get_notify)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    settings = await _get_settings_doc(current["workspace_id"])
    svc = EmailService(settings)
    msg = EmailMessage(
        to=payload.to, subject=payload.subject, body=payload.body,
        status="draft" if payload.save_as_draft else ("scheduled" if payload.schedule_at else "queued"),
        scheduled_at=payload.schedule_at, created_by=current["id"],
    )
    if not payload.save_as_draft and not payload.schedule_at:
        res = await svc.send(to=msg.to, subject=msg.subject, body=msg.body)
        msg.status = res["status"]; msg.provider_message_id = res.get("provider_message_id")
        msg.error = res.get("error"); msg.sent_at = datetime.now(timezone.utc)
        if res.get("mocked"): msg.provider = "resend-mock"
        lead.activities.append(Activity(type="email_sent",
            message=f"Email sent to {msg.to}: '{msg.subject[:60]}'",
            metadata={"email_id": msg.id, "status": msg.status, "mocked": bool(res.get("mocked"))}))
        if lead.created_by:
            await notify.push(user_id=lead.created_by, kind="email_sent",
                title=f"Email sent to {msg.to}", body=msg.subject, lead_id=lead_id)
    elif payload.schedule_at:
        lead.activities.append(Activity(type="email_scheduled",
            message=f"Email scheduled for {msg.scheduled_at.isoformat()}",
            metadata={"email_id": msg.id}))
    else:
        lead.activities.append(Activity(type="email_draft", message=f"Draft saved: '{msg.subject[:60]}'",
            metadata={"email_id": msg.id}))
    lead.emails.append(msg)
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    return lead


@api.post("/webhooks/resend")
async def resend_webhook(request: Request):
    """Public webhook — Resend calls this with delivery events."""
    payload = await request.json()
    event = payload.get("type") or payload.get("event") or ""
    data = payload.get("data") or {}
    message_id = data.get("email_id") or data.get("id")
    if not message_id: return {"ok": False, "reason": "no message id"}
    map_status = {"email.sent": "sent", "email.delivered": "delivered",
                    "email.opened": "opened", "email.clicked": "clicked",
                    "email.bounced": "bounced", "email.complained": "failed"}
    new_status = map_status.get(event)
    if not new_status: return {"ok": True, "ignored": event}
    field = f"emails.$.{new_status}_at" if new_status in ("delivered", "opened", "clicked") else None
    update = {"$set": {"emails.$.status": new_status}}
    if field: update["$set"][field] = _now_iso()
    await db.leads.update_one({"emails.provider_message_id": message_id}, update)
    return {"ok": True}


# ---------- Meetings on a lead ----------
@api.post("/leads/{lead_id}/meetings/propose")
async def propose_meeting(lead_id: str, payload: MeetingProposeInput,
                            current=Depends(require_role("admin", "sales_manager", "sdr"))):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    slots = recommend_slots(lead.qualification.model_dump(), duration_min=payload.duration_min)
    return {"slots": slots,
            "title_suggestion": payload.title or f"Intro call — {lead.company}",
            "description_suggestion": payload.description or
                f"Intro call between {current['email']} and {lead.name} ({lead.company}). "
                f"Discussion focused on the inbound query.",
            "duration_min": payload.duration_min}


@api.post("/leads/{lead_id}/meetings", response_model=Lead)
async def confirm_meeting(lead_id: str, payload: MeetingConfirmInput,
                            current=Depends(require_role("admin", "sales_manager", "sdr")),
                            notify: NotificationService = Depends(get_notify),
                            audit: AuditService = Depends(get_audit)):
    doc = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Lead not found")
    lead = Lead(**doc)
    start = payload.start
    if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    end = start.replace(microsecond=0) + __import__("datetime").timedelta(minutes=payload.duration_min)
    attendees = payload.attendee_emails or [lead.email]
    settings = await _get_settings_doc(current["workspace_id"])
    organizer_email = settings.get("google_calendar_organizer_email") or current["email"]
    gcal_url = google_calendar_url(title=payload.title, description=payload.description or "",
                                     start=start, end=end, attendees=attendees)
    meeting = Meeting(title=payload.title, description=payload.description,
                       start=start, end=end, attendee_emails=attendees,
                       organizer_id=current["id"], status="scheduled",
                       gcal_template_url=gcal_url)
    lead.meetings.append(meeting)
    if lead.pipeline_stage in ("new", "qualified"):
        old_stage = lead.pipeline_stage
        lead.pipeline_stage = "demo_scheduled"
        lead.stage_history.append(StageChange(from_stage=old_stage, to_stage="demo_scheduled",
                                                by_user_id=current["id"], by_user_name=current["email"]))
    lead.activities.append(Activity(type="meeting_scheduled",
        message=f"Meeting '{meeting.title}' scheduled for {start.isoformat()}",
        metadata={"meeting_id": meeting.id, "gcal_url": gcal_url}))
    lead.updated_at = datetime.now(timezone.utc)
    await db.leads.replace_one({"id": lead.id}, _serialize(lead.model_dump()))
    await audit.log(action="create.meeting", resource_type="meeting", resource_id=meeting.id,
                     new_value={"title": payload.title, "start": start.isoformat(),
                                "attendees": attendees})
    if lead.created_by:
        await notify.push(user_id=lead.created_by, kind="meeting_scheduled",
            title=f"Meeting scheduled: {payload.title}",
            body=f"With {lead.name} on {start.strftime('%b %d, %H:%M UTC')}", lead_id=lead_id)
    return lead


@api.get("/leads/{lead_id}/meetings/{meeting_id}/ics", response_class=PlainTextResponse)
async def meeting_ics(lead_id: str, meeting_id: str, current=Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id, "owner_id": current["workspace_id"]}, {"_id": 0})
    if not lead: raise HTTPException(status_code=404, detail="Lead not found")
    meeting = next((m for m in lead.get("meetings", []) if m["id"] == meeting_id), None)
    if not meeting: raise HTTPException(status_code=404, detail="Meeting not found")
    start = _parse_dt(meeting["start"]); end = _parse_dt(meeting["end"])
    settings = await _get_settings_doc(current["workspace_id"])
    organizer = settings.get("google_calendar_organizer_email") or current["email"]
    ics = build_ics(title=meeting["title"], description=meeting.get("description") or "",
                     start=start, end=end, organizer_email=organizer,
                     attendee_emails=meeting.get("attendee_emails") or [])
    return PlainTextResponse(ics, media_type="text/calendar")


# ---------- Notifications ----------
@api.get("/notifications")
async def list_notifications(current=Depends(get_current_user), unread_only: bool = False,
                              limit: int = 30,
                              n: NotificationService = Depends(get_notify)):
    items = await n.list(current["id"], limit=limit, unread_only=unread_only)
    unread = await n.unread_count(current["id"])
    return {"items": items, "unread": unread}


@api.post("/notifications/{notif_id}/read")
async def read_notification(notif_id: str, current=Depends(get_current_user),
                              n: NotificationService = Depends(get_notify)):
    await n.mark_read(current["id"], notif_id); return {"ok": True}


@api.post("/notifications/read-all")
async def read_all(current=Depends(get_current_user),
                     n: NotificationService = Depends(get_notify)):
    await n.mark_all_read(current["id"]); return {"ok": True}


# ---------- Audit ----------
@api.get("/audit")
async def audit_list(current=Depends(require_role("admin", "sales_manager")),
                       resource_type: Optional[str] = None, action: Optional[str] = None,
                       limit: int = 200,
                       audit: AuditService = Depends(get_audit)):
    return await audit.list(limit=limit, resource_type=resource_type, action=action)


@api.get("/audit/export.csv", response_class=PlainTextResponse)
async def audit_export(current=Depends(require_role("admin", "sales_manager")),
                         audit: AuditService = Depends(get_audit)):
    rows = await audit.list(limit=5000)
    header = "at,user_email,action,resource_type,resource_id,old_value,new_value"
    def esc(v): return '"' + str(v).replace('"', '""') + '"'
    lines = [header] + [",".join(esc(r.get(k, "")) for k in
        ["at","user_email","action","resource_type","resource_id","old_value","new_value"]) for r in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


# ---------- Analytics ----------
@api.get("/analytics/summary")
async def analytics_summary(current=Depends(get_current_user)):
    owner = current["workspace_id"]
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
            insights.append({"lead_id": l["id"], "company": l["company"], "name": l["name"],
                             "score": q_.get("score"), "summary": q_.get("qualification_summary"),
                             "action": q_.get("recommended_action")})
    return {"total_leads": total, "qualified_leads": qualified,
            "conversion_rate": conv_rate, "qualified_rate": qualified_rate,
            "avg_score": avg_score, "score_distribution": score_distribution,
            "by_industry": by_industry, "timeline": timeline, "ai_insights": insights}


@api.get("/analytics/activity")
async def recent_activity(current=Depends(get_current_user), limit: int = 20):
    leads = await db.leads.find({"owner_id": current["workspace_id"]}, {"_id": 0}).to_list(500)
    acts = []
    for l in leads:
        for a in l.get("activities", []):
            acts.append({**a, "lead_id": l["id"], "lead_name": l["name"], "company": l["company"]})
    acts.sort(key=lambda x: x.get("at", ""), reverse=True)
    return acts[:limit]


@api.get("/analytics/ai")
async def analytics_ai(current=Depends(get_current_user)):
    owner = current["workspace_id"]
    leads = await db.leads.find({"owner_id": owner}, {"_id": 0}).to_list(2000)
    decisions = await db.ai_decisions.find({"owner_id": owner}, {"_id": 0}).to_list(5000)
    scores = [l.get("qualification", {}).get("score") for l in leads if l.get("qualification", {}).get("score") is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    high_intent = sum(1 for l in leads if (l.get("qualification") or {}).get("buying_intent") in ("High", "Very High"))
    ind: dict = {}
    for l in leads:
        i = (l.get("qualification") or {}).get("industry") or "Unknown"
        ind[i] = ind.get(i, 0) + 1
    total = sum(ind.values()) or 1
    industry_distribution = sorted([{"industry": k, "count": v, "pct": round(v / total * 100, 1)}
                                      for k, v in ind.items() if k != "Unknown"],
                                     key=lambda x: -x["count"])[:8]
    icp_leads = sorted([l for l in leads if (l.get("qualification") or {}).get("icp_match") is True],
                        key=lambda l: -(l.get("qualification", {}).get("score") or 0))[:5]
    top_icp = [{"lead_id": l["id"], "name": l["name"], "company": l["company"],
                 "score": l.get("qualification", {}).get("score"),
                 "industry": l.get("qualification", {}).get("industry"),
                 "reason": l.get("qualification", {}).get("icp_match_reasoning")} for l in icp_leads]
    qd = [d for d in decisions if d.get("decision_type") == "qualification"]
    success = sum(1 for d in qd if d.get("status") == "success")
    success_rate = round((success / len(qd)) * 100, 1) if qd else 0
    latencies = [d.get("latency_ms") for d in qd if d.get("latency_ms")]
    avg_processing_ms = round(sum(latencies) / len(latencies)) if latencies else 0
    prompt_versions: dict = {}
    for d in qd:
        prompt_versions[d.get("prompt_name")] = max(prompt_versions.get(d.get("prompt_name"), 0), d.get("prompt_version") or 1)
    return {"avg_ai_score": avg, "high_intent_leads": high_intent,
            "industry_distribution": industry_distribution, "top_icp_matches": top_icp,
            "qualification_success_rate": success_rate,
            "qualification_success_count": success, "qualification_total": len(qd),
            "avg_processing_ms": avg_processing_ms, "prompt_versions": prompt_versions,
            "total_ai_decisions": len(decisions)}


@api.get("/analytics/advanced")
async def analytics_advanced(current=Depends(get_current_user)):
    """Sales funnel, pipeline value, revenue forecast, cycle, source perf, win rate, SDR leaderboard, AI accuracy."""
    owner = current["workspace_id"]
    leads = await db.leads.find({"owner_id": owner}, {"_id": 0}).to_list(3000)
    total = len(leads)

    # Funnel per pipeline stage
    stage_counts = {s: 0 for s in PIPELINE_STAGES}
    for l in leads:
        st = l.get("pipeline_stage") or "new"
        stage_counts[st] = stage_counts.get(st, 0) + 1
    funnel = [{"stage": s, "count": stage_counts[s]} for s in PIPELINE_STAGES]

    # Pipeline value + revenue forecast (score-weighted, avg deal $12k assumption; not persisted)
    AVG_DEAL_USD = int(os.environ.get("SDR_AVG_DEAL_USD", "12000"))
    open_stages = ("qualified", "demo_scheduled", "proposal_sent", "negotiation")
    open_leads = [l for l in leads if (l.get("pipeline_stage") or "") in open_stages]
    pipeline_value = len(open_leads) * AVG_DEAL_USD
    forecast = int(sum((l.get("qualification", {}).get("score") or 0) / 100 * AVG_DEAL_USD for l in open_leads))

    # Cycle time (created → closed_won)
    cycles = []
    for l in leads:
        if l.get("pipeline_stage") == "closed_won":
            c = _parse_dt(l.get("created_at")); u = _parse_dt(l.get("updated_at"))
            if c and u: cycles.append((u - c).days)
    avg_cycle_days = round(sum(cycles) / len(cycles), 1) if cycles else 0

    # Source performance
    src: dict = {}
    for l in leads:
        s = l.get("source") or "website"
        r = src.setdefault(s, {"count": 0, "won": 0})
        r["count"] += 1
        if l.get("pipeline_stage") == "closed_won": r["won"] += 1
    source_performance = [{"source": k, "count": v["count"], "won": v["won"],
                            "win_rate": round(v["won"] / v["count"] * 100, 1) if v["count"] else 0}
                           for k, v in sorted(src.items(), key=lambda x: -x[1]["count"])]

    # Win rate
    closed = [l for l in leads if l.get("pipeline_stage") in ("closed_won", "closed_lost")]
    won = sum(1 for l in closed if l["pipeline_stage"] == "closed_won")
    win_rate = round(won / len(closed) * 100, 1) if closed else 0

    # Conversion rates per stage transition
    conv = []
    for i in range(len(PIPELINE_STAGES) - 2):  # exclude closed_won/lost end
        s_from = PIPELINE_STAGES[i]; s_to = PIPELINE_STAGES[i+1]
        # leads that ever reached s_to = count in s_to and beyond
        from_pool = sum(stage_counts[s] for s in PIPELINE_STAGES[i:])
        to_pool = sum(stage_counts[s] for s in PIPELINE_STAGES[i+1:])
        conv.append({"from": s_from, "to": s_to,
                      "rate": round(to_pool / from_pool * 100, 1) if from_pool else 0})

    # Top SDR performance (leads owned + won)
    sdr_rows: dict = {}
    users = await db.users.find({"workspace_id": owner}, {"_id": 0, "password_hash": 0}).to_list(200)
    id_to_user = {u["id"]: u for u in users}
    for l in leads:
        aid = l.get("assigned_to")
        if not aid: continue
        r = sdr_rows.setdefault(aid, {"user_id": aid, "leads": 0, "qualified": 0, "won": 0})
        r["leads"] += 1
        if l.get("pipeline_stage") == "closed_won": r["won"] += 1
        if (l.get("qualification", {}).get("score") or 0) >= 50: r["qualified"] += 1
    top_sdrs = sorted([
        {**r, "full_name": id_to_user.get(r["user_id"], {}).get("full_name", "unknown"),
         "email": id_to_user.get(r["user_id"], {}).get("email", ""),
         "win_rate": round(r["won"] / r["leads"] * 100, 1) if r["leads"] else 0}
        for r in sdr_rows.values()
    ], key=lambda x: -x["leads"])[:10]

    # AI accuracy: for leads where AI said "Reject Lead" but human converted, OR AI said "Call Immediately" and closed_won.
    # Approximation: agreement between AI's recommended_action and outcome.
    total_actionable = 0; agreed = 0
    for l in leads:
        act = (l.get("qualification") or {}).get("recommended_action")
        stage = l.get("pipeline_stage")
        if not act or stage in ("new", "qualified"): continue
        total_actionable += 1
        good_actions = ("Book Demo", "Call Immediately", "Send Personalized Email")
        reject_actions = ("Reject Lead", "Add to Nurture Campaign")
        if stage in ("demo_scheduled", "proposal_sent", "negotiation", "closed_won") and act in good_actions: agreed += 1
        elif stage == "closed_lost" and act in reject_actions: agreed += 1
    ai_accuracy = round(agreed / total_actionable * 100, 1) if total_actionable else 0

    return {
        "funnel": funnel, "pipeline_value_usd": pipeline_value, "revenue_forecast_usd": forecast,
        "avg_cycle_days": avg_cycle_days, "source_performance": source_performance,
        "stage_conversions": conv, "win_rate": win_rate,
        "top_sdrs": top_sdrs, "ai_recommendation_accuracy": ai_accuracy,
        "avg_deal_usd": AVG_DEAL_USD,
    }


def _extract_contact_id(lead: Lead) -> Optional[str]:
    for a in reversed(lead.activities or []):
        md = a.metadata or {}
        if md.get("provider") == "hubspot" and md.get("action") == "create_contact":
            data = md.get("data") or {}
            if data.get("id"): return data["id"]
    return None


# ---------- Register + CORS ----------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown(): client.close()
from fastapi import FastAPI

@app.get("/")
def home():
    return {"message": "AI SDR Agent is running"}

@app.get("/health")
def health():
    return {"status": "ok"}
    @app.get("/")
def root():
    return {"message": "AI SDR Agent is running!"}


@app.get("/health")
def health():
    return {"status": "ok"}
