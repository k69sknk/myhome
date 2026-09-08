"""Connexion SQLite et session SQLAlchemy.

Aucun modele n'est encore declare : le modele de donnees est fige dans
docs/DATA_MODEL.md et docs/schema.sql, et sera traduit en tables SQLAlchemy dans
`homekeeper_api.models` une fois l'architecture validee.
"""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    """Base declarative commune. `Base.metadata` est la cible d'Alembic."""


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection: Any, _connection_record: Any) -> None:
    """Applique les PRAGMA indispensables a chaque nouvelle connexion.

    `foreign_keys` n'est PAS actif par defaut dans SQLite. Sans ce PRAGMA, toutes
    les regles ON DELETE du schema sont ignorees silencieusement, ce qui laisserait
    passer exactement les pertes de donnees que le modele cherche a empecher.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        # Laisse a une ecriture concurrente le temps de se terminer au lieu de
        # renvoyer immediatement « database is locked ».
        cursor.execute("PRAGMA busy_timeout = 5000")
    finally:
        cursor.close()


def create_db_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_session() -> Iterator[Session]:
    """Dependance FastAPI fournissant une session par requete."""
    with get_session_factory()() as session:
        yield session
