import json

from ..google_scopes import has_capability, missing_scopes
from ..models import UserSession
from ..settings import get_settings
from .errors import api_error


def require_google_capability(
    current_session: UserSession,
    capability: str,
) -> None:
    if get_settings().google_provider == "mock":
        return
    granted = set(json.loads(current_session.google_granted_scopes_json or "[]"))
    if not granted:
        granted = _credential_scopes(current_session)
    if has_capability(granted, capability):
        return
    raise api_error(
        403,
        "google_permission_required",
        "Google permission is required for this action.",
        capability=capability,
        missing_scopes=missing_scopes(granted, capability),
    )


def _credential_scopes(current_session: UserSession) -> set[str]:
    try:
        from google.oauth2.credentials import Credentials

        from ..google_provider import decrypt_credentials_json

        raw = decrypt_credentials_json(current_session.google_credentials_json)
        credentials = Credentials.from_authorized_user_info(json.loads(raw))
        return set(getattr(credentials, "granted_scopes", None) or []) or set(
            credentials.scopes or []
        )
    except Exception:
        return set()
