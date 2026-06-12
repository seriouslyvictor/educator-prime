"""Auth router: /api/auth/*"""
from datetime import UTC, datetime, timedelta
import json
import os
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlmodel import Session, delete

from ..api.auth_errors import google_auth_http_exception
from ..api.common import _as_utc
from ..api.deps import get_current_session, is_admin_email
from ..api.errors import api_error
from ..api.session_cleanup import purge_cached_classroom_state_for_user, purge_google_session_if_needed
from ..database import get_session
from ..google_provider import DbTokenStore, build_oauth_authorization_url, make_google_provider
from ..models import OAuthState, UserSession
from ..observability import get_logger, log_error, log_event, log_warning
from ..schemas import AuthStart, AuthState
from ..settings import get_settings

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


def disconnected_auth_state() -> AuthState:
    return AuthState(
        signed_in=False,
        identity_scopes=False,
        classroom_scopes=False,
        drive_scopes=False,
        provider=settings.google_provider,
    )


@router.get("/api/auth/me", response_model=AuthState)
def auth_me(
    request: Request,
    db: Session = Depends(get_session),
) -> AuthState:
    log_event(logger, "auth.me.start", provider=settings.google_provider)
    if settings.google_provider == "mock":
        from ..google_provider import MockGoogleProvider
        profile = MockGoogleProvider().account_profile()
        log_event(logger, "auth.me.mock", name=profile.name, email=profile.email)
        return AuthState(
            signed_in=True,
            identity_scopes=True,
            classroom_scopes=True,
            drive_scopes=True,
            email=profile.email,
            name=profile.name,
            picture=profile.picture,
            provider="mock",
            is_admin=is_admin_email(profile.email),
        )
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return disconnected_auth_state()
    row = db.get(UserSession, session_id)
    if row is None or _as_utc(row.expires_at) < datetime.now(UTC):
        return disconnected_auth_state()
    scopes: set[str] = set()
    name = None
    email = None
    picture = None
    try:
        store = DbTokenStore(session_id, db)
        credentials = store.load_credentials()
        scopes = set(credentials.scopes or [])
        provider = make_google_provider(session_id, db)
        profile = provider.account_profile()
        name = profile.name
        email = profile.email
        picture = profile.picture
    except Exception as error:
        auth_failure = google_auth_http_exception(error)
        if auth_failure:
            log_warning(
                logger,
                "auth.me.profile_auth_failed",
                purge_token=auth_failure.purge_token,
            )
            purge_google_session_if_needed(auth_failure, row, db)
            if auth_failure.purge_token or not scopes:
                return disconnected_auth_state()
        else:
            log_error(logger, "auth.me.profile_failed")
            if not scopes:
                return disconnected_auth_state()
    log_event(
        logger,
        "auth.me.google",
        scope_count=len(scopes),
        scopes=sorted(scopes),
        name=name,
        email=email,
    )
    has_google_identity = {"openid", "email", "profile"}.issubset(scopes)
    has_classroom_identity = any("classroom.profile.emails" in scope for scope in scopes)
    return AuthState(
        signed_in=bool(scopes),
        identity_scopes=has_google_identity or has_classroom_identity,
        classroom_scopes=any(scope.startswith("classroom.") for scope in scopes)
        or any("classroom" in scope for scope in scopes),
        drive_scopes=any("drive.readonly" in scope for scope in scopes),
        email=email,
        name=name,
        picture=picture,
        provider=settings.google_provider,
        is_admin=is_admin_email(email),
    )


@router.post("/api/auth/google/logout")
def auth_logout(
    request: Request,
    db: Session = Depends(get_session),
) -> Response:
    log_event(logger, "auth.google.logout", provider=settings.google_provider)
    if settings.google_provider == "google":
        session_id = request.cookies.get(settings.session_cookie_name)
        if session_id:
            row = db.get(UserSession, session_id)
            if row is not None:
                purge_cached_classroom_state_for_user(row.user_email, db)
                db.delete(row)
                db.commit()
    response = JSONResponse(content=disconnected_auth_state().model_dump())
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return response


@router.post("/api/auth/google/start", response_model=AuthStart)
def auth_start(scopes: list[str], db: Session = Depends(get_session)) -> AuthStart:
    log_event(
        logger,
        "auth.google.start",
        provider=settings.google_provider,
        scope_count=len(scopes),
        scopes=scopes,
    )
    if settings.google_provider == "mock":
        return AuthStart(mock_connected=True, scopes=scopes)
    if not settings.google_client_id or not settings.google_client_secret:
        log_warning(logger, "auth.google.not_configured")
        raise api_error(
            503,
            "oauth_not_configured",
            "Google OAuth is not configured.",
        )
    state = token_urlsafe(24)
    now = datetime.now(UTC)
    db.add(OAuthState(
        id=state,
        scopes_json=json.dumps(scopes),
        expires_at=now + timedelta(minutes=10),
    ))
    db.exec(delete(OAuthState).where(OAuthState.expires_at < now))
    db.commit()
    return AuthStart(
        authorization_url=build_oauth_authorization_url(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            scopes=scopes,
            state=state,
        ),
        scopes=scopes,
    )


def _email_from_credentials(creds) -> str | None:
    import base64 as _base64
    import json as _json

    id_token = getattr(creds, "id_token", None)
    if isinstance(id_token, dict):
        return id_token.get("email")
    if isinstance(id_token, str):
        try:
            payload = id_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return _json.loads(_base64.urlsafe_b64decode(payload)).get("email")
        except Exception:
            return None
    return None


@router.get("/api/auth/google/callback")
def auth_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_session),
) -> RedirectResponse:
    log_event(logger, "auth.google.callback.start", state=state, has_code=bool(code))
    if not settings.google_client_id or not settings.google_client_secret:
        log_warning(logger, "auth.google.callback.not_configured")
        raise api_error(
            503,
            "oauth_not_configured",
            "Google OAuth is not configured.",
        )

    oauth_state = db.get(OAuthState, state)
    if oauth_state is None or _as_utc(oauth_state.expires_at) < datetime.now(UTC):
        log_warning(logger, "auth.google.callback.invalid_state", received_state=state)
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    scopes = json.loads(oauth_state.scopes_json)
    db.delete(oauth_state)
    db.commit()

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=scopes,
        state=state,
    )
    flow.redirect_uri = settings.google_redirect_uri
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow.fetch_token(authorization_response=str(request.url), code=code)
    creds = flow.credentials
    user_email = _email_from_credentials(creds) or ""

    session_id = token_urlsafe(32)
    now = datetime.now(UTC)
    max_age = timedelta(hours=settings.session_max_age_hours)
    db.add(UserSession(
        id=session_id,
        user_email=user_email,
        google_credentials_json=creds.to_json(),
        created_at=now,
        expires_at=now + max_age,
    ))
    db.commit()

    log_event(
        logger,
        "auth.google.callback.complete",
        user_email=user_email,
        scopes=scopes,
    )
    is_prod = settings.frontend_origin.startswith("https://")
    redirect = RedirectResponse(f"{settings.frontend_origin}/?google=connected")
    redirect.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=int(max_age.total_seconds()),
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/",
    )
    return redirect
