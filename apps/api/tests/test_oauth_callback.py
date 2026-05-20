import json
import os
from pathlib import Path

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "google"
os.environ["CD_GOOGLE_CLIENT_ID"] = "client-id"
os.environ["CD_GOOGLE_CLIENT_SECRET"] = "client-secret"
os.environ["CD_GOOGLE_REDIRECT_URI"] = "http://testserver/api/auth/google/callback"

from fastapi.testclient import TestClient

from classroom_downloader.main import app, settings


def test_callback_relaxes_scope_mismatch_before_fetch_token(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "state.json"
    token_path = tmp_path / "token.json"
    state_path.write_text(
        json.dumps(
            {
                "state": "state-123",
                "scopes": [
                    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
                    "https://www.googleapis.com/auth/classroom.courses.readonly",
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "google_oauth_state_path", str(state_path))
    monkeypatch.setattr(settings, "google_token_path", str(token_path))

    class FakeCredentials:
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
    assert token_path.exists()
    assert not state_path.exists()
