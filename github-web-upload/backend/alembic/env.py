"""Alembic environment configuration for Travel Planner."""

import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402

# Import all models so Alembic can detect them for autogenerate
import app.models.flight  # noqa: E402, F401
import app.models.itinerary  # noqa: E402, F401
import app.models.place  # noqa: E402, F401
import app.models.flight_compare  # noqa: E402, F401
import app.models.user  # noqa: E402, F401
import app.models.collaboration  # noqa: E402, F401
import app.models.custom_tags  # noqa: E402, F401

# Alembic Config object
config = context.config

# Set the database URL from our app config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Set up Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
