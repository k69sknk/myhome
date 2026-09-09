"""Connexion SQLite et session SQLAlchemy."""

from collections.abc import Iterator
from typing import Any

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    """Base declarative commune. `Base.metadata` est la cible d'Alembic."""


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
    finally:
        cursor.close()


def create_db_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True)


def session_factory_for(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_app_settings(request: Request) -> Settings:
    """Reglages de l'application en cours, poses sur app.state par create_app."""
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    """Session par requete, liee aux reglages de l'application FastAPI."""
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
