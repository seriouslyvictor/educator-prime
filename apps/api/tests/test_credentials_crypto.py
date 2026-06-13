from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from classroom_downloader.database import engine, init_db
from classroom_downloader.main import settings
from classroom_downloader.models import UserSession


CREDS_JSON = (
    '{"token":"access-token","refresh_token":"refresh-secret",'
    '"client_secret":"client-secret","scopes":["scope-a"]}'
)


def test_credentials_json_round_trips_encrypted(monkeypatch) -> None:
    from classroom_downloader.google_provider import (
        decrypt_credentials_json,
        encrypt_credentials_json,
    )

    monkeypatch.setattr(settings, "session_secret_key", "test-session-secret")

    encrypted = encrypt_credentials_json(CREDS_JSON)

    assert encrypted != CREDS_JSON
    assert "refresh-secret" not in encrypted
    assert decrypt_credentials_json(encrypted) == CREDS_JSON


def test_legacy_plaintext_credentials_pass_through(monkeypatch) -> None:
    from classroom_downloader.google_provider import decrypt_credentials_json

    monkeypatch.setattr(settings, "session_secret_key", "test-session-secret")

    assert decrypt_credentials_json('{"token":"abc"}') == '{"token":"abc"}'


def test_encrypt_credentials_json_no_key_returns_input(monkeypatch) -> None:
    from classroom_downloader.google_provider import encrypt_credentials_json

    monkeypatch.setattr(settings, "session_secret_key", None)

    assert encrypt_credentials_json(CREDS_JSON) == CREDS_JSON


def test_encrypt_existing_credentials_migrates_plaintext_rows(monkeypatch) -> None:
    from classroom_downloader.google_provider import decrypt_credentials_json
    from scripts.encrypt_existing_credentials import encrypt_existing_credentials

    monkeypatch.setattr(settings, "session_secret_key", "test-session-secret")
    init_db()
    session_id = "crypto-migration-session"
    now = datetime.now(UTC)

    with Session(engine) as db:
        db.merge(
            UserSession(
                id=session_id,
                user_email="teacher@example.edu",
                google_credentials_json=CREDS_JSON,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

    with Session(engine) as db:
        assert encrypt_existing_credentials(db) >= 1
        row = db.get(UserSession, session_id)
        assert row is not None
        assert not row.google_credentials_json.startswith("{")
        assert decrypt_credentials_json(row.google_credentials_json) == CREDS_JSON

    with Session(engine) as db:
        assert encrypt_existing_credentials(db) == 0
