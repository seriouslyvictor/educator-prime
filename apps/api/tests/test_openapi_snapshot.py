"""Guard the API contract: fail when the OpenAPI schema drifts from the
checked-in snapshot.

The frontend client in apps/web is written against this contract, but nothing
type-checks across the apps/api <-> apps/web seam. This test makes every
route/model change visible as a diff to openapi.snapshot.json. If the change
is intentional, regenerate the snapshot:

    uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from classroom_downloader.main import app

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "openapi.snapshot.json"


def test_openapi_schema_matches_snapshot() -> None:
    assert SNAPSHOT_PATH.exists(), (
        "openapi.snapshot.json is missing; generate it with "
        "`uv run python scripts/export_openapi.py`"
    )
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert app.openapi() == snapshot, (
        "The OpenAPI schema no longer matches openapi.snapshot.json. "
        "If this API change is intentional, regenerate the snapshot with "
        "`uv run python scripts/export_openapi.py` and commit the diff."
    )
