"""Seed the demo workspace with realistic AI SDR data for a live demo.

Usage:
    cd /app/backend && python -m scripts.seed_demo

Creates 4 users (admin, sales manager, 2 SDRs) in workspace 'Acme Sales'
and 8 leads across pipeline stages with notes, activities, and stage history.
Idempotent — safe to re-run.
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from auth import hash_password


DEMO_WORKSPACE_ID = "demo-workspace-acme"
DEMO_USERS = [
    {"email": "alice@acme.demo", "full_name": "Alice Chen", "role": "admin", "password": "demo1234"},
    {"email": "bob@acme.demo", "full_name": "Bob Martinez", "role": "sales_manager", "password": "demo1234"},
    {"email": "carol@acme.demo", "full_name": "Carol Kim", "role": "sdr", "password": "demo1234"},
    {"email": "dave@acme.demo", "full_name": "Dave Patel", "role": "sdr", "password": "demo1234"},
]

DEMO_LEADS = [
    {"name": "Sarah Chen", "email": "sarah@fintechco.io", "company": "FinTech Co",
     "job_title": "VP Engineering", "region": "us",
     "message": "We need SOC2 in Q1, budget approved, evaluating 3 vendors.",
     "stage": "demo_scheduled", "score": 92, "industry": "Fintech", "intent": "Very High"},
    {"name": "Miguel Torres", "email": "miguel@healthbridge.com", "company": "HealthBridge",
     "job_title": "CTO", "region": "us",
     "message": "HIPAA compliance concerns — need SDR to walk through security posture.",
     "stage": "proposal_sent", "score": 88, "industry": "Healthcare", "intent": "High"},
    {"name": "Emma Larsson", "email": "emma@nordicretail.se", "company": "Nordic Retail",
     "job_title": "Head of Growth", "region": "eu",
     "message": "Exploring how AI can auto-qualify our inbound.",
     "stage": "qualified", "score": 74, "industry": "E-commerce", "intent": "High"},
    {"name": "Raj Kapoor", "email": "raj@edtechworks.in", "company": "EdTech Works",
     "job_title": "Founder & CEO", "region": "apac",
     "message": "Signed up for trial last week — impressive score explanations.",
     "stage": "negotiation", "score": 91, "industry": "Education", "intent": "Very High"},
    {"name": "Priya Shah", "email": "priya@shopgurus.com", "company": "ShopGurus",
     "job_title": "COO", "region": "us",
     "message": "Slow inbound follow-up is killing us — 3 weeks avg response time.",
     "stage": "new", "score": None, "industry": None, "intent": None},
    {"name": "Nathan Wright", "email": "nathan@builderco.uk", "company": "BuilderCo",
     "job_title": "Sales Director", "region": "eu",
     "message": "Just kicking tires — want a demo eventually, no rush.",
     "stage": "qualified", "score": 55, "industry": "Manufacturing", "intent": "Medium"},
    {"name": "Julia Moretti", "email": "julia@brandhaus.it", "company": "BrandHaus",
     "job_title": "Marketing Manager", "region": "eu",
     "message": "Just looking around, testing tools.",
     "stage": "closed_lost", "score": 28, "industry": "Media", "intent": "Low"},
    {"name": "David Klein", "email": "david@quantumlabs.de", "company": "Quantum Labs",
     "job_title": "CEO", "region": "eu",
     "message": "Closing this quarter — need enterprise plan with SSO.",
     "stage": "closed_won", "score": 96, "industry": "SaaS", "intent": "Very High"},
]


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # Workspace
    await db.workspaces.update_one(
        {"id": DEMO_WORKSPACE_ID},
        {"$set": {"id": DEMO_WORKSPACE_ID, "name": "Acme Sales (Demo)",
                    "owner_user_id": None, "rr_index": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    print(f"✓ Workspace: {DEMO_WORKSPACE_ID}")

    # Users
    user_ids = {}
    for u in DEMO_USERS:
        existing = await db.users.find_one({"email": u["email"]}, {"_id": 0})
        if existing:
            user_ids[u["email"]] = existing["id"]
            print(f"  · user exists: {u['email']}")
            continue
        uid = uuid.uuid4().hex
        user_ids[u["email"]] = uid
        await db.users.insert_one({
            "id": uid, "email": u["email"], "full_name": u["full_name"],
            "password_hash": hash_password(u["password"]),
            "workspace_id": DEMO_WORKSPACE_ID, "role": u["role"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  ✓ user: {u['email']} ({u['role']})")

    await db.workspaces.update_one(
        {"id": DEMO_WORKSPACE_ID},
        {"$set": {"owner_user_id": user_ids[DEMO_USERS[0]["email"]]}},
    )

    # Leads
    sdrs = [user_ids[u["email"]] for u in DEMO_USERS if u["role"] == "sdr"]
    admin_id = user_ids[DEMO_USERS[0]["email"]]
    now = datetime.now(timezone.utc)
    for i, l in enumerate(DEMO_LEADS):
        if await db.leads.find_one({"email": l["email"], "owner_id": DEMO_WORKSPACE_ID}, {"_id": 1}):
            print(f"  · lead exists: {l['email']}")
            continue
        assignee = sdrs[i % len(sdrs)] if sdrs else admin_id
        lid = uuid.uuid4().hex
        created_at = (now - timedelta(days=len(DEMO_LEADS) - i, hours=i)).isoformat()
        qualification = None
        if l["score"] is not None:
            qualification = {
                "industry": l["industry"], "company_size": "201-500",
                "business_type": "B2B SaaS", "icp_match": l["score"] >= 65,
                "icp_match_reasoning": f"Match: {l['industry']} + intent {l['intent']}",
                "buying_intent": l["intent"], "urgency": "High" if l["score"] >= 85 else "Medium",
                "decision_maker_probability": 80 if "CEO" in l["job_title"] or "CTO" in l["job_title"] or "VP" in l["job_title"] else 55,
                "score": l["score"],
                "score_explanation": f"Score {l['score']} — {l['intent']} intent + {l['industry']} ICP",
                "qualification_summary": f"{l['name']} at {l['company']} — strong {l['intent'].lower()} intent inbound.",
                "key_signals": ["Explicit budget mention", "Decision maker title", f"{l['industry']} ICP fit"],
                "recommended_action": "Book Demo" if l["score"] >= 75 else "Send Personalized Email" if l["score"] >= 50 else "Add to Nurture Campaign",
                "action_reasoning": "Score + intent + title all align.",
                "next_step_reason": None,
                "key_signals": ["Explicit budget mention", "Senior title", f"{l['industry']} ICP fit"],
            }
            qualification.pop("key_signals", None) if False else None
        activities = [{"id": uuid.uuid4().hex, "type": "created",
                        "message": f"Lead captured from website", "metadata": {},
                        "at": created_at}]
        if qualification:
            activities.append({"id": uuid.uuid4().hex, "type": "qualified",
                                "message": f"AI qualified with score {l['score']}/100 — {qualification['recommended_action']}",
                                "metadata": {"score": l["score"]}, "at": created_at})
        stage_history = [{"id": uuid.uuid4().hex, "from_stage": None, "to_stage": "new",
                            "by_user_id": None, "by_user_name": "system", "at": created_at}]
        if l["stage"] != "new":
            stage_history.append({"id": uuid.uuid4().hex, "from_stage": "new", "to_stage": l["stage"],
                                    "by_user_id": assignee, "by_user_name": "demo", "at": created_at})
        notes = []
        if i % 2 == 0 and qualification:
            notes.append({"id": uuid.uuid4().hex, "author_id": assignee,
                            "author_name": [u["full_name"] for u in DEMO_USERS if user_ids[u["email"]] == assignee][0],
                            "body": f"Called {l['name'].split()[0]} — high-intent, ready to schedule demo next week.",
                            "mentions": [], "at": created_at})
        doc = {
            "id": lid, "owner_id": DEMO_WORKSPACE_ID, "created_by": admin_id,
            "assigned_to": assignee,
            "assignment_reason": f"Round-robin → {[u['full_name'] for u in DEMO_USERS if user_ids[u['email']] == assignee][0]}",
            "name": l["name"], "email": l["email"], "company": l["company"],
            "job_title": l["job_title"], "message": l["message"], "region": l["region"],
            "source": "website",
            "status": "qualified" if l["score"] and l["score"] >= 50 else "new",
            "processing_status": "qualified" if l["score"] else "pending",
            "pipeline_stage": l["stage"],
            "stage_history": stage_history,
            "qualification": qualification or {"key_signals": []},
            "outreach": None, "generated_email": None,
            "activities": activities, "notes": notes,
            "emails": [], "meetings": [],
            "created_at": created_at, "updated_at": created_at,
        }
        await db.leads.insert_one(doc)
        print(f"  ✓ lead: {l['name']} @ {l['company']} → {l['stage']} (score {l['score']})")

    print(f"\n✅ Seed complete. Sign in at /login with:")
    for u in DEMO_USERS:
        print(f"   {u['role']:15} {u['email']}  /  {u['password']}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
