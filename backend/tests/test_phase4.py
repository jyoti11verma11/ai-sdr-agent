"""Phase 4 backend tests — Workspaces + RBAC + Assignment + Pipeline + Notes +
Notifications + Audit + Email (Resend mock) + Meetings + Advanced Analytics.

Every test class creates its OWN admin user (fresh workspace) so xdist parallel
workers cannot race on shared workspace state.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if "REACT_APP_BACKEND_URL" in os.environ else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

PIPELINE_STAGES = ["new", "qualified", "demo_scheduled", "proposal_sent",
                   "negotiation", "closed_won", "closed_lost"]


# ---------------- helpers ----------------
def _signup(api_client, tag: str, invite_token: str | None = None,
             email: str | None = None) -> dict:
    email = email or f"TEST_p4_{tag}_{uuid.uuid4().hex[:8]}@sdr.ai"
    body = {"email": email, "password": "phase4pw", "full_name": f"P4 {tag}"}
    if invite_token: body["invite_token"] = invite_token
    r = api_client.post(f"{BASE_URL}/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "id": d["user"]["id"], "token": d["token"],
            "user": d["user"],
            "headers": {"Authorization": f"Bearer {d['token']}",
                        "Content-Type": "application/json"}}


def _high_intent_payload(tag: str, region: str | None = None) -> dict:
    p = {
        "name": f"TEST P4 {tag}",
        "email": f"TEST_{tag}_{uuid.uuid4().hex[:6]}@stripe.com",
        "company": "Stripe Payments Inc",
        "job_title": "VP Engineering",
        "message": "Budget approved for Q1. SOC2 compliance required. Need demo ASAP. Ready to purchase.",
        "source": "website",
    }
    if region: p["region"] = region
    return p


def _poll(session, headers, lead_id: str, timeout: float = 60.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = session.get(f"{BASE_URL}/api/leads/{lead_id}", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("processing_status") in ("qualified", "failed"):
            return last
        time.sleep(1.0)
    return last


def _create_and_wait(api_client, user, tag: str, region: str | None = None) -> dict:
    r = api_client.post(f"{BASE_URL}/api/leads",
                        json=_high_intent_payload(tag, region),
                        headers=user["headers"], timeout=15)
    assert r.status_code == 200, r.text
    return _poll(api_client, user["headers"], r.json()["id"], timeout=90.0)


# ---------------- Auth / Workspace ----------------
class TestSignupWorkspace:
    def test_signup_creates_admin_and_workspace(self, api_client):
        u = _signup(api_client, "ws")
        assert u["user"]["role"] == "admin"
        assert u["user"]["workspace_id"] == u["id"]
        assert u["user"]["workspace_name"] and "workspace" in u["user"]["workspace_name"].lower()

    def test_me_returns_role_and_workspace(self, api_client):
        u = _signup(api_client, "wsme")
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers=u["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "admin"
        assert d["workspace_id"] == u["id"]
        assert d["workspace_name"]


# ---------------- Members + Invites + Role update ----------------
class TestWorkspaceMembersAndInvites:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "adm")

    def test_list_members_returns_admin_self(self, api_client, admin):
        r = api_client.get(f"{BASE_URL}/api/workspace/members", headers=admin["headers"])
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        assert any(m["user_id"] == admin["id"] and m["role"] == "admin" for m in rows)

    def test_admin_creates_invite_and_lists_pending(self, api_client, admin):
        invite_email = f"TEST_inv_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": invite_email, "role": "sdr"},
                            headers=admin["headers"])
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["email"] == invite_email.lower()
        assert inv["role"] == "sdr"
        assert inv["token"] and len(inv["token"]) > 10
        assert inv["accepted"] is False

        r2 = api_client.get(f"{BASE_URL}/api/workspace/invites", headers=admin["headers"])
        assert r2.status_code == 200
        pending = r2.json()
        assert any(p["token"] == inv["token"] for p in pending)

    def test_signup_with_invite_joins_workspace(self, api_client, admin):
        invite_email = f"TEST_join_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": invite_email, "role": "sales_manager"},
                            headers=admin["headers"])
        assert r.status_code == 200
        token = r.json()["token"]

        joiner = _signup(api_client, "join", invite_token=token, email=invite_email)
        assert joiner["user"]["workspace_id"] == admin["id"], \
            "joiner should be in admin's workspace"
        assert joiner["user"]["role"] == "sales_manager"

        # invite marked accepted (no longer listed pending)
        r2 = api_client.get(f"{BASE_URL}/api/workspace/invites", headers=admin["headers"])
        assert not any(p["token"] == token for p in r2.json())

        # list members returns 2+
        r3 = api_client.get(f"{BASE_URL}/api/workspace/members", headers=admin["headers"])
        ids = {m["user_id"] for m in r3.json()}
        assert admin["id"] in ids
        assert joiner["id"] in ids

    def test_invite_email_mismatch_rejected(self, api_client, admin):
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": f"TEST_mm_{uuid.uuid4().hex[:6]}@sdr.ai",
                                  "role": "sdr"},
                            headers=admin["headers"])
        token = r.json()["token"]
        # Signup with DIFFERENT email
        r2 = api_client.post(f"{BASE_URL}/api/auth/signup", json={
            "email": f"TEST_wrong_{uuid.uuid4().hex[:6]}@sdr.ai",
            "password": "phase4pw", "full_name": "Wrong",
            "invite_token": token,
        })
        assert r2.status_code == 400, f"expected 400, got {r2.status_code}: {r2.text}"

    def test_patch_member_role_by_admin(self, api_client, admin):
        # invite + signup an SDR
        invite_email = f"TEST_role_{uuid.uuid4().hex[:6]}@sdr.ai"
        rr = api_client.post(f"{BASE_URL}/api/workspace/invites",
                              json={"email": invite_email, "role": "sdr"},
                              headers=admin["headers"])
        token = rr.json()["token"]
        member = _signup(api_client, "roleu", invite_token=token, email=invite_email)

        # admin promotes them to sales_manager
        rp = api_client.patch(
            f"{BASE_URL}/api/workspace/members/{member['id']}",
            json={"role": "sales_manager"}, headers=admin["headers"])
        assert rp.status_code == 200, rp.text

        # verify via list_members
        r = api_client.get(f"{BASE_URL}/api/workspace/members", headers=admin["headers"])
        for m in r.json():
            if m["user_id"] == member["id"]:
                assert m["role"] == "sales_manager"
                break
        else:
            pytest.fail("member missing after role update")

    def test_admin_cannot_self_change_role(self, api_client, admin):
        r = api_client.patch(
            f"{BASE_URL}/api/workspace/members/{admin['id']}",
            json={"role": "sdr"}, headers=admin["headers"])
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


# ---------------- RBAC ----------------
class TestRBAC:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "rbacA")

    @pytest.fixture(scope="class")
    def sdr(self, api_client, admin):
        em = f"TEST_rbSdr_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": em, "role": "sdr"},
                            headers=admin["headers"])
        return _signup(api_client, "rbSdr", invite_token=r.json()["token"], email=em)

    @pytest.fixture(scope="class")
    def viewer(self, api_client, admin):
        em = f"TEST_rbVw_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": em, "role": "viewer"},
                            headers=admin["headers"])
        return _signup(api_client, "rbVw", invite_token=r.json()["token"], email=em)

    def test_sdr_cannot_create_invite(self, api_client, sdr):
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": "x@x.com", "role": "sdr"},
                            headers=sdr["headers"])
        assert r.status_code == 403, r.text

    def test_sdr_cannot_put_settings(self, api_client, sdr):
        r = api_client.put(f"{BASE_URL}/api/settings",
                           json={"auto_sync_hubspot": True, "auto_notify_slack": True,
                                 "auto_trigger_n8n": False},
                           headers=sdr["headers"])
        assert r.status_code == 403, r.text

    def test_sdr_cannot_put_prompts(self, api_client, sdr):
        r = api_client.put(f"{BASE_URL}/api/prompts/qualification",
                           json={"template": "x"}, headers=sdr["headers"])
        assert r.status_code == 403, r.text

    def test_sdr_cannot_get_audit(self, api_client, sdr):
        r = api_client.get(f"{BASE_URL}/api/audit", headers=sdr["headers"])
        assert r.status_code == 403, r.text

    def test_viewer_cannot_create_lead(self, api_client, viewer):
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("vw"),
                            headers=viewer["headers"], timeout=10)
        assert r.status_code == 403, r.text

    def test_admin_can_do_all_gated_ops(self, api_client, admin):
        # settings PUT
        r1 = api_client.put(f"{BASE_URL}/api/settings",
                             json={"auto_sync_hubspot": True,
                                   "auto_notify_slack": True,
                                   "auto_trigger_n8n": False},
                             headers=admin["headers"])
        assert r1.status_code == 200
        # audit GET
        r2 = api_client.get(f"{BASE_URL}/api/audit", headers=admin["headers"])
        assert r2.status_code == 200
        # prompts PUT
        cur = api_client.get(f"{BASE_URL}/api/prompts/qualification",
                              headers=admin["headers"]).json()["template"]
        r3 = api_client.put(f"{BASE_URL}/api/prompts/qualification",
                             json={"template": cur + "\n# admin can edit"},
                             headers=admin["headers"])
        assert r3.status_code == 200


# ---------------- Assignment engine (round-robin + rule) ----------------
class TestAssignmentEngine:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "asgA")

    def test_lead_auto_assigned_by_round_robin_and_activity_added(self, api_client, admin):
        lead = _create_and_wait(api_client, admin, "rr")
        assert lead["processing_status"] == "qualified", lead.get("processing_status")
        assert lead["assigned_to"], f"lead should be assigned, got {lead.get('assigned_to')}"
        assert "Round-robin" in (lead.get("assignment_reason") or "") or \
               "Rule" in (lead.get("assignment_reason") or ""), \
               f"unexpected assignment_reason: {lead.get('assignment_reason')}"
        types = [a["type"] for a in lead["activities"]]
        assert "assigned" in types, f"missing 'assigned' activity in {types}"

    def test_assignment_notification_when_assignee_differs_from_creator(self, api_client, admin):
        # Invite a second user (sales_manager so they're a member)
        em = f"TEST_a2_{uuid.uuid4().hex[:6]}@sdr.ai"
        rr = api_client.post(f"{BASE_URL}/api/workspace/invites",
                              json={"email": em, "role": "sales_manager"},
                              headers=admin["headers"])
        member2 = _signup(api_client, "a2", invite_token=rr.json()["token"], email=em)

        # Create a rule that assigns leads with region='us' to member2 explicitly.
        rule = api_client.post(f"{BASE_URL}/api/assignment/rules",
                                json={"region_match": "us",
                                      "assign_to_user_id": member2["id"],
                                      "priority": 10},
                                headers=admin["headers"])
        assert rule.status_code == 200, rule.text

        # admin creates a US lead → should be assigned to member2 (different from creator)
        lead = _create_and_wait(api_client, admin, "usL", region="us")
        assert lead["assigned_to"] == member2["id"], \
            f"expected rule-based assignment to member2, got {lead.get('assigned_to')} · reason={lead.get('assignment_reason')}"
        assert "Rule" in (lead.get("assignment_reason") or "")

        # member2 should see a notification 'lead_assigned'
        r = api_client.get(f"{BASE_URL}/api/notifications", headers=member2["headers"])
        assert r.status_code == 200
        n = r.json()
        kinds = [i["kind"] for i in n["items"]]
        assert "lead_assigned" in kinds, f"missing lead_assigned notification for assignee: {kinds}"


# ---------------- PATCH assign / stage ----------------
class TestPatchAssignAndStage:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "pa")

    @pytest.fixture(scope="class")
    def member(self, api_client, admin):
        em = f"TEST_pam_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": em, "role": "sdr"},
                            headers=admin["headers"])
        return _signup(api_client, "pam", invite_token=r.json()["token"], email=em)

    @pytest.fixture(scope="class")
    def lead(self, api_client, admin):
        return _create_and_wait(api_client, admin, "pa")

    def test_patch_assign_activity_notification_audit(self, api_client, admin, member, lead):
        r = api_client.patch(f"{BASE_URL}/api/leads/{lead['id']}/assign",
                              json={"assigned_to": member["id"],
                                    "reason": "manual test"},
                              headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        assert upd["assigned_to"] == member["id"]
        assert any(a["type"] == "assigned" for a in upd["activities"])

        # notification for member
        n = api_client.get(f"{BASE_URL}/api/notifications", headers=member["headers"]).json()
        assert any(i["kind"] == "lead_assigned" for i in n["items"])

        # audit entry
        a = api_client.get(f"{BASE_URL}/api/audit?action=update.lead_assignment",
                            headers=admin["headers"]).json()
        assert any(row.get("resource_id") == lead["id"] for row in a)

    def test_patch_stage_history_activity_audit(self, api_client, admin, lead):
        r = api_client.patch(f"{BASE_URL}/api/leads/{lead['id']}/stage",
                              json={"pipeline_stage": "proposal_sent"},
                              headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        assert upd["pipeline_stage"] == "proposal_sent"
        # stage_history entry with by_user_id
        assert any(h.get("to_stage") == "proposal_sent" and h.get("by_user_id") == admin["id"]
                   for h in upd["stage_history"])
        # activity
        assert any(a["type"] == "stage_change" for a in upd["activities"])
        # audit
        a = api_client.get(f"{BASE_URL}/api/audit?action=update.lead_stage",
                            headers=admin["headers"]).json()
        assert any(row.get("resource_id") == lead["id"] for row in a)


# ---------------- Kanban pipeline view ----------------
class TestPipelineView:
    def test_pipeline_view_shape(self, api_client):
        u = _signup(api_client, "pipv")
        r = api_client.get(f"{BASE_URL}/api/leads/pipeline", headers=u["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["stages"] == PIPELINE_STAGES
        assert set(d["by_stage"].keys()) == set(PIPELINE_STAGES)
        for s in PIPELINE_STAGES:
            assert isinstance(d["by_stage"][s], list)


# ---------------- Notes with @mention ----------------
class TestNotesMentions:
    def test_note_with_mention_creates_notification(self, api_client):
        admin = _signup(api_client, "noteA")
        em = f"TEST_mn_{uuid.uuid4().hex[:6]}@sdr.ai"
        r = api_client.post(f"{BASE_URL}/api/workspace/invites",
                            json={"email": em, "role": "sdr"},
                            headers=admin["headers"])
        member = _signup(api_client, "mn", invite_token=r.json()["token"], email=em)

        lead = _create_and_wait(api_client, admin, "noteL")
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/notes",
                             json={"body": f"Hey @{em}, please review this lead"},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        assert len(upd["notes"]) >= 1
        note = upd["notes"][-1]
        assert member["id"] in note["mentions"], \
            f"expected {member['id']} in mentions, got {note['mentions']}"

        # mention notification for member
        n = api_client.get(f"{BASE_URL}/api/notifications", headers=member["headers"]).json()
        assert any(i["kind"] == "mention" for i in n["items"]), \
            f"missing mention notification: {[i['kind'] for i in n['items']]}"


# ---------------- Notifications endpoints ----------------
class TestNotifications:
    def test_list_mark_read_and_read_all(self, api_client):
        admin = _signup(api_client, "nt")
        em = f"TEST_ntM_{uuid.uuid4().hex[:6]}@sdr.ai"
        rr = api_client.post(f"{BASE_URL}/api/workspace/invites",
                              json={"email": em, "role": "sdr"},
                              headers=admin["headers"])
        member = _signup(api_client, "ntM", invite_token=rr.json()["token"], email=em)
        # Generate a mention notification
        lead = _create_and_wait(api_client, admin, "ntL")
        api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/notes",
                         json={"body": f"Ping @{em}"},
                         headers=admin["headers"])

        r = api_client.get(f"{BASE_URL}/api/notifications", headers=member["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "unread" in d
        assert isinstance(d["items"], list)
        assert d["unread"] >= 1
        nid = d["items"][0]["id"]

        r2 = api_client.post(f"{BASE_URL}/api/notifications/{nid}/read",
                              headers=member["headers"])
        assert r2.status_code == 200
        d2 = api_client.get(f"{BASE_URL}/api/notifications",
                             headers=member["headers"]).json()
        # unread should decrement
        assert d2["unread"] == d["unread"] - 1

        r3 = api_client.post(f"{BASE_URL}/api/notifications/read-all",
                              headers=member["headers"])
        assert r3.status_code == 200
        d3 = api_client.get(f"{BASE_URL}/api/notifications",
                             headers=member["headers"]).json()
        assert d3["unread"] == 0


# ---------------- Audit list + CSV export ----------------
class TestAudit:
    def test_audit_list_and_csv_export(self, api_client):
        admin = _signup(api_client, "aud")
        # Generate a couple audit-emitting ops
        api_client.put(f"{BASE_URL}/api/settings",
                        json={"auto_sync_hubspot": True, "auto_notify_slack": True,
                              "auto_trigger_n8n": False},
                        headers=admin["headers"])
        api_client.post(f"{BASE_URL}/api/workspace/invites",
                        json={"email": f"TEST_aux_{uuid.uuid4().hex[:6]}@sdr.ai",
                              "role": "sdr"},
                        headers=admin["headers"])

        r = api_client.get(f"{BASE_URL}/api/audit", headers=admin["headers"])
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 2
        actions = [row["action"] for row in rows]
        assert "update.settings" in actions
        assert "create.invite" in actions

        # CSV export
        r_csv = api_client.get(f"{BASE_URL}/api/audit/export.csv",
                                headers=admin["headers"])
        assert r_csv.status_code == 200, r_csv.text
        ct = r_csv.headers.get("content-type", "")
        assert "text/csv" in ct, f"expected text/csv, got: {ct}"
        text = r_csv.text
        first_line = text.splitlines()[0]
        assert first_line == "at,user_email,action,resource_type,resource_id,old_value,new_value"
        # at least one data row (has our email — emails are stored lowercase)
        assert admin["email"].lower() in text.lower()


# ---------------- Emails (Resend mock) ----------------
class TestEmails:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "em")

    @pytest.fixture(scope="class")
    def lead(self, api_client, admin):
        return _create_and_wait(api_client, admin, "em")

    def test_send_email_mock(self, api_client, admin, lead):
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/emails",
                             json={"to": lead["email"],
                                   "subject": "TEST intro",
                                   "body": "Hello there"},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        assert len(upd["emails"]) >= 1
        msg = upd["emails"][-1]
        assert msg["status"] == "sent"
        assert msg["provider"] == "resend-mock"
        # activity email_sent with mocked=true
        acts = [a for a in upd["activities"] if a["type"] == "email_sent"]
        assert acts, "email_sent activity missing"
        assert acts[-1]["metadata"].get("mocked") is True

    def test_save_as_draft(self, api_client, admin, lead):
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/emails",
                             json={"to": lead["email"],
                                   "subject": "TEST draft",
                                   "body": "Draft body",
                                   "save_as_draft": True},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        msg = upd["emails"][-1]
        assert msg["status"] == "draft"
        assert any(a["type"] == "email_draft" for a in upd["activities"])

    def test_schedule_at_future(self, api_client, admin, lead):
        # schedule 1 day in future
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/emails",
                             json={"to": lead["email"],
                                   "subject": "TEST scheduled",
                                   "body": "Scheduled body",
                                   "schedule_at": future},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        msg = upd["emails"][-1]
        assert msg["status"] == "scheduled"
        assert any(a["type"] == "email_scheduled" for a in upd["activities"])

    def test_resend_webhook_updates_status_to_delivered(self, api_client, admin, lead):
        # Send an email to get a mock provider_message_id
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/emails",
                             json={"to": lead["email"],
                                   "subject": "TEST wh",
                                   "body": "hook body"},
                             headers=admin["headers"])
        assert r.status_code == 200
        upd = r.json()
        msg = upd["emails"][-1]
        pmid = msg["provider_message_id"]
        assert pmid, "no provider_message_id from mock"

        # Call webhook (public — no auth)
        rw = requests.post(f"{BASE_URL}/api/webhooks/resend",
                            json={"type": "email.delivered",
                                  "data": {"email_id": pmid}}, timeout=15)
        assert rw.status_code == 200, rw.text

        # Verify email status now 'delivered'
        r_get = api_client.get(f"{BASE_URL}/api/leads/{lead['id']}",
                                headers=admin["headers"])
        assert r_get.status_code == 200
        emails = r_get.json()["emails"]
        matched = [e for e in emails if e["provider_message_id"] == pmid]
        assert matched, "email not found after webhook"
        assert matched[0]["status"] == "delivered"
        assert matched[0].get("delivered_at")


# ---------------- Meetings ----------------
class TestMeetings:
    @pytest.fixture(scope="class")
    def admin(self, api_client):
        return _signup(api_client, "mt")

    @pytest.fixture(scope="class")
    def lead(self, api_client, admin):
        return _create_and_wait(api_client, admin, "mt")

    def test_propose_returns_three_slots(self, api_client, admin, lead):
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/meetings/propose",
                             json={"duration_min": 30},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert "slots" in d and isinstance(d["slots"], list) and len(d["slots"]) == 3
        for s in d["slots"]:
            assert "start" in s and "end" in s and s["duration_min"] == 30
        assert d.get("title_suggestion")
        assert d.get("description_suggestion")
        assert d["duration_min"] == 30

    def test_confirm_transitions_stage_and_ics(self, api_client, admin, lead):
        from datetime import datetime, timezone, timedelta
        start = (datetime.now(timezone.utc) + timedelta(days=1, hours=2)).isoformat()
        r = api_client.post(f"{BASE_URL}/api/leads/{lead['id']}/meetings",
                             json={"title": "TEST intro call",
                                   "description": "Phase 4 meeting",
                                   "start": start,
                                   "duration_min": 30,
                                   "attendee_emails": [lead["email"]]},
                             headers=admin["headers"])
        assert r.status_code == 200, r.text
        upd = r.json()
        assert len(upd["meetings"]) >= 1
        m = upd["meetings"][-1]
        assert m["gcal_template_url"].startswith("https://calendar.google.com/calendar/render?")
        # stage transitioned to demo_scheduled (lead was 'qualified')
        assert upd["pipeline_stage"] == "demo_scheduled", \
            f"expected demo_scheduled, got {upd['pipeline_stage']}"
        # stage_history entry
        assert any(h["to_stage"] == "demo_scheduled" for h in upd["stage_history"])

        # ICS endpoint
        r_ics = api_client.get(
            f"{BASE_URL}/api/leads/{lead['id']}/meetings/{m['id']}/ics",
            headers=admin["headers"])
        assert r_ics.status_code == 200, r_ics.text
        assert "BEGIN:VCALENDAR" in r_ics.text
        assert "END:VCALENDAR" in r_ics.text


# ---------------- Integrations (Resend mocked) ----------------
class TestResendIntegration:
    def test_resend_test_returns_mocked_without_key(self, api_client):
        u = _signup(api_client, "rs")
        r = api_client.post(f"{BASE_URL}/api/integrations/resend/test",
                             headers=u["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "mocked", d

    def test_status_includes_resend(self, api_client):
        u = _signup(api_client, "rss")
        r = api_client.get(f"{BASE_URL}/api/integrations/status",
                            headers=u["headers"])
        assert r.status_code == 200
        d = r.json()
        assert "resend" in d
        assert "configured" in d["resend"] and "mode" in d["resend"]
        assert d["resend"]["mode"] in ("live", "mock")


# ---------------- Advanced analytics ----------------
class TestAdvancedAnalytics:
    def test_advanced_shape(self, api_client):
        admin = _signup(api_client, "adv")
        # need at least one lead for meaningful values
        _create_and_wait(api_client, admin, "adv")

        r = api_client.get(f"{BASE_URL}/api/analytics/advanced",
                            headers=admin["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("funnel", "pipeline_value_usd", "revenue_forecast_usd",
                  "avg_cycle_days", "source_performance", "stage_conversions",
                  "win_rate", "top_sdrs", "ai_recommendation_accuracy",
                  "avg_deal_usd"):
            assert k in d, f"missing advanced key {k}"

        # Funnel: list of 7 {stage,count}
        assert isinstance(d["funnel"], list) and len(d["funnel"]) == 7
        stages_in_order = [row["stage"] for row in d["funnel"]]
        assert stages_in_order == PIPELINE_STAGES
        for row in d["funnel"]:
            assert "count" in row and isinstance(row["count"], int)

        assert isinstance(d["pipeline_value_usd"], int)
        assert isinstance(d["revenue_forecast_usd"], int)
        assert isinstance(d["avg_cycle_days"], (int, float))
        assert isinstance(d["source_performance"], list)
        assert isinstance(d["stage_conversions"], list)
        assert isinstance(d["win_rate"], (int, float))
        assert isinstance(d["top_sdrs"], list)
        for row in d["top_sdrs"]:
            assert "full_name" in row and "win_rate" in row
        assert isinstance(d["ai_recommendation_accuracy"], (int, float))
        assert isinstance(d["avg_deal_usd"], int)


# ---------------- Cross-workspace isolation ----------------
class TestWorkspaceIsolation:
    def test_isolation_leads_audit_notifications_prompts(self, api_client):
        wsA = _signup(api_client, "isoA")
        wsB = _signup(api_client, "isoB")

        # A creates lead + custom prompt + settings change
        _create_and_wait(api_client, wsA, "iso")
        api_client.put(f"{BASE_URL}/api/prompts/qualification",
                        json={"template": "A CUSTOM PROMPT " + uuid.uuid4().hex[:8]},
                        headers=wsA["headers"])
        api_client.put(f"{BASE_URL}/api/settings",
                        json={"auto_sync_hubspot": True, "auto_notify_slack": True,
                              "auto_trigger_n8n": False},
                        headers=wsA["headers"])

        # B should see 0 leads, empty audit, empty notifications, default prompt v1
        rL = api_client.get(f"{BASE_URL}/api/leads", headers=wsB["headers"])
        assert rL.status_code == 200 and rL.json() == []

        rA = api_client.get(f"{BASE_URL}/api/audit", headers=wsB["headers"])
        assert rA.status_code == 200 and rA.json() == []

        rN = api_client.get(f"{BASE_URL}/api/notifications", headers=wsB["headers"])
        assert rN.status_code == 200
        assert rN.json()["items"] == [] or all(
            i.get("workspace_id") in (None, wsB["id"]) for i in rN.json()["items"])

        rP = api_client.get(f"{BASE_URL}/api/prompts/qualification",
                             headers=wsB["headers"])
        assert rP.status_code == 200
        assert "A CUSTOM PROMPT" not in rP.json()["template"]
        assert rP.json()["version"] == 1


# ---------------- Regression: Phase 1-3 extended fields ----------------
class TestRegressionExtendedLead:
    def test_lead_has_phase4_fields(self, api_client):
        admin = _signup(api_client, "rg")
        lead = _create_and_wait(api_client, admin, "rg")
        for k in ("pipeline_stage", "stage_history", "notes", "emails",
                  "meetings", "assigned_to", "assignment_reason"):
            assert k in lead, f"lead missing phase 4 field {k}"
        assert isinstance(lead["stage_history"], list) and len(lead["stage_history"]) >= 1
        assert lead["pipeline_stage"] in PIPELINE_STAGES
