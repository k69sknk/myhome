"""La premiere migration traduit docs/schema.sql."""

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from mabarak_api.db import create_db_engine
from mabarak_api.migrate import alembic_config, upgrade_to_head


def test_premiere_migration_cree_tables_vues_et_categories(settings) -> None:
    upgrade_to_head(settings)

    engine: Engine = create_db_engine(settings)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    views = set(inspector.get_view_names())

    expected = {
        "home",
        "location",
        "category",
        "asset",
        "warranty",
        "maintenance_task",
        "ha_link",
    }
    assert expected.issubset(tables)
    assert {"v_task_status", "v_asset_timeline"}.issubset(views)

    with engine.connect() as connection:
        builtin = connection.execute(
            text("SELECT COUNT(*) FROM category WHERE is_builtin = 1")
        ).scalar_one()
        vacuum = connection.execute(
            text("SELECT COUNT(*) FROM category WHERE slug = 'vacuum'")
        ).scalar_one()

    assert builtin >= 20
    assert vacuum == 1


def test_premiere_migration_se_rejoue_si_le_stamp_manque(settings) -> None:
    """executescript committe hors transaction : un crash peut laisser les tables
    sans ligne alembic_version. Le second demarrage doit quand meme aboutir."""
    upgrade_to_head(settings)
    engine: Engine = create_db_engine(settings)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
    upgrade_to_head(settings)

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        homes = connection.execute(text("SELECT COUNT(*) FROM home")).scalar_one()
    assert version == "0007_accents_categories_lieux"
    assert homes == 0


def test_migrations_ulterieures_ne_perdent_pas_les_donnees_existantes(settings) -> None:
    """Garde-fou general : une migration qui recree une table referencee par une
    FK ON DELETE CASCADE (ex. asset.home_id -> home) peut supprimer en cascade
    tout ce qui en depend si SQLite ne desactive pas les contraintes FK pendant
    la recreation -- ce qui n'arrive pas ici, car toutes les migrations d'une
    meme invocation s'executent dans une seule transaction (PRAGMA foreign_keys
    ne peut pas changer au milieu d'une transaction). Rejoue chaque migration
    depuis une base peuplee comme une vraie install existante, et verifie
    qu'aucune ne fait disparaitre de donnees."""
    config = alembic_config(settings)
    engine: Engine = create_db_engine(settings)

    # Etat de depart : avant que la toute premiere revision n'existe encore.
    command.upgrade(config, "0001_schema")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("INSERT INTO home (id, name) VALUES (1, 'Maison')"))
        connection.execute(
            text(
                "INSERT INTO asset (id, home_id, kind, name) "
                "VALUES (1, 1, 'equipment', 'Chaudiere')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO maintenance_task (id, asset_id, name, recurrence_type) "
                "VALUES (1, 1, 'Revision', 'none')"
            )
        )

    script = ScriptDirectory.from_config(config)
    revisions = [rev.revision for rev in script.walk_revisions(base="0001_schema", head="head")]
    revisions.reverse()  # walk_revisions descend du head vers la base.

    for revision in revisions:
        command.upgrade(config, revision)
        with engine.connect() as connection:
            homes = connection.execute(text("SELECT COUNT(*) FROM home")).scalar_one()
            assets = connection.execute(text("SELECT COUNT(*) FROM asset")).scalar_one()
            tasks = connection.execute(text("SELECT COUNT(*) FROM maintenance_task")).scalar_one()
        assert (homes, assets, tasks) == (1, 1, 1), f"donnees perdues apres la migration {revision}"
