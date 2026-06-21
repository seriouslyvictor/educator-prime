import json
import os
from datetime import UTC, datetime, timedelta

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "google"
os.environ["CD_GOOGLE_CLIENT_ID"] = "client-id"
os.environ["CD_GOOGLE_CLIENT_SECRET"] = "client-secret"
os.environ["CD_GOOGLE_REDIRECT_URI"] = "http://testserver/api/auth/google/callback"

from fastapi.testclient import TestClient
from sqlmodel import Session

from classroom_downloader.database import engine, init_db
from classroom_downloader.main import app, settings
from classroom_downloader.models import OAuthState


def test_callback_relaxes_scope_mismatch_before_fetch_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(settings, "session_secret_key", "test-session-secret")

    scopes = [
        "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
        "https://www.googleapis.com/auth/classroom.courses.readonly",
    ]
    init_db()
    with Session(engine) as db:
        db.merge(OAuthState(
            id="state-123",
            scopes_json=json.dumps(scopes),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        ))
        db.commit()

    class FakeCredentials:
        id_token = None

        def to_json(self) -> str:
            return "{}"

    class FakeFlow:
        credentials = FakeCredentials()
        redirect_uri = None

        @classmethod
        def from_client_config(cls, *_args, **_kwargs):
            return cls()

        def fetch_token(self, **_kwargs) -> None:
            assert os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] == "1"

    import google_auth_oauthlib.flow

    monkeypatch.setattr(google_auth_oauthlib.flow, "Flow", FakeFlow)

    with TestClient(app) as client:
        response = client.get(
            "/api/auth/google/callback?state=state-123&code=code-123",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == f"{settings.frontend_origin}/?google=connected"
    with Session(engine) as db:
        assert db.get(OAuthState, "state-123") is None


def test_callback_redirects_access_denied_to_google_auth_denied(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")

    with TestClient(app) as client:
        response = client.get(
            "/api/auth/google/callback?error=access_denied&state=state-123",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == (
        f"{settings.frontend_origin}/?google=error&reason=google_auth_denied"
    )


def test_callback_redirects_admin_policy_to_policy_blocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")

    with TestClient(app) as client:
        response = client.get(
            "/api/auth/google/callback?error=admin_policy_enforced&state=state-123",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == (
        f"{settings.frontend_origin}/?google=error&reason=google_policy_blocked"
    )


def test_callback_expired_state_still_returns_400(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(settings, "session_secret_key", "test-session-secret")

    init_db()
    with Session(engine) as db:
        db.merge(OAuthState(
            id="expired-state",
            scopes_json=json.dumps(["openid"]),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ))
        db.commit()

    with TestClient(app) as client:
        response = client.get(
            "/api/auth/google/callback?state=expired-state&code=code-123",
            follow_redirects=False,
        )

    assert response.status_code == 400
