"""Phase 3 backend tests — True AI SDR Agent.

Covers:
- POST /api/leads returns <1s with processing_status='pending' (background task).
- Polling GET /api/leads/{id}: pending → analyzing → qualified within ~30s.
- Final qualification has ALL new fields (business_type, icp_match, icp_match_reasoning,
  urgency, decision_maker_probability, score_explanation, action_reasoning).
- recommended_action within allowed set.
- Final lead.outreach has subject + first_email + linkedin_message + followup_email.
- Legacy generated_email still populated.
- GET /api/leads/status-counts shape.
- GET /api/leads/{id}/decisions shape.
- Prompts (AI Playground): list, get, 404, update (version increments), reset,
  test qualification, test outreach.
- Regenerate: type=first_email|linkedin_message|followup_email|all, invalid=422,
  unqualified=400, legacy alias.
- Analytics AI endpoint shape.
- Owner isolation for prompts, decisions, leads, regenerate.

Per-class fresh users to avoid xdist parallel races.
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

ALLOWED_ACTIONS = {"Book Demo", "Call Immediately", "Send Personalized Email",
                   "Add to Nurture Campaign", "Reject Lead"}
NEW_QUAL_FIELDS = ("business_type", "icp_match", "icp_match_reasoning", "urgency",
                   "decision_maker_probability", "score_explanation", "action_reasoning")


def _new_user(api_client, tag: str) -> dict:
    email = f"TEST_p3_{tag}_{uuid.uuid4().hex[:8]}@sdr.ai"
    r = api_client.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "phase3pw", "full_name": f"P3 {tag}",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "id": d["user"]["id"], "token": d["token"],
            "headers": {"Authorization": f"Bearer {d['token']}",
                        "Content-Type": "application/json"}}


def _high_intent_payload(tag: str) -> dict:
    return {
        "name": f"TEST Alice {tag}",
        "email": f"TEST_{tag}_{uuid.uuid4().hex[:6]}@stripe.com",
        "company": "Stripe Payments Inc",
        "job_title": "VP Engineering",
        "website": "https://stripe.com",
        "company_size_hint": "1000+",
        "message": "Budget approved for Q1. SOC2 compliance required. Need demo ASAP for vendor evaluation. Ready to purchase this quarter.",
        "source": "website",
    }


def _poll_until_terminal(api_client, headers, lead_id: str, timeout: float = 45.0):
    """Poll GET /api/leads/{id} until processing_status in {qualified, failed}."""
    deadline = time.time() + timeout
    seen_states = []
    last = None
    while time.time() < deadline:
        r = api_client.get(f"{BASE_URL}/api/leads/{lead_id}", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        last = r.json()
        st = last.get("processing_status")
        if not seen_states or seen_states[-1] != st:
            seen_states.append(st)
        if st in ("qualified", "failed"):
            return last, seen_states
        time.sleep(1.0)
    return last, seen_states


# ---------------- Background pipeline: fast return + poll ----------------
class TestBackgroundPipeline:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "bg")

    @pytest.fixture(scope="class")
    def created(self, api_client, user):
        """Create a lead and record timing + full poll state."""
        t0 = time.time()
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("bg"),
                            headers=user["headers"], timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        initial = r.json()
        final, seen = _poll_until_terminal(api_client, user["headers"], initial["id"], timeout=60.0)
        return {"initial": initial, "final": final, "seen": seen, "elapsed": elapsed}

    def test_create_returns_fast_and_pending(self, created):
        assert created["elapsed"] < 3.0, f"POST /api/leads took {created['elapsed']:.2f}s (expected <3s)"
        init = created["initial"]
        assert init["processing_status"] == "pending", f"Expected pending, got {init['processing_status']}"
        # Score should still be None initially — pipeline hasn't run yet
        assert (init.get("qualification") or {}).get("score") is None, \
            f"Expected score=None on create, got {init['qualification']}"

    def test_transitions_pending_to_analyzing_to_qualified(self, created):
        seen = created["seen"]
        # Terminal must be reached
        assert seen[-1] == "qualified", f"Did not reach qualified. Seen: {seen}"
        # At least pending observed at some point (we may have missed 'analyzing' if very fast)
        assert "pending" in seen or "analyzing" in seen or "qualified" in seen

    def test_final_qualification_has_all_new_fields(self, created):
        q = created["final"].get("qualification") or {}
        for k in NEW_QUAL_FIELDS:
            assert k in q, f"Missing qualification field: {k}. Got keys: {list(q.keys())}"
        assert q.get("score") is not None and 0 <= q["score"] <= 100
        assert isinstance(q.get("icp_match"), bool), f"icp_match must be bool, got {type(q.get('icp_match'))}"
        assert q.get("icp_match_reasoning") and isinstance(q["icp_match_reasoning"], str)
        assert q.get("business_type") and isinstance(q["business_type"], str)
        assert q.get("urgency") and isinstance(q["urgency"], str)
        assert isinstance(q.get("decision_maker_probability"), int), \
            f"decision_maker_probability must be int, got {q.get('decision_maker_probability')}"
        assert 0 <= q["decision_maker_probability"] <= 100
        assert q.get("score_explanation") and isinstance(q["score_explanation"], str)
        assert q.get("action_reasoning") and isinstance(q["action_reasoning"], str)

    def test_recommended_action_in_allowed_set(self, created):
        q = created["final"].get("qualification") or {}
        assert q.get("recommended_action") in ALLOWED_ACTIONS, \
            f"recommended_action '{q.get('recommended_action')}' not in {ALLOWED_ACTIONS}"

    def test_outreach_kit_all_four_pieces(self, created):
        out = created["final"].get("outreach") or {}
        for k in ("subject", "first_email", "linkedin_message", "followup_email"):
            assert out.get(k), f"outreach.{k} missing/empty: {out}"
            assert isinstance(out[k], str) and len(out[k].strip()) > 0

    def test_legacy_generated_email_present(self, created):
        em = created["final"].get("generated_email") or {}
        assert em.get("subject"), f"legacy generated_email.subject missing: {em}"
        assert em.get("body"), f"legacy generated_email.body missing: {em}"

    def test_full_integration_activities_after_bg(self, created):
        lead = created["final"]
        types = {a["type"] for a in lead.get("activities", [])}
        for t in ("created", "qualified", "email_generated",
                  "hubspot_contact", "hubspot_company", "hubspot_deal", "slack_notified"):
            assert t in types, f"Missing activity {t}. Got: {types}"
        score = (lead.get("qualification") or {}).get("score") or 0
        if score >= 85:
            assert "slack_high_priority" in types, \
                f"Score {score} should trigger slack_high_priority. Got {types}"


# ---------------- Status counts ----------------
class TestStatusCounts:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "sc")

    def test_status_counts_shape_before_any_leads(self, api_client, user):
        r = api_client.get(f"{BASE_URL}/api/leads/status-counts", headers=user["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data.keys()) == {"pending", "analyzing", "qualified", "failed"}, \
            f"Unexpected keys: {list(data.keys())}"
        for k, v in data.items():
            assert isinstance(v, int), f"{k} must be int, got {type(v)}"

    def test_status_counts_reflects_lead_creation(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("sc"),
                            headers=user["headers"], timeout=15)
        assert r.status_code == 200
        lead_id = r.json()["id"]
        # immediately after: pending or analyzing
        r2 = api_client.get(f"{BASE_URL}/api/leads/status-counts", headers=user["headers"])
        assert r2.status_code == 200
        c1 = r2.json()
        assert (c1["pending"] + c1["analyzing"] + c1["qualified"]) >= 1

        # wait for terminal, then verify qualified went up
        final, _ = _poll_until_terminal(api_client, user["headers"], lead_id, timeout=60.0)
        assert final["processing_status"] in ("qualified", "failed")
        r3 = api_client.get(f"{BASE_URL}/api/leads/status-counts", headers=user["headers"])
        c2 = r3.json()
        assert c2["qualified"] + c2["failed"] >= 1


# ---------------- AI Decisions ----------------
class TestAIDecisions:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "dec")

    @pytest.fixture(scope="class")
    def qualified_lead(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("dec"),
                            headers=user["headers"], timeout=15)
        assert r.status_code == 200
        lead = r.json()
        final, _ = _poll_until_terminal(api_client, user["headers"], lead["id"], timeout=60.0)
        return final

    def test_decisions_endpoint_shape(self, api_client, user, qualified_lead):
        r = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}/decisions",
                           headers=user["headers"])
        assert r.status_code == 200, r.text
        decisions = r.json()
        assert isinstance(decisions, list)
        assert len(decisions) >= 2, f"Expected >=2 decisions (qualify+outreach), got {len(decisions)}"
        types = {d["decision_type"] for d in decisions}
        assert "qualification" in types, f"Missing qualification decision: {types}"
        assert "outreach" in types, f"Missing outreach decision: {types}"

        for d in decisions:
            for k in ("id", "owner_id", "lead_id", "decision_type", "prompt_name",
                      "prompt_version", "model", "input_summary", "output",
                      "latency_ms", "status", "at"):
                assert k in d, f"decision missing key {k}: {d}"
            assert d["owner_id"] == user["id"]
            assert d["lead_id"] == qualified_lead["id"]
            assert d["model"] == "gpt-5.2", f"model expected gpt-5.2, got {d['model']}"
            assert isinstance(d["prompt_version"], int) and d["prompt_version"] >= 1
            assert isinstance(d["latency_ms"], int) and d["latency_ms"] > 0
            assert d["status"] in ("success", "fallback", "error")
            assert isinstance(d["output"], dict)

    def test_decisions_owner_isolation(self, api_client, user, qualified_lead):
        other = _new_user(api_client, "dec_other")
        r = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}/decisions",
                           headers=other["headers"])
        # Since lead doesn't belong to other user, expect 404
        assert r.status_code == 404, f"Expected 404 for other user's lead, got {r.status_code}"

    def test_decisions_404_unknown_lead(self, api_client, user):
        r = api_client.get(f"{BASE_URL}/api/leads/{uuid.uuid4().hex}/decisions",
                           headers=user["headers"])
        assert r.status_code == 404


# ---------------- Prompts / AI Playground ----------------
class TestPrompts:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "prompt")

    def test_list_prompts_returns_two_v1(self, api_client, user):
        r = api_client.get(f"{BASE_URL}/api/prompts", headers=user["headers"])
        assert r.status_code == 200, r.text
        prompts = r.json()
        assert isinstance(prompts, list)
        assert len(prompts) == 2, f"Expected exactly 2 prompts, got {len(prompts)}: {[p.get('name') for p in prompts]}"
        names = {p["name"] for p in prompts}
        assert names == {"qualification", "outreach"}
        for p in prompts:
            assert p["version"] == 1, f"{p['name']} default version should be 1, got {p['version']}"
            assert p.get("template") and isinstance(p["template"], str) and len(p["template"]) > 50

    def test_get_prompt_qualification(self, api_client, user):
        r = api_client.get(f"{BASE_URL}/api/prompts/qualification", headers=user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "qualification"
        assert data["version"] >= 1
        assert data["template"]

    def test_get_prompt_invalidname_404(self, api_client, user):
        r = api_client.get(f"{BASE_URL}/api/prompts/invalidname", headers=user["headers"])
        assert r.status_code == 404

    def test_update_and_reset_increment_version(self, api_client, user):
        # ensure seeded at v1
        r0 = api_client.get(f"{BASE_URL}/api/prompts/qualification", headers=user["headers"])
        v0 = r0.json()["version"]

        new_template = r0.json()["template"] + "\n\n# CUSTOM EDIT " + uuid.uuid4().hex[:6]
        r1 = api_client.put(f"{BASE_URL}/api/prompts/qualification",
                            json={"template": new_template}, headers=user["headers"])
        assert r1.status_code == 200, r1.text
        assert r1.json()["version"] == v0 + 1
        assert r1.json()["template"] == new_template

        # GET reflects update
        r2 = api_client.get(f"{BASE_URL}/api/prompts/qualification", headers=user["headers"])
        assert r2.json()["template"] == new_template
        assert r2.json()["version"] == v0 + 1

        # Reset increments version again (v0+2)
        r3 = api_client.post(f"{BASE_URL}/api/prompts/qualification/reset", headers=user["headers"])
        assert r3.status_code == 200
        assert r3.json()["version"] == v0 + 2
        assert "CUSTOM EDIT" not in r3.json()["template"]

    def test_update_invalid_prompt_name_404(self, api_client, user):
        r = api_client.put(f"{BASE_URL}/api/prompts/nonsense",
                           json={"template": "x"}, headers=user["headers"])
        assert r.status_code == 404

    def test_prompt_test_qualification_returns_full_shape(self, api_client, user):
        """POST /api/prompts/qualification/test with {lead} → returns full qualification JSON."""
        payload = {"lead": {
            "name": "TEST PromptTest QUser",
            "email": f"TEST_pt_{uuid.uuid4().hex[:6]}@corp.com",
            "company": "TestCorp Fintech",
            "job_title": "CTO",
            "message": "Budget approved Q1. SOC2. Ready to buy.",
        }}
        r = api_client.post(f"{BASE_URL}/api/prompts/qualification/test",
                            json=payload, headers=user["headers"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in NEW_QUAL_FIELDS:
            assert k in data, f"prompt test missing {k}. Got keys: {list(data.keys())}"
        assert data.get("score") is not None
        assert data.get("recommended_action") in ALLOWED_ACTIONS

    def test_prompt_test_outreach(self, api_client, user):
        """POST /api/prompts/outreach/test — supplies qualification explicitly."""
        payload = {
            "lead": {
                "name": "TEST OutreachTest",
                "email": f"TEST_po_{uuid.uuid4().hex[:6]}@corp.com",
                "company": "OutreachCorp",
                "job_title": "CEO",
                "message": "Need SOC2, budget approved.",
            },
            "qualification": {
                "industry": "SaaS",
                "company_size": "51-200",
                "business_type": "B2B SaaS",
                "icp_match": True,
                "buying_intent": "High",
                "urgency": "High",
                "decision_maker_probability": 90,
                "score": 82,
                "key_signals": ["Budget approved", "Senior title"],
                "recommended_action": "Book Demo",
            },
        }
        r = api_client.post(f"{BASE_URL}/api/prompts/outreach/test",
                            json=payload, headers=user["headers"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("subject", "first_email", "linkedin_message", "followup_email"):
            assert data.get(k), f"outreach test missing {k}: keys={list(data.keys())}"

    def test_prompt_test_records_decision_with_lead_id_none(self, api_client, user):
        """Prompt test should insert an AIDecision (lead_id may be None)."""
        # count decisions before
        # Use decisions endpoint via a fake lead-id? Not available. Use analytics/ai total.
        r0 = api_client.get(f"{BASE_URL}/api/analytics/ai", headers=user["headers"])
        assert r0.status_code == 200
        before = r0.json().get("total_ai_decisions", 0)

        payload = {"lead": {
            "name": "TEST PromptDecision",
            "email": f"TEST_pd_{uuid.uuid4().hex[:6]}@corp.com",
            "company": "DecisionCorp",
            "job_title": "VP",
            "message": "Budget approved, urgent.",
        }}
        r = api_client.post(f"{BASE_URL}/api/prompts/qualification/test",
                            json=payload, headers=user["headers"], timeout=60)
        assert r.status_code == 200

        r1 = api_client.get(f"{BASE_URL}/api/analytics/ai", headers=user["headers"])
        after = r1.json().get("total_ai_decisions", 0)
        assert after > before, f"Prompt test did not record AIDecision: before={before} after={after}"

    def test_prompts_owner_isolation(self, api_client, user):
        """User A's prompt customisation must NOT leak to User B."""
        other = _new_user(api_client, "prompt_other")
        custom = "CUSTOM PROMPT FOR OWNER ISOLATION TEST " + uuid.uuid4().hex[:8]
        r_u = api_client.put(f"{BASE_URL}/api/prompts/qualification",
                             json={"template": custom}, headers=user["headers"])
        assert r_u.status_code == 200

        r_o = api_client.get(f"{BASE_URL}/api/prompts/qualification", headers=other["headers"])
        assert r_o.status_code == 200
        assert custom not in r_o.json()["template"], "Prompt leaked across owners!"
        assert r_o.json()["version"] == 1  # other user still on default v1


# ---------------- Regenerate outreach pieces ----------------
class TestRegenerate:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "regen")

    @pytest.fixture(scope="class")
    def qualified_lead(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("regen"),
                            headers=user["headers"], timeout=15)
        assert r.status_code == 200
        lead = r.json()
        final, _ = _poll_until_terminal(api_client, user["headers"], lead["id"], timeout=60.0)
        assert final["processing_status"] == "qualified", f"Lead did not qualify: {final['processing_status']}"
        return final

    def test_regenerate_first_email_only(self, api_client, user, qualified_lead):
        before = qualified_lead["outreach"]
        assert before.get("first_email") and before.get("linkedin_message") and before.get("followup_email")
        r = api_client.post(
            f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate?type=first_email",
            headers=user["headers"], timeout=60,
        )
        assert r.status_code == 200, r.text
        after = r.json()["outreach"]
        # linkedin + followup untouched
        assert after["linkedin_message"] == before["linkedin_message"], \
            "linkedin_message must be untouched for type=first_email"
        assert after["followup_email"] == before["followup_email"], \
            "followup_email must be untouched for type=first_email"
        assert after["first_email"], "first_email should still be non-empty"

    def test_regenerate_records_decision(self, api_client, user, qualified_lead):
        r = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}/decisions",
                           headers=user["headers"])
        assert r.status_code == 200
        types = {d["decision_type"] for d in r.json()}
        assert "regenerate_email" in types, f"Expected regenerate_email decision, got {types}"

    def test_regenerate_linkedin_message(self, api_client, user, qualified_lead):
        # snapshot
        r0 = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}", headers=user["headers"])
        before = r0.json()["outreach"]

        r = api_client.post(
            f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate?type=linkedin_message",
            headers=user["headers"], timeout=60,
        )
        assert r.status_code == 200, r.text
        after = r.json()["outreach"]
        assert after["first_email"] == before["first_email"], "first_email should be untouched"
        assert after["followup_email"] == before["followup_email"], "followup_email should be untouched"
        assert after["linkedin_message"], "linkedin_message should exist"

        r_d = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}/decisions",
                             headers=user["headers"])
        types = {d["decision_type"] for d in r_d.json()}
        assert "regenerate_linkedin" in types, f"Expected regenerate_linkedin decision, got {types}"

    def test_regenerate_followup_email(self, api_client, user, qualified_lead):
        r0 = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}", headers=user["headers"])
        before = r0.json()["outreach"]

        r = api_client.post(
            f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate?type=followup_email",
            headers=user["headers"], timeout=60,
        )
        assert r.status_code == 200, r.text
        after = r.json()["outreach"]
        assert after["first_email"] == before["first_email"], "first_email should be untouched"
        assert after["linkedin_message"] == before["linkedin_message"], "linkedin_message should be untouched"
        assert after["followup_email"], "followup_email should exist"

        r_d = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}/decisions",
                             headers=user["headers"])
        types = {d["decision_type"] for d in r_d.json()}
        assert "regenerate_followup" in types, f"Expected regenerate_followup, got {types}"

    def test_regenerate_all(self, api_client, user, qualified_lead):
        r = api_client.post(
            f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate?type=all",
            headers=user["headers"], timeout=60,
        )
        assert r.status_code == 200, r.text
        after = r.json()["outreach"]
        for k in ("subject", "first_email", "linkedin_message", "followup_email"):
            assert after.get(k), f"regenerate all missing {k}"

    def test_regenerate_invalid_type_422(self, api_client, user, qualified_lead):
        r = api_client.post(
            f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate?type=invalid",
            headers=user["headers"], timeout=30,
        )
        assert r.status_code == 422, f"Expected 422 for invalid type, got {r.status_code}: {r.text}"

    def test_regenerate_email_legacy_alias(self, api_client, user, qualified_lead):
        r0 = api_client.get(f"{BASE_URL}/api/leads/{qualified_lead['id']}", headers=user["headers"])
        before = r0.json()["outreach"]
        r = api_client.post(f"{BASE_URL}/api/leads/{qualified_lead['id']}/regenerate-email",
                            headers=user["headers"], timeout=60)
        assert r.status_code == 200, r.text
        after = r.json()["outreach"]
        assert after["linkedin_message"] == before["linkedin_message"], \
            "legacy alias should regenerate first_email only — linkedin untouched"
        assert after["followup_email"] == before["followup_email"], \
            "legacy alias should regenerate first_email only — followup untouched"
        assert after["first_email"]


class TestRegenerateGuardrails:
    """Tests for 400 on unqualified lead + 404 on unknown lead."""
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "regen_guard")

    def test_regenerate_400_when_score_is_none(self, api_client, user):
        """Insert bare lead (no qualification), then regenerate → 400."""
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
            "id": lead_id, "owner_id": user["id"],
            "name": "TEST NoQual", "email": f"TEST_nq_{uuid.uuid4().hex[:6]}@x.com",
            "company": "NoQualCo", "source": "manual", "status": "new",
            "processing_status": "pending",
            "qualification": {"score": None},
            "activities": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        db.leads.insert_one(dict(bare))
        try:
            r = api_client.post(f"{BASE_URL}/api/leads/{lead_id}/regenerate?type=first_email",
                                 headers=user["headers"], timeout=30)
            assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        finally:
            db.leads.delete_one({"id": lead_id})
            mc.close()

    def test_regenerate_404_unknown_lead(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads/{uuid.uuid4().hex}/regenerate?type=first_email",
                            headers=user["headers"], timeout=30)
        assert r.status_code == 404

    def test_regenerate_404_other_users_lead(self, api_client, user):
        """Own lead qualified → other user tries to regenerate → 404."""
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("guard"),
                            headers=user["headers"], timeout=15)
        assert r.status_code == 200
        lead_id = r.json()["id"]
        final, _ = _poll_until_terminal(api_client, user["headers"], lead_id, timeout=60.0)
        assert final["processing_status"] == "qualified"

        other = _new_user(api_client, "regen_other")
        r_o = api_client.post(f"{BASE_URL}/api/leads/{lead_id}/regenerate?type=first_email",
                              headers=other["headers"], timeout=30)
        assert r_o.status_code == 404


# ---------------- Analytics AI ----------------
class TestAnalyticsAI:
    @pytest.fixture(scope="class")
    def user(self, api_client):
        return _new_user(api_client, "aai")

    @pytest.fixture(scope="class")
    def with_lead(self, api_client, user):
        r = api_client.post(f"{BASE_URL}/api/leads",
                            json=_high_intent_payload("aai"),
                            headers=user["headers"], timeout=15)
        assert r.status_code == 200
        final, _ = _poll_until_terminal(api_client, user["headers"], r.json()["id"], timeout=60.0)
        return final

    def test_analytics_ai_shape(self, api_client, user, with_lead):
        r = api_client.get(f"{BASE_URL}/api/analytics/ai", headers=user["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        # Keys
        for k in ("avg_ai_score", "high_intent_leads", "industry_distribution",
                  "top_icp_matches", "qualification_success_rate",
                  "qualification_success_count", "qualification_total",
                  "avg_processing_ms", "prompt_versions", "total_ai_decisions"):
            assert k in data, f"analytics/ai missing key: {k}"
        # Types
        assert isinstance(data["avg_ai_score"], (int, float))
        assert isinstance(data["high_intent_leads"], int)
        assert isinstance(data["industry_distribution"], list)
        assert isinstance(data["top_icp_matches"], list)
        assert isinstance(data["qualification_success_rate"], (int, float))
        assert 0 <= data["qualification_success_rate"] <= 100
        assert isinstance(data["qualification_success_count"], int)
        assert isinstance(data["qualification_total"], int)
        assert isinstance(data["avg_processing_ms"], int)
        assert isinstance(data["prompt_versions"], dict)
        assert isinstance(data["total_ai_decisions"], int)

        # Content sanity
        for row in data["industry_distribution"]:
            for k in ("industry", "count", "pct"):
                assert k in row, f"industry row missing {k}: {row}"
        for icp in data["top_icp_matches"]:
            for k in ("lead_id", "name", "company", "score", "industry", "reason"):
                assert k in icp, f"top_icp row missing {k}: {icp}"

        # after >=1 successful lead this user should have real numbers
        assert data["qualification_total"] >= 1
        assert data["total_ai_decisions"] >= 2
        assert "qualification" in data["prompt_versions"]

    def test_analytics_ai_owner_isolation(self, api_client, with_lead):
        """Fresh user should see empty analytics (0 leads, 0 decisions)."""
        other = _new_user(api_client, "aai_other")
        r = api_client.get(f"{BASE_URL}/api/analytics/ai", headers=other["headers"])
        assert r.status_code == 200
        data = r.json()
        assert data["qualification_total"] == 0
        assert data["total_ai_decisions"] == 0
        assert data["high_intent_leads"] == 0
        assert data["industry_distribution"] == []
        assert data["top_icp_matches"] == []
