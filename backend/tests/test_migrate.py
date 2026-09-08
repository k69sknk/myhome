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
