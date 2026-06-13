"""Encrypt existing plaintext Google OAuth credentials in UserSession rows.

Requires CD_SESSION_SECRET_KEY set to the same value used by the app. Run once
with:

    uv run python scripts/encrypt_existing_credentials.py

The script is idempotent: rows that no longer start with "{" are skipped.
"""

import os
import sys
from pathlib import Path

from sqlmodel import Session, select

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from classroom_downloader.database import engine, init_db  # noqa: E402
from classroom_downloader.google_provider import encrypt_credentials_json  # noqa: E402
from classroom_downloader.models import UserSession  # noqa: E402
from classroom_downloader.settings import get_settings  # noqa: E402


def encrypt_existing_credentials(db: Session) -> int:
    if not get_settings().session_secret_key:
        raise RuntimeError("CD_SESSION_SECRET_KEY must be set before migrating credentials.")

    migrated = 0
    rows = db.exec(select(UserSession)).all()
    for row in rows:
        if not row.google_credentials_json.startswith("{"):
            continue
        row.google_credentials_json = encrypt_credentials_json(row.google_credentials_json)
        db.add(row)
        migrated += 1
    if migrated:
        db.commit()
    return migrated


def main() -> None:
    if not os.environ.get("CD_SESSION_SECRET_KEY"):
        raise SystemExit("CD_SESSION_SECRET_KEY must be set before migrating credentials.")
    init_db()
    with Session(engine) as db:
        migrated = encrypt_existing_credentials(db)
    print(f"Encrypted {migrated} plaintext credential row(s).")


if __name__ == "__main__":
    main()
