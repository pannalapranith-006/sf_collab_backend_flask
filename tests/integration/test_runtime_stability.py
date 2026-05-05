"""Integration tests for runtime stability and auth behavior."""

import pytest
from flask_jwt_extended import create_access_token


@pytest.mark.integration
def test_health_endpoint_returns_healthy_payload(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "healthy", "database": "connected"}


@pytest.mark.integration
def test_health_reflects_allowed_origin(client):
    origin = "http://localhost:5173"
    response = client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == origin
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"


@pytest.mark.integration
def test_health_does_not_reflect_disallowed_origin(client):
    response = client.get("/health", headers={"Origin": "http://evil.example"})

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") is None


@pytest.mark.integration
def test_protected_users_endpoint_requires_jwt(client):
    response = client.get("/api/users")

    assert response.status_code == 401
    payload = response.get_json()
    assert payload is not None
    assert "msg" in payload


@pytest.mark.integration
def test_protected_users_endpoint_accepts_bearer_jwt(client, app):
    with app.app_context():
        token = create_access_token(identity="1")

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get("success") is True
    assert "data" in data
    assert "users" in data["data"]
