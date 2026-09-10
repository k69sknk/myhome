"""Provenance du catalogue de demarrage sur les lieux, fiches et entretiens.

Revision ID: 0008_provenance_catalogue
Revises: 0007_accents_categories_lieux
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0008_provenance_catalogue"
down_revision: str | None = "0007_accents_categories_lieux"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("location", "asset", "maintenance_task")


def upgrade() -> None:
    # ALTER TABLE ADD COLUMN est natif sous SQLite et ne recree pas la table :
    # pas de risque de cascade sur `document.maintenance_task_id` (voir 0004).
    inspector = inspect(op.get_bind())
    for table in _TABLES:
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "catalog_key" not in columns:
            op.add_column(table, sa.Column("catalog_key", sa.Text))


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("catalog_key")
