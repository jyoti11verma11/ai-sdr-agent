"""Shared fixtures for AI SDR Agent backend tests."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if "REACT_APP_BACKEND_URL" in os.environ else None

# Fallback: read from frontend/.env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

DEMO_EMAIL = "demo@sdr.ai"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def demo_token(api_client):
    r = api_client.post(f"{BASE_URL}/api/auth/login",
                        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Demo login failed: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def demo_user_id(api_client, demo_token):
    r = api_client.get(f"{BASE_URL}/api/auth/me",
                       headers={"Authorization": f"Bearer {demo_token}"})
    return r.json()["id"]


@pytest.fixture(scope="session")
def auth_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def secondary_user(api_client):
    """A second user for owner-isolation tests."""
    email = f"TEST_iso_{uuid.uuid4().hex[:8]}@sdr.ai"
    password = "isopass1234"
    r = api_client.post(f"{BASE_URL}/api/auth/signup",
                        json={"email": email, "password": password,
                              "full_name": "Isolation Tester"})
    if r.status_code != 200:
        pytest.skip(f"Secondary signup failed: {r.status_code} {r.text}")
    data = r.json()
    return {
        "email": email,
        "password": password,
        "token": data["token"],
        "id": data["user"]["id"],
        "headers": {"Authorization": f"Bearer {data['token']}",
                    "Content-Type": "application/json"},
    }
