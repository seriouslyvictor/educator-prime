"""Credential encryption/decryption helpers and token store classes."""
from datetime import UTC, datetime
from pathlib import Path

from .cache import clear_google_provider_caches
from ..observability import get_logger, log_event, log_warning
from ..settings import get_settings


logger = get_logger(__name__)


def _credential_fernet():
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    secret = get_settings().session_secret_key
    if not secret:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_credentials_json(plaintext: str) -> str:
    fernet = _credential_fernet()
    if fernet is None:
        return plaintext
    return fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_credentials_json(stored: str) -> str:
    # Legacy plaintext rows can be removed after all deployments run the migration.
    if stored.startswith("{"):
        return stored
    fernet = _credential_fernet()
    if fernet is None:
        return stored
    return fernet.decrypt(stored.encode("ascii")).decode("utf-8")


class TokenStore:
    def __init__(self, token_path: str):
        self.token_path = Path(token_path)

    def exists(self) -> bool:
        exists = self.token_path.exists()
        log_event(logger, "google.token.exists", path=str(self.token_path), exists=exists)
        return exists

    def save(self, credentials_json: str) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials_json, encoding="utf-8")
        clear_google_provider_caches()
        log_event(
            logger,
            "google.token.save",
            path=str(self.token_path),
            byte_size=len(credentials_json.encode("utf-8")),
        )

    def delete(self) -> None:
        self.token_path.unlink(missing_ok=True)
        clear_google_provider_caches()
        log_event(logger, "google.token.delete", path=str(self.token_path))

    def load_credentials(self):
        if not self.token_path.exists():
            log_warning(logger, "google.token.missing", path=str(self.token_path))
            raise FileNotFoundError(self.token_path)
        from google.oauth2.credentials import Credentials

        log_event(logger, "google.token.load", path=str(self.token_path))
        return Credentials.from_authorized_user_file(str(self.token_path))

    def load_valid_credentials(self):
        credentials = self.load_credentials()
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request

            log_event(logger, "google.token.refresh", path=str(self.token_path))
            credentials.refresh(Request())
            self.save(credentials.to_json())
            return credentials

        from google.auth.exceptions import RefreshError

        log_warning(
            logger,
            "google.token.not_refreshable",
            path=str(self.token_path),
            expired=credentials.expired,
            has_refresh_token=bool(credentials.refresh_token),
        )
        raise RefreshError("Stored Google credentials cannot be refreshed.")


class DbTokenStore:
    """Loads and refreshes Google credentials stored in the UserSession DB row."""

    def __init__(self, session_id: str, db) -> None:
        self._session_id = session_id
        self._db = db

    def load_credentials(self):
        from ..models import UserSession

        row = self._db.get(UserSession, self._session_id)
        expires = row.expires_at if row else None
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if row is None or expires < datetime.now(UTC):
            log_warning(logger, "google.token.missing", session_id=self._session_id)
            raise FileNotFoundError("Session not found or expired")
        from google.oauth2.credentials import Credentials

        import json as _json
        log_event(logger, "google.token.load", session_id=self._session_id)
        raw = decrypt_credentials_json(row.google_credentials_json)
        return Credentials.from_authorized_user_info(_json.loads(raw))

    def load_valid_credentials(self):
        from ..models import UserSession

        credentials = self.load_credentials()
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request

            log_event(logger, "google.token.refresh", session_id=self._session_id)
            credentials.refresh(Request())
            row = self._db.get(UserSession, self._session_id)
            if row is not None:
                row.google_credentials_json = encrypt_credentials_json(credentials.to_json())
                row.last_seen_at = datetime.now(UTC)
                self._db.add(row)
                self._db.commit()
            return credentials
        from google.auth.exceptions import RefreshError

        log_warning(
            logger,
            "google.token.not_refreshable",
            session_id=self._session_id,
            expired=credentials.expired,
            has_refresh_token=bool(credentials.refresh_token),
        )
        raise RefreshError("Stored Google credentials cannot be refreshed.")
