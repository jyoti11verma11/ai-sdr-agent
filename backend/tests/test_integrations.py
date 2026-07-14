"""Phase 2 backend tests — HubSpot / Slack / n8n integrations orchestrator.

Every test class creates its OWN user (settings are per-owner) so xdist parallel
workers cannot race on shared settings/state.

Covers:
- GET /api/integrations/status (default mock modes)
- POST /api/integrations/{provider}/test (mock + error paths)
- POST /api/integrations/invalidprovider/test → 400
- Invalid HubSpot / Slack credentials → status=error via real HTTP
- POST /api/leads pipeline emits full activity chain incl. slack_high_priority
- GET /api/integrations/logs (list + provider filter + owner isolation)
- POST /api/leads/{id}/retry-sync (success + 400 for unqualified + 404)
- PATCH /api/leads/{id}/status without HubSpot token (graceful skip)
- n8n retry logic with unreachable webhook (attempts=3, elapsed >= 3s)
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

DEFAULT_SETTINGS = {
    "hubspot_token": None,
    "slack_webhook_url": None,
    "n8n_webhook_url": None,
    "auto_sync_hubspot": True,
    "auto_notify_slack": True,
    "auto_trigger_n8n": False,
}


def _new_user(api_client, tag: str) -> dict:
    """Sign up a fresh isolated user."""
    email = f"TEST_{tag}_{uuid.uuid4().hex[:8]}@sdr.ai"
    r = api_client.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "phase2pw", "full_name": f"{tag} tester",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    return {
        "email": email, "id": data["user"]["id"], "token": data["token"],
        "headers": {"Authorization": f"Bearer {data['token']}",
                    "Content-Type": "application/json"},
    }


def _reset_settings(api_client, headers, extra: dict | None = None):
    payload = dict(DEFAULT_SETTINGS)
    if extra:
        payload.update(extra)
    r = api_client.put(f"{BASE_URL}/api/settings", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- Integrations status ----------------
class TestIntegrationsStatus:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "status")

    def test_status_default_all_mock(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        r = api_client.get(f"{BASE_URL}/api/integrations/status", headers=user["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        for p in ("hubspot", "slack", "n8n"):
            assert p in data, f"Provider {p} missing from status"
            entry = data[p]
            for k in ("configured", "enabled", "mode", "last_sync", "last_status", "last_message"):
                assert k in entry, f"key {k} missing on {p}: {entry}"
            assert entry["mode"] == "mock", f"{p} not in mock mode (no token) — got {entry}"
            assert entry["configured"] is False

    def test_status_requires_auth(self, api_client):
        r = requests.get(f"{BASE_URL}/api/integrations/status")
        assert r.status_code == 401


# ---------------- Test-connection endpoint ----------------
class TestIntegrationsTestEndpoint:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "testep")

    def test_hubspot_test_returns_mocked_when_no_token(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        r = api_client.post(f"{BASE_URL}/api/integrations/hubspot/test", headers=user["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "mocked"
        assert data["provider"] == "hubspot"

    def test_slack_test_returns_mocked_when_no_webhook(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        r = api_client.post(f"{BASE_URL}/api/integrations/slack/test", headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "mocked"
        assert data["provider"] == "slack"

    def test_n8n_test_returns_mocked_when_no_url(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        r = api_client.post(f"{BASE_URL}/api/integrations/n8n/test", headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "mocked"
        assert data["provider"] == "n8n"

    def test_invalid_provider_returns_400(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/integrations/invalidprovider/test",
                            headers=user["headers"])
        assert r.status_code == 400

    def test_hubspot_invalid_token_returns_error(self, api_client, user):
        _reset_settings(api_client, user["headers"],
                        {"hubspot_token": "pat-na1-invalid-token-abcdef"})
        try:
            r = api_client.post(f"{BASE_URL}/api/integrations/hubspot/test",
                                headers=user["headers"], timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "error", f"Expected error, got {data}"
            msg = (data.get("message") or "").lower()
            assert "401" in msg or "invalid" in msg or "unauthorized" in msg, \
                f"Unexpected error message: {data['message']}"
        finally:
            _reset_settings(api_client, user["headers"])

    def test_slack_invalid_webhook_returns_error(self, api_client, user):
        _reset_settings(api_client, user["headers"],
                        {"slack_webhook_url": "https://hooks.slack.com/services/T00/B00/xxx"})
        try:
            r = api_client.post(f"{BASE_URL}/api/integrations/slack/test",
                                headers=user["headers"], timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "error", f"Expected error, got {data}"
        finally:
            _reset_settings(api_client, user["headers"])


# ---------------- End-to-end lead pipeline ----------------
class TestLeadIntegrationPipeline:
    """Verify full activity chain and integration_logs persistence."""

    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "pipeline")

    @pytest.fixture(scope="class")
    def high_score_lead(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        payload = {
            "name": "TEST HighPri Alice",
            "email": f"TEST_hp_{uuid.uuid4().hex[:6]}@stripe.com",
            "company": "Stripe Payments Inc",
            "job_title": "VP Engineering",
            "website": "https://stripe.com",
            "company_size_hint": "1000+",
            "message": "Budget approved for Q1. Need SOC2. Ready to buy this week. Demo ASAP.",
            "source": "website",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                            headers=user["headers"], timeout=90)
        assert r.status_code == 200, r.text
        return r.json()

    def test_activity_chain_and_metadata(self, high_score_lead):
        lead = high_score_lead
        acts = lead.get("activities", [])
        types_in_order = [a["type"] for a in acts]

        for expected in ("created", "qualified", "email_generated",
                         "hubspot_contact", "hubspot_company", "hubspot_deal",
                         "slack_notified"):
            assert expected in types_in_order, f"Missing {expected}. Got: {types_in_order}"

        def idx(t): return types_in_order.index(t)
        assert idx("created") < idx("qualified") < idx("email_generated")
        assert idx("email_generated") < idx("hubspot_contact") < idx("hubspot_company") < idx("hubspot_deal")
        assert idx("hubspot_deal") < idx("slack_notified")

        score = (lead.get("qualification") or {}).get("score") or 0
        if score >= 85:
            assert "slack_high_priority" in types_in_order, \
                f"Score {score} should trigger slack_high_priority. Got: {types_in_order}"
            assert idx("slack_notified") < idx("slack_high_priority")

        for a in acts:
            if a["type"].startswith("hubspot_") or a["type"].startswith("slack_"):
                md = a.get("metadata") or {}
                for k in ("provider", "action", "status", "data"):
                    assert k in md, f"metadata missing {k} for {a['type']}: {md}"
                assert md["status"] == "mocked", \
                    f"{a['type']} status should be mocked, got {md['status']}"

    def test_status_reflects_last_sync_after_lead(self, api_client, user, high_score_lead):
        r = api_client.get(f"{BASE_URL}/api/integrations/status", headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["hubspot"]["last_sync"] is not None, f"hubspot last_sync missing: {data['hubspot']}"
        assert data["slack"]["last_sync"] is not None, f"slack last_sync missing: {data['slack']}"
        # n8n has auto_trigger_n8n=false → no sync
        assert data["n8n"]["last_sync"] is None, f"n8n should not have synced: {data['n8n']}"


# ---------------- Integration logs ----------------
class TestIntegrationLogs:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "logs")

    @pytest.fixture(scope="class")
    def other_user(self, api_client):
        return _new_user(api_client, "logs_other")

    def test_logs_are_persisted_and_shaped(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        payload = {
            "name": "TEST LogPersist",
            "email": f"TEST_log_{uuid.uuid4().hex[:6]}@corp.com",
            "company": "LogCorp",
            "job_title": "CEO",
            "message": "Ready to buy. Budget approved.",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                            headers=user["headers"], timeout=90)
        assert r.status_code == 200

        r = api_client.get(f"{BASE_URL}/api/integrations/logs", headers=user["headers"])
        assert r.status_code == 200, r.text
        logs = r.json()
        assert isinstance(logs, list) and len(logs) >= 1
        for log in logs[:5]:
            for k in ("id", "owner_id", "provider", "action", "status", "message", "lead_id", "created_at"):
                assert k in log, f"log missing key {k}: {log}"

    def test_logs_provider_filter(self, api_client, user):
        # ensure at least one lead ran (may be from prior test in this class)
        r = api_client.get(f"{BASE_URL}/api/integrations/logs?provider=hubspot",
                           headers=user["headers"])
        assert r.status_code == 200
        logs = r.json()
        assert isinstance(logs, list)
        for log in logs:
            assert log["provider"] == "hubspot", f"provider filter leaked: {log}"

    def test_logs_owner_isolation(self, api_client, user, other_user):
        # user has logs from previous tests; other_user has none
        r_other = api_client.get(f"{BASE_URL}/api/integrations/logs",
                                 headers=other_user["headers"])
        assert r_other.status_code == 200
        other_logs = r_other.json()

        r_user = api_client.get(f"{BASE_URL}/api/integrations/logs",
                                headers=user["headers"])
        user_logs = r_user.json()
        assert len(user_logs) >= 1

        user_ids = {l["id"] for l in user_logs}
        other_ids = {l["id"] for l in other_logs}
        assert user_ids.isdisjoint(other_ids), "Owner isolation broken across integration_logs"
        for l in other_logs:
            assert l["owner_id"] == other_user["id"]
        for l in user_logs:
            assert l["owner_id"] == user["id"]

    def test_logs_requires_auth(self, api_client):
        r = requests.get(f"{BASE_URL}/api/integrations/logs")
        assert r.status_code == 401


# ---------------- Retry-sync endpoint ----------------
class TestRetrySync:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "retry")

    def test_retry_sync_appends_activities_and_logs(self, api_client, user):
        _reset_settings(api_client, user["headers"])
        create_payload = {
            "name": "TEST Retry Buyer",
            "email": f"TEST_retry_{uuid.uuid4().hex[:6]}@corp.com",
            "company": "RetryCorp",
            "job_title": "CTO",
            "message": "Budget approved. Need SOC2. Q1 rollout.",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=create_payload,
                            headers=user["headers"], timeout=90)
        assert r.status_code == 200, r.text
        lead_before = r.json()
        lead_id = lead_before["id"]
        acts_before = len(lead_before["activities"])

        r_logs = api_client.get(f"{BASE_URL}/api/integrations/logs?limit=200",
                                headers=user["headers"])
        logs_before = len(r_logs.json())

        r_retry = api_client.post(f"{BASE_URL}/api/leads/{lead_id}/retry-sync",
                                   headers=user["headers"], timeout=60)
        assert r_retry.status_code == 200, r_retry.text
        lead_after = r_retry.json()
        acts_after = len(lead_after["activities"])
        assert acts_after > acts_before, \
            f"Retry did not append activities: before={acts_before} after={acts_after}"

        r_logs2 = api_client.get(f"{BASE_URL}/api/integrations/logs?limit=200",
                                 headers=user["headers"])
        logs_after = len(r_logs2.json())
        assert logs_after > logs_before, \
            f"Retry did not add integration_logs: before={logs_before} after={logs_after}"

    def test_retry_sync_400_when_lead_has_no_qualification(self, api_client, user):
        """Insert a bare lead with no qualification via direct Mongo, then retry."""
        from pymongo import MongoClient
        from pathlib import Path

        env_vals = {}
        for line in Path("/app/backend/.env").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env_vals[k.strip()] = v.strip().strip('"').strip("'")
        mongo_url = env_vals.get("MONGO_URL") or os.environ.get("MONGO_URL")
        db_name = env_vals.get("DB_NAME") or os.environ.get("DB_NAME")
        mc = MongoClient(mongo_url)
        db = mc[db_name]

        lead_id = uuid.uuid4().hex
        bare = {
            "id": lead_id,
            "owner_id": user["id"],
            "name": "TEST BareLead",
            "email": f"TEST_bare_{uuid.uuid4().hex[:6]}@x.com",
            "company": "BareCo",
            "source": "manual",
            "status": "new",
            "qualification": {"score": None},
            "activities": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        db.leads.insert_one(dict(bare))
        try:
            r = api_client.post(f"{BASE_URL}/api/leads/{lead_id}/retry-sync",
                                 headers=user["headers"], timeout=30)
            assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        finally:
            db.leads.delete_one({"id": lead_id})
            mc.close()

    def test_retry_sync_404_unknown_lead(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads/{uuid.uuid4().hex}/retry-sync",
                             headers=user["headers"], timeout=30)
        assert r.status_code == 404


# ---------------- PATCH status graceful skip ----------------
class TestStatusPatchGracefulSkip:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "patch")

    def test_status_patch_no_hubspot_token_does_not_crash(self, api_client, user):
        _reset_settings(api_client, user["headers"])  # no hubspot_token
        payload = {
            "name": "TEST NoHubToken",
            "email": f"TEST_nohub_{uuid.uuid4().hex[:6]}@x.com",
            "company": "NoHubCo",
            "message": "curious buyer with budget",
        }
        r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                            headers=user["headers"], timeout=90)
        assert r.status_code == 200
        lead_id = r.json()["id"]
        r_patch = api_client.patch(f"{BASE_URL}/api/leads/{lead_id}/status",
                                    json={"status": "contacted"},
                                    headers=user["headers"], timeout=30)
        assert r_patch.status_code == 200, r_patch.text
        assert r_patch.json()["status"] == "contacted"


# ---------------- n8n retry backoff ----------------
class TestN8nRetryBackoff:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "n8n")

    def test_n8n_retries_3_times_with_exponential_backoff(self, api_client, user):
        # httpbin.org/status/503 returns 503 fast → predictable retry failure
        unreachable_url = "https://httpbin.org/status/503"
        _reset_settings(api_client, user["headers"], {
            "n8n_webhook_url": unreachable_url,
            "auto_trigger_n8n": True,
        })
        try:
            payload = {
                "name": "TEST N8nRetry",
                "email": f"TEST_n8n_{uuid.uuid4().hex[:6]}@retry.com",
                "company": "RetryN8nCo",
                "message": "budget approved this quarter",
            }
            t0 = time.time()
            r = api_client.post(f"{BASE_URL}/api/leads", json=payload,
                                headers=user["headers"], timeout=120)
            elapsed = time.time() - t0
            assert r.status_code == 200, r.text
            lead = r.json()
            n8n_acts = [a for a in lead["activities"] if a["type"] == "n8n_triggered"]
            assert len(n8n_acts) == 1, \
                f"Expected exactly 1 n8n activity, got: {[a['type'] for a in lead['activities']]}"
            md = n8n_acts[0].get("metadata") or {}
            assert md.get("provider") == "n8n"
            assert md.get("status") == "error", f"expected error, got {md}"
            assert md.get("attempts") == 3, f"expected attempts=3, got {md.get('attempts')}"
            assert elapsed >= 3.0, f"Expected >=3s elapsed (1s + 2s backoff), got {elapsed:.2f}s"
        finally:
            _reset_settings(api_client, user["headers"])
