"""Initialize the database and start FastAPI in WeChat CloudRun."""

import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, get_engine
import app.models  # noqa: F401 - register every model with Base.metadata


def wait_for_database(attempts: int = 15) -> None:
    engine = get_engine()
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:
            if attempt == attempts:
                raise RuntimeError("Database did not become ready") from exc
            time.sleep(min(attempt, 5))


def prepare_schema() -> None:
    engine = get_engine()
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    existing = set(inspect(engine).get_table_names())
    app_tables = set(Base.metadata.tables)

    if "alembic_version" not in existing and not (existing & app_tables):
        # Fresh CloudRun template databases may contain unrelated demo tables.
        if engine.dialect.name == "mysql":
            for table in Base.metadata.tables.values():
                table.dialect_options["mysql"]["charset"] = "utf8mb4"
                table.dialect_options["mysql"]["collate"] = "utf8mb4_unicode_ci"
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    if settings.APP_ENV == "production" and settings.DATABASE_URL.startswith("sqlite"):
        raise RuntimeError(
            "CloudRun production requires MYSQL_ADDRESS, MYSQL_USERNAME and MYSQL_PASSWORD"
        )
    wait_for_database()
    prepare_schema()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "80")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
