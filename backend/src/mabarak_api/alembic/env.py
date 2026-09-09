"""Environnement Alembic.

La cible est `Base.metadata` (modeles SQLAlchemy). La premiere revision execute
le schema SQL packagé (`0001_schema`).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mabarak_api import models as _models  # noqa: F401
from mabarak_api.config import get_settings
from mabarak_api.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# L'URL peut venir d'alembic.ini (usage developpeur) ou des reglages de
# l'application (usage conteneur, via `mabarak-migrate`).
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Indispensable en SQLite : les ALTER TABLE y sont tres limites, Alembic
        # doit recreer la table et recopier les donnees.
        render_as_batch=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
