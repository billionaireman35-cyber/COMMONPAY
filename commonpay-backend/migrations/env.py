import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mirror.store import metadata

# Register every table on the shared metadata before Alembic inspects it.
import mirror.auth_store  # noqa: E402,F401
import mirror.payout_store  # noqa: E402,F401
import mirror.locks  # noqa: E402,F401

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = metadata


def database_url():
    raw = os.environ.get("DATABASE_URL", "").strip()

    if not raw:
        raise RuntimeError(
            "DATABASE_URL is required for Alembic. "
            "No default SQLite database will be selected."
        )

    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]

    url = make_url(raw)

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+pg8000")

    if url.drivername == "postgresql+pg8000":
        query = dict(url.query)
        query.pop("sslmode", None)
        query.pop("channel_binding", None)
        url = url.set(query=query)

    return url


def run_migrations_offline():
    url = database_url()

    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = database_url()

    connect_args = {}

    if url.drivername == "postgresql+pg8000":
        connect_args["ssl_context"] = True

    engine = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
