"""Environnement Alembic.

La cible est `Base.metadata` (modeles SQLAlchemy). La premiere revision execute
le schema SQL packagé (`0001_schema`).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

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

    # SQLite ne sait pas modifier une colonne : la seule facon est de recreer la
    # table, ce qui passe par un DROP TABLE. Et un DROP TABLE sous
    # `foreign_keys = ON` efface d'abord, en cascade, tout ce qui reference la
    # table — les documents d'une intervention, par exemple. Ce n'est pas une
    # hypothese : la 0004 a perdu des donnees exactement comme ca, et le
    # commentaire de cette revision en garde la trace.
    #
    # La procedure documentee par SQLite est de couper l'integrite le temps du
    # remaniement, puis de la verifier avant de rendre la main. C'est ce que fait
    # ce listener, pose sur le seul moteur des migrations : l'application, elle,
    # garde ses contraintes actives (voir db.py).
    @event.listens_for(connectable, "connect")
    def _sans_contraintes_pendant_la_migration(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=OFF")

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

        # Hors transaction, une fois les migrations validees : si l'une d'elles a
        # laisse une ligne orpheline, mieux vaut le savoir ici que six mois plus
        # tard devant une fiche qui pointe dans le vide.
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:
            details = ", ".join(f"{ligne[0]}#{ligne[1]} -> {ligne[2]}" for ligne in violations[:5])
            raise RuntimeError(
                f"Migration interrompue : {len(violations)} reference(s) cassee(s) — {details}"
            )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
