"""Comprehensive backend tests for AI SDR Agent.

Covers:
- Health
- Auth (signup / login / me / 401)
- Settings (GET/PUT)
- Leads (create with LLM qualification+email, public capture, owner isolation,
  get, list, status update, regenerate email, delete, 404s)
- Analytics (summary + activity)
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


# ---------------- Health ----------------
class TestHealth:
    def test_root_health(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("service") == "AI SDR Agent"
        assert "time" in data


# ---------------- Auth ----------------
class TestAuth:
    def test_signup_creates_user_and_returns_jwt(self, api_client):
        email = f"TEST_signup_{uuid.uuid4().hex[:8]}@sdr.ai"
        payload = {"email": email, "password": "signup1234",
                   "full_name": "Signup Tester"}
        r = api_client.post(f"{BASE_URL}/api/auth/signup", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["user"]["email"] == email.lower()
        assert data["user"]["full_name"] == "Signup Tester"
        assert "id" in data["user"]

    def test_signup_duplicate_email_rejected(self, api_client):
        email = f"TEST_dup_{uuid.uuid4().hex[:8]}@sdr.ai"
        p = {"email": email, "password": "signup1234", "full_name": "Dup"}
        r1 = api_client.post(f"{BASE_URL}/api/auth/signup", json=p)
        assert r1.status_code == 200
        r2 = api_client.post(f"{BASE_URL}/api/auth/signup", json=p)
        assert r2.status_code == 400
        assert "already" in r2.json().get("detail", "").lower()

    def test_login_success(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "demo@sdr.ai", "password": "demo1234"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == "demo@sdr.ai"
        assert isinstance(data["token"], str)

    def test_login_invalid_credentials(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": "demo@sdr.ai", "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_unknown_email(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/auth/login",
                            json={"email": f"noone_{uuid.uuid4().hex[:6]}@sdr.ai",
                                  "password": "whatever"})
        assert r.status_code == 401

    def test_me_returns_current_user(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == "demo@sdr.ai"
        assert "id" in data
        assert "full_name" in data

    def test_me_401_without_token(self, api_client):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401

    def test_me_401_with_bad_token(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/auth/me",
                           headers={"Authorization": "Bearer garbage.token.here"})
        assert r.status_code == 401


# ---------------- Settings ----------------
class TestSettings:
    def test_get_settings_returns_defaults(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/settings", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        # required keys present
        for k in ("hubspot_token", "slack_webhook_url", "n8n_webhook_url",
                  "auto_sync_hubspot", "auto_notify_slack", "auto_trigger_n8n"):
            assert k in data
        assert isinstance(data["auto_sync_hubspot"], bool)
        assert isinstance(data["auto_notify_slack"], bool)
        assert isinstance(data["auto_trigger_n8n"], bool)

    def test_put_settings_updates_and_persists(self, api_client, auth_headers):
        payload = {
            "hubspot_token": None,
            "slack_webhook_url": None,
            "n8n_webhook_url": None,
            "auto_sync_hubspot": True,
            "auto_notify_slack": True,
            "auto_trigger_n8n": True,
        }
        r = api_client.put(f"{BASE_URL}/api/settings", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["auto_trigger_n8n"] is True

        # verify persistence via GET
        r2 = api_client.get(f"{BASE_URL}/api/settings", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["auto_trigger_n8n"] is True

        # reset to defaults for other tests
        payload["auto_trigger_n8n"] = False
        api_client.put(f"{BASE_URL}/api/settings", json=payload, headers=auth_headers)

    def test_settings_requires_auth(self, api_client):
        r = requests.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 401


# ---------------- Leads ----------------
class TestLeads:
    """Lead creation, AI pipeline, CRUD and owner isolation."""

    @pytest.fixture(scope="class")
    def created_lead(self, api_client, auth_headers):
        """Create a high-intent lead that should qualify via LLM or heuristic."""
        payload = {
            "name": "TEST Alice Buyer",
            "email": f"TEST_alice_{uuid.uuid4().hex[:6]}@acme.io",
            "company": "Acme Fintech Inc",
            "job_title": "VP Engineering",
            "website": "https://acme.io",
            "company_size_hint": "501-1000",
            "message": "We have budget approved for Q1 and need a demo ASAP for vendor evaluation. SOC2 compliance required.",
            "source": "website",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                            headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"Lead create failed: {r.status_code} {r.text}"
        return r.json()

    def test_create_lead_qualification_and_email(self, created_lead):
        lead = created_lead
        # Basic
        assert lead["name"] == "TEST Alice Buyer"
        assert lead["company"] == "Acme Fintech Inc"
        assert "id" in lead and "owner_id" in lead
        assert lead["status"] in ("qualified", "disqualified", "qualifying")

        # Qualification filled
        q = lead.get("qualification") or {}
        assert q.get("score") is not None, f"Missing score: {q}"
        assert 0 <= q["score"] <= 100
        assert q.get("industry"), f"Missing industry: {q}"
        assert q.get("buying_intent"), f"Missing buying_intent: {q}"
        assert q.get("recommended_action"), f"Missing recommended_action: {q}"
        assert q.get("qualification_summary"), "Missing qualification_summary"
        assert isinstance(q.get("key_signals"), list) and len(q["key_signals"]) >= 1

        # For a high-intent lead we expect qualified status (score >= 50)
        assert q["score"] >= 50, f"Expected high score for high-intent lead, got {q['score']}"
        assert lead["status"] == "qualified"

        # Generated email
        em = lead.get("generated_email") or {}
        assert em.get("subject"), "email subject missing"
        assert em.get("body"), "email body missing"
        assert len(em["body"]) > 30

        # Activities include the required lifecycle types
        act_types = {a.get("type") for a in lead.get("activities", [])}
        for expected in ("created", "qualified", "email_generated",
                         "hubspot_sync", "slack_notified"):
            assert expected in act_types, f"Missing activity: {expected}. Got {act_types}"

        # Mock integrations logged with mocked status
        for a in lead["activities"]:
            if a["type"] == "hubspot_sync":
                assert a.get("metadata", {}).get("status") == "mocked"
            if a["type"] == "slack_notified":
                assert a.get("metadata", {}).get("status") == "mocked"

    def test_create_lead_requires_auth(self, api_client):
        r = requests.post(f"{BASE_URL}/api/leads",
                          json={"name": "x", "email": "x@x.com", "company": "X"})
        assert r.status_code == 401

    def test_public_lead_capture(self, api_client):
        payload = {
            "name": "TEST Public Peter",
            "email": f"TEST_public_{uuid.uuid4().hex[:6]}@corp.com",
            "company": "PublicCorp SaaS",
            "job_title": "Head of Ops",
            "message": "Interested in pricing and evaluating for our team.",
            "source": "public-form",
        }
        r = requests.post(
            f"{BASE_URL}/api/leads/public",
            params={"owner_email": "demo@sdr.ai"},
            json=payload, timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "TEST Public Peter"
        assert data.get("qualification", {}).get("score") is not None
        assert data.get("generated_email", {}).get("subject")

    def test_public_lead_unknown_owner_404(self, api_client):
        r = requests.post(
            f"{BASE_URL}/api/leads/public",
            params={"owner_email": f"nobody_{uuid.uuid4().hex[:6]}@nowhere.com"},
            json={"name": "x", "email": "x@x.com", "company": "X"}, timeout=30,
        )
        assert r.status_code == 404

    def test_list_leads_owner_isolation(self, api_client, auth_headers,
                                         created_lead, secondary_user):
        # demo user can see created_lead
        r = api_client.get(f"{BASE_URL}/api/leads", headers=auth_headers)
        assert r.status_code == 200
        ids = [l["id"] for l in r.json()]
        assert created_lead["id"] in ids

        # secondary user should NOT see demo's lead
        r2 = api_client.get(f"{BASE_URL}/api/leads",
                            headers=secondary_user["headers"])
        assert r2.status_code == 200
        other_ids = [l["id"] for l in r2.json()]
        assert created_lead["id"] not in other_ids

    def test_get_single_lead(self, api_client, auth_headers, created_lead):
        r = api_client.get(f"{BASE_URL}/api/leads/{created_lead['id']}",
                           headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == created_lead["id"]

    def test_get_lead_404_for_other_user(self, api_client, secondary_user,
                                          created_lead):
        r = api_client.get(f"{BASE_URL}/api/leads/{created_lead['id']}",
                           headers=secondary_user["headers"])
        assert r.status_code == 404

    def test_get_lead_404_unknown_id(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/leads/{uuid.uuid4()}",
                           headers=auth_headers)
        assert r.status_code == 404

    def test_update_status_appends_activity(self, api_client, auth_headers,
                                             created_lead):
        r = api_client.patch(
            f"{BASE_URL}/api/leads/{created_lead['id']}/status",
            json={"status": "contacted"}, headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "contacted"
        types_msgs = [(a["type"], a["message"]) for a in data["activities"]]
        assert any(t == "status_change" for t, _ in types_msgs)

    def test_regenerate_email(self, api_client, auth_headers, created_lead):
        original_subject = created_lead["generated_email"]["subject"]
        r = api_client.post(
            f"{BASE_URL}/api/leads/{created_lead['id']}/regenerate-email",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["generated_email"]["subject"]
        assert data["generated_email"]["body"]
        # At least one email_generated activity (initial + regen)
        gen_count = sum(1 for a in data["activities"] if a["type"] == "email_generated")
        assert gen_count >= 2

    def test_delete_lead_and_verify_removal(self, api_client, auth_headers):
        # Create a throwaway lead
        payload = {
            "name": "TEST DeleteMe",
            "email": f"TEST_del_{uuid.uuid4().hex[:6]}@x.com",
            "company": "DeleteCo",
            "message": "curious",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                            headers=auth_headers, timeout=60)
        assert r.status_code == 200
        lead_id = r.json()["id"]

        r_del = api_client.delete(f"{BASE_URL}/api/leads/{lead_id}",
                                   headers=auth_headers)
        assert r_del.status_code == 200
        assert r_del.json().get("ok") is True

        r_get = api_client.get(f"{BASE_URL}/api/leads/{lead_id}",
                               headers=auth_headers)
        assert r_get.status_code == 404

    def test_delete_unknown_lead_404(self, api_client, auth_headers):
        r = api_client.delete(f"{BASE_URL}/api/leads/{uuid.uuid4()}",
                              headers=auth_headers)
        assert r.status_code == 404


# ---------------- Analytics ----------------
class TestAnalytics:
    def test_summary_shape(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/analytics/summary",
                           headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total_leads", "qualified_leads", "conversion_rate",
                  "avg_score", "score_distribution", "by_industry",
                  "timeline", "ai_insights"):
            assert k in data, f"Missing key: {k}"
        assert isinstance(data["total_leads"], int)
        assert isinstance(data["score_distribution"], list) and len(data["score_distribution"]) == 4
        assert isinstance(data["by_industry"], list)
        assert isinstance(data["timeline"], list)
        assert isinstance(data["ai_insights"], list)
        assert data["total_leads"] >= 1

    def test_activity_endpoint(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/analytics/activity",
                           headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "lead_id" in data[0]
            assert "type" in data[0]
            assert "message" in data[0]

    def test_analytics_requires_auth(self, api_client):
        r = requests.get(f"{BASE_URL}/api/analytics/summary")
        assert r.status_code == 401
