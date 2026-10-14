"""Alembic environment configuration.
Reads DATABASE_URL from .env so secrets are never hardcoded here.
"""
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Load .env ──────────────────────────────────────────────────────────────────
def _load_dotenv():
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_dotenv()

# ── Alembic config ─────────────────────────────────────────────────────────────
config = context.config

# If DATABASE_URL env var is set, override alembic.ini value
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    # Alembic needs psycopg2 (sync), not asyncpg
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so Alembic can autogenerate migrations ───────────────────
from backend.models.user import User, Device, AuditLog, Alert, DeadLetter       # noqa: F401
from backend.models.telemetry import TelemetryReading                            # noqa: F401
from backend.models.routing import RoutingDecision                               # noqa: F401
from backend.core.database import Base

target_metadata = Base.metadata


# ── Migration functions ────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
