"""Regenerate openapi.snapshot.json from the live FastAPI app.

Run this after intentionally changing any route or request/response model:

    uv run python scripts/export_openapi.py

tests/test_openapi_snapshot.py fails whenever the app's OpenAPI schema
drifts from the checked-in snapshot, so every API contract change shows up
as a reviewable diff instead of a silent frontend breakage.
"""

import json
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

# Mirror tests/conftest.py: build the settings singleton from deterministic
# values so the snapshot never depends on a developer's apps/api/.env.
os.environ.setdefault("CD_TESTING", "1")
os.environ.setdefault("CD_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CD_GOOGLE_PROVIDER", "mock")
os.environ.setdefault("CD_GOOGLE_CLIENT_ID", "client-id")
os.environ.setdefault("CD_GOOGLE_CLIENT_SECRET", "client-secret")
os.environ.setdefault(
    "CD_GOOGLE_REDIRECT_URI", "http://testserver/api/auth/google/callback"
)

from classroom_downloader.main import app  # noqa: E402

SNAPSHOT_PATH = API_ROOT / "openapi.snapshot.json"


def main() -> None:
    SNAPSHOT_PATH.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
