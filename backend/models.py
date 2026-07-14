"""Pydantic models for AI SDR Agent."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime, timezone
import uuid


def _uid() -> str: return str(uuid.uuid4())
def _now() -> datetime: return datetime.now(timezone.utc)


# ---------- Roles / RBAC ----------
Role = Literal["admin", "sales_manager", "sdr", "viewer"]

ROLE_HIERARCHY = {"admin": 4, "sales_manager": 3, "sdr": 2, "viewer": 1}


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=1, max_length=120)
    invite_token: Optional[str] = None  # for joining an existing workspace


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role = "admin"
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


# ---------- Workspace ----------
class Workspace(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    owner_user_id: str
    created_at: datetime = Field(default_factory=_now)


class WorkspaceMember(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: Role


class Invite(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    email: EmailStr
    role: Role = "sdr"
    invited_by: str
    token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    accepted: bool = False
    created_at: datetime = Field(default_factory=_now)


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = "sdr"


class MemberRoleUpdate(BaseModel):
    role: Role


# ---------- Leads ----------
LeadStatus = Literal["new", "qualifying", "qualified", "disqualified", "contacted", "converted"]
ProcessingStatus = Literal["pending", "analyzing", "qualified", "failed"]
PipelineStage = Literal["new", "qualified", "demo_scheduled", "proposal_sent", "negotiation", "closed_won", "closed_lost"]

PIPELINE_STAGES: list[PipelineStage] = ["new", "qualified", "demo_scheduled", "proposal_sent", "negotiation", "closed_won", "closed_lost"]


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    job_title: Optional[str] = None
    website: Optional[str] = None
    company_size_hint: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = "website"
    region: Optional[str] = None  # for assignment engine


class Qualification(BaseModel):
    industry: Optional[str] = None
    company_size: Optional[str] = None
    business_type: Optional[str] = None
    icp_match: Optional[bool] = None
    icp_match_reasoning: Optional[str] = None
    buying_intent: Optional[str] = None
    urgency: Optional[str] = None
    decision_maker_probability: Optional[int] = None
    score: Optional[int] = None
    score_explanation: Optional[str] = None
    qualification_summary: Optional[str] = None
    key_signals: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    action_reasoning: Optional[str] = None
    next_step_reason: Optional[str] = None


class Outreach(BaseModel):
    subject: Optional[str] = None
    first_email: Optional[str] = None
    linkedin_message: Optional[str] = None
    followup_email: Optional[str] = None
    generated_at: Optional[datetime] = None


class GeneratedEmail(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    generated_at: Optional[datetime] = None


class Activity(BaseModel):
    id: str = Field(default_factory=_uid)
    type: str
    message: str
    metadata: dict = Field(default_factory=dict)
    at: datetime = Field(default_factory=_now)


class StageChange(BaseModel):
    id: str = Field(default_factory=_uid)
    from_stage: Optional[str] = None
    to_stage: str
    by_user_id: Optional[str] = None
    by_user_name: Optional[str] = None
    at: datetime = Field(default_factory=_now)


class Note(BaseModel):
    id: str = Field(default_factory=_uid)
    author_id: str
    author_name: str
    body: str
    mentions: List[str] = Field(default_factory=list)  # user_ids
    at: datetime = Field(default_factory=_now)


class EmailMessage(BaseModel):
    id: str = Field(default_factory=_uid)
    to: str
    subject: str
    body: str
    status: str = "draft"  # draft | scheduled | queued | sent | delivered | opened | clicked | bounced | failed
    provider: str = "resend"
    provider_message_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    error: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=_now)


class Meeting(BaseModel):
    id: str = Field(default_factory=_uid)
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    attendee_emails: List[str] = Field(default_factory=list)
    organizer_id: str
    status: str = "proposed"  # proposed | scheduled | completed | cancelled
    gcal_event_id: Optional[str] = None
    gcal_template_url: Optional[str] = None
    provider: str = "google_calendar"
    created_at: datetime = Field(default_factory=_now)


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=_uid)
    owner_id: str  # workspace_id (kept name for legacy compat)
    created_by: Optional[str] = None  # user_id who created
    assigned_to: Optional[str] = None
    assignment_reason: Optional[str] = None
    name: str
    email: str
    company: str
    job_title: Optional[str] = None
    website: Optional[str] = None
    company_size_hint: Optional[str] = None
    message: Optional[str] = None
    source: str = "website"
    region: Optional[str] = None
    status: LeadStatus = "new"
    processing_status: ProcessingStatus = "pending"
    pipeline_stage: PipelineStage = "new"
    stage_history: List[StageChange] = Field(default_factory=list)
    qualification: Qualification = Field(default_factory=Qualification)
    generated_email: Optional[GeneratedEmail] = None
    outreach: Optional[Outreach] = None
    activities: List[Activity] = Field(default_factory=list)
    notes: List[Note] = Field(default_factory=list)
    emails: List[EmailMessage] = Field(default_factory=list)
    meetings: List[Meeting] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadStageUpdate(BaseModel):
    pipeline_stage: PipelineStage


class LeadAssignUpdate(BaseModel):
    assigned_to: Optional[str] = None  # user_id (None to unassign)
    reason: Optional[str] = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class EmailSendInput(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    schedule_at: Optional[datetime] = None
    save_as_draft: bool = False


class MeetingProposeInput(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_min: int = 30
    timezone_hint: Optional[str] = None


class MeetingConfirmInput(BaseModel):
    title: str
    description: Optional[str] = None
    start: datetime
    duration_min: int = 30
    attendee_emails: List[EmailStr] = Field(default_factory=list)


# ---------- Integration settings ----------
class IntegrationSettings(BaseModel):
    hubspot_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    n8n_webhook_url: Optional[str] = None
    resend_api_key: Optional[str] = None
    resend_from_email: Optional[str] = None  # e.g. "AI SDR <sdr@yourdomain.com>"
    google_calendar_organizer_email: Optional[str] = None
    auto_sync_hubspot: bool = True
    auto_notify_slack: bool = True
    auto_trigger_n8n: bool = False


# ---------- Assignment rules ----------
class AssignmentRule(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    priority: int = 100
    region_match: Optional[str] = None
    industry_match: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    assign_to_user_id: Optional[str] = None  # None => round-robin
    active: bool = True


class AssignmentRuleInput(BaseModel):
    priority: int = 100
    region_match: Optional[str] = None
    industry_match: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    assign_to_user_id: Optional[str] = None
    active: bool = True


# ---------- AI decisions / Prompts ----------
class AIDecision(BaseModel):
    id: str = Field(default_factory=_uid)
    owner_id: str
    lead_id: Optional[str] = None
    decision_type: str
    prompt_name: str
    prompt_version: int
    model: str
    input_summary: str
    output: dict = Field(default_factory=dict)
    reasoning: Optional[str] = None
    score: Optional[int] = None
    action: Optional[str] = None
    latency_ms: Optional[int] = None
    status: str = "success"
    error: Optional[str] = None
    at: datetime = Field(default_factory=_now)


class Prompt(BaseModel):
    id: str = Field(default_factory=_uid)
    owner_id: str
    name: str
    template: str
    version: int = 1
    updated_at: datetime = Field(default_factory=_now)


class PromptUpdate(BaseModel):
    template: str


class PromptTestInput(BaseModel):
    lead: LeadCreate
    qualification: Optional[Qualification] = None


# ---------- Notifications ----------
class Notification(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    user_id: str
    kind: str  # email_sent | meeting_scheduled | lead_assigned | qualification_done | webhook_failed | slack_failed | mention
    title: str
    body: Optional[str] = None
    lead_id: Optional[str] = None
    read: bool = False
    created_at: datetime = Field(default_factory=_now)


# ---------- Audit logs ----------
class AuditLog(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    user_id: str
    user_email: str
    action: str  # verb.resource — e.g. "update.lead_stage"
    resource_type: str
    resource_id: Optional[str] = None
    old_value: dict = Field(default_factory=dict)
    new_value: dict = Field(default_factory=dict)
    at: datetime = Field(default_factory=_now)
