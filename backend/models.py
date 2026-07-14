"""Pydantic models for AI SDR Agent."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime, timezone
import uuid


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=1, max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


# ---------- Leads ----------
LeadStatus = Literal["new", "qualifying", "qualified", "disqualified", "contacted", "converted"]


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


class Qualification(BaseModel):
    industry: Optional[str] = None
    company_size: Optional[str] = None
    buying_intent: Optional[str] = None
    score: Optional[int] = None
    qualification_summary: Optional[str] = None
    key_signals: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    next_step_reason: Optional[str] = None


class GeneratedEmail(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    generated_at: Optional[datetime] = None


class Activity(BaseModel):
    id: str = Field(default_factory=_uid)
    type: str  # "created" | "qualified" | "email_generated" | "hubspot_sync" | "slack_notified" | "n8n_triggered" | "status_change"
    message: str
    metadata: dict = Field(default_factory=dict)
    at: datetime = Field(default_factory=_now)


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uid)
    owner_id: str
    name: str
    email: str
    company: str
    job_title: Optional[str] = None
    website: Optional[str] = None
    company_size_hint: Optional[str] = None
    message: Optional[str] = None
    source: str = "website"
    status: LeadStatus = "new"
    qualification: Qualification = Field(default_factory=Qualification)
    generated_email: Optional[GeneratedEmail] = None
    activities: List[Activity] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


# ---------- Settings ----------
class IntegrationSettings(BaseModel):
    hubspot_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    n8n_webhook_url: Optional[str] = None
    auto_sync_hubspot: bool = True
    auto_notify_slack: bool = True
    auto_trigger_n8n: bool = False
