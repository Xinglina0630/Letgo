from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        connect_args = {}
        if "sqlite" in settings.DATABASE_URL:
            connect_args = {"check_same_thread": False}
        engine_options = {
            "echo": settings.DEBUG,
            "connect_args": connect_args,
            "pool_pre_ping": True,
        }
        if settings.DATABASE_URL.startswith("mysql"):
            # Cloud MySQL may auto-pause; recycle stale connections after wake-up.
            engine_options.update({"pool_recycle": 240, "pool_size": 5, "max_overflow": 5})
        _engine = create_engine(settings.DATABASE_URL, **engine_options)

        # Enable SQLite foreign key enforcement
        if "sqlite" in settings.DATABASE_URL:
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that provides a database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. For development only — production uses Alembic."""
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=get_engine())
