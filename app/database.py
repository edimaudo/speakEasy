from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_database(database_url: str | None = None):
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        if os.getenv("VERCEL"):
            raise RuntimeError(
                "DATABASE_URL must point to persistent PostgreSQL on Vercel. "
                "SQLite is suitable for local development but Vercel function storage is ephemeral."
            )
        data_dir = Path(os.getenv("SPEAKEASY_DATA_DIR", Path.cwd() / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{(data_dir / 'speakeasy.sqlite3').as_posix()}"

    url = _normalise_database_url(url)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite:"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite:"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def get_session_factory(request=None):
    if request is not None and hasattr(request.app.state, "session_factory"):
        return request.app.state.session_factory
    raise RuntimeError("Database session factory is not attached to the application.")


def get_db(request) -> Generator[Session, None, None]:
    factory = get_session_factory(request)
    db = factory()
    try:
        yield db
    finally:
        db.close()
