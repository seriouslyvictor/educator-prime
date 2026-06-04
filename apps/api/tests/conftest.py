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

os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
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
