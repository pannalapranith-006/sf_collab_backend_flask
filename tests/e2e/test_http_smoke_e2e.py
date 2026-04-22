import os
import time
import uuid

import pytest
import requests


BASE_URL_CANDIDATES = [
    os.getenv("E2E_BASE_URL", "").strip(),
    "http://localhost:5000",
    "http://backend:5000",
]


def _wait_for_health(timeout_seconds=60):
    candidates = [url for url in BASE_URL_CANDIDATES if url]
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        for base_url in candidates:
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    return base_url
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = exc
        time.sleep(2)
    raise RuntimeError(f"Backend health check did not pass in time. Last error: {last_error}")


@pytest.mark.e2e
def test_health_and_cors_headers():
    base_url = _wait_for_health()

    origin = "http://localhost:5173"
    response = requests.get(f"{base_url}/health", headers={"Origin": origin}, timeout=10)

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "healthy"
    assert response.headers.get("Access-Control-Allow-Origin") == origin


@pytest.mark.e2e
def test_register_login_and_me_flow():
    base_url = _wait_for_health()

    unique = uuid.uuid4().hex[:10]
    email = f"e2e_{unique}@example.com"
    password = "E2E_password_123"

    register_payload = {
        "email": email,
        "password": password,
        "firstName": "E2E",
        "lastName": "User",
    }

    register_response = requests.post(
        f"{base_url}/api/auth/register",
        json=register_payload,
        timeout=20,
    )
    assert register_response.status_code in (200, 201)

    session = requests.Session()

    login_response = session.post(
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert login_response.status_code == 200

    me_response = session.get(f"{base_url}/api/auth/me", timeout=15)
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload.get("success") is True
    assert me_payload.get("data", {}).get("user", {}).get("email") == email
