"""Shared pytest configuration for the API test suite.

Two isolation concerns are handled here:

1. **OAuth configuration ordering.** A few test modules set Google OAuth
   environment variables at import time, but the ``settings`` singleton is
   built the first time ``classroom_downloader.main`` is imported -- which, in
   a full-suite run, happens while collecting an *earlier* test module, before
   those env vars exist. ``conftest.py`` is imported before any test module, so
   setting the OAuth defaults here guarantees the singleton is configured
   regardless of collection order. (Run alone the affected test passed; only
   the full-suite ordering exposed the gap.)

2. **Process-global state leaking between tests.** Tier 2 caching introduced
   module-level provider/profile/Drive-metadata caches, and a couple of tests
   mutate the ``settings`` singleton directly (not via ``monkeypatch``). The
   autouse fixture below snapshots ``settings`` and clears the provider caches
   around every test so neither can leak across the suite.
"""

import os

# Set before any classroom_downloader import: tells settings.py to skip loading
# the developer's apps/api/.env so the suite is deterministic.
os.environ.setdefault("CD_TESTING", "1")
os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
# Pin the provider to the in-memory mock so a developer's real apps/api/.env
# (CD_GOOGLE_PROVIDER=google), now loaded into os.environ via settings.load_dotenv,
# never leaks the real Google provider into the suite. A real shell env var still
# wins. This makes a plain `uv run --extra dev pytest -q` green with no overrides.
os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")
# A dummy provider key so litellm-engine tests (which mock the actual completion
# call) pass the new provider-key readiness gate. Tests covering the missing-key
# path delete it via monkeypatch.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("CD_GOOGLE_CLIENT_ID", "client-id")
os.environ.setdefault("CD_GOOGLE_CLIENT_SECRET", "client-secret")
os.environ.setdefault(
    "CD_GOOGLE_REDIRECT_URI", "http://testserver/api/auth/google/callback"
)

import pytest

from classroom_downloader.google_provider import clear_google_provider_caches
from classroom_downloader.main import settings


@pytest.fixture(autouse=True)
def _reset_global_state():
    snapshot = dict(settings.__dict__)
    clear_google_provider_caches()
    try:
        yield
    finally:
        settings.__dict__.clear()
        settings.__dict__.update(snapshot)
        clear_google_provider_caches()
