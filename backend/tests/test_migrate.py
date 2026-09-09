"""La premiere migration traduit docs/schema.sql."""

from sqlalchemy import Engine, inspect, text

from homekeeper_api.db import create_db_engine
from homekeeper_api.migrate import upgrade_to_head


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
    assert version == "0003_task_prep_fields"
    assert homes == 0
