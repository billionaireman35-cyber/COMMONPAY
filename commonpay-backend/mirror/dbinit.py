"""Explicit PostgreSQL schema initialisation through Alembic.

This command deliberately refuses to run without --apply.
It never selects the local SQLite database implicitly.
"""

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "--apply":
        raise SystemExit(
            "Database migrations require explicit approval.\n"
            "Usage: python -m mirror.dbinit --apply"
        )

    raw = os.environ.get("DATABASE_URL", "").strip()

    if not raw:
        raise SystemExit("DATABASE_URL is required.")

    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]

    url = make_url(raw)

    if not url.drivername.startswith("postgresql"):
        raise SystemExit(
            "This command only applies PostgreSQL migrations. "
            "SQLite databases are not selected automatically."
        )

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))

    command.upgrade(config, "head")

    print("CommonPay PostgreSQL migrations applied successfully.")


if __name__ == "__main__":
    main()
