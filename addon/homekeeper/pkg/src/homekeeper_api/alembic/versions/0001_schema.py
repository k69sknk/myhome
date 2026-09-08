"""Schema initial : tables, vues et categories integrees.

Revision ID: 0001_schema
Revises:
"""

from collections.abc import Sequence
from pathlib import Path
from sqlite3 import Connection as SqliteConnection

from alembic import op

revision: str = "0001_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = Path(__file__).resolve().parents[2] / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA.read_text(encoding="utf-8")
    dbapi = op.get_bind().connection.driver_connection
    if not isinstance(dbapi, SqliteConnection):
        raise TypeError("la migration initiale exige SQLite")
    dbapi.executescript(sql)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_task_status")
    op.execute("DROP VIEW IF EXISTS v_asset_timeline")
    for table in (
        "document",
        "cost",
        "intervention",
        "issue",
        "maintenance_task",
        "warranty",
        "ha_link",
        "asset",
        "manufacturer",
        "category",
        "location",
        "home",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
