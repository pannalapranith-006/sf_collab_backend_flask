"""Integration tests for core auth API flows."""

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from app.models.user import User


@pytest.mark.integration
def test_me_requires_auth(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.integration
def test_logout_requires_auth(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 401


@pytest.mark.integration
def test_refresh_requires_refresh_token(client):
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401


@pytest.mark.integration
def test_me_with_access_token_returns_user(client, app, db):
    user = User(
        email="me-flow@example.com",
        first_name="Me",
        last_name="Flow",
        role="member",
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    with app.app_context():
        access_token = create_access_token(identity=str(user.id))

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload.get("success") is True
    assert "data" in payload
    assert "user" in payload["data"]
    assert payload["data"]["user"]["email"] == "me-flow@example.com"


@pytest.mark.integration
def test_logout_with_access_token_succeeds(client, app):
    with app.app_context():
        access_token = create_access_token(identity="1")

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload.get("message") == "Logged out successfully"


@pytest.mark.integration
def test_refresh_with_refresh_token_succeeds(client, app, db):
    user = User(
        email="refresh-flow@example.com",
        first_name="Refresh",
        last_name="Flow",
        role="member",
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    with app.app_context():
        refresh_token = create_refresh_token(identity=str(user.id))

    response = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload.get("message") == "Token refreshed"
    set_cookie_headers = response.headers.getlist("Set-Cookie")
    assert any("access_token_cookie=" in header for header in set_cookie_headers)
