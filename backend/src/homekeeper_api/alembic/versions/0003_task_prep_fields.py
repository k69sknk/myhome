"""Champs de preparation sur les entretiens (piece a remplacer, a prevoir).

Revision ID: 0003_task_prep_fields
Revises: 0002_location_types
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003_task_prep_fields"
down_revision: str | None = "0002_location_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_COLUMNS = (
    "needs_part_replacement",
    "replacement_part_name",
    "replacement_part_source",
    "preparation_notes",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in inspect(bind).get_columns("maintenance_task")}
    if _NEW_COLUMNS[0] in existing:
        # Deja cree par le schema.sql de la migration 0001 : installs neuves.
        return

    op.add_column(
        "maintenance_task",
        sa.Column("needs_part_replacement", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("maintenance_task", sa.Column("replacement_part_name", sa.Text))
    op.add_column("maintenance_task", sa.Column("replacement_part_source", sa.Text))
    op.add_column("maintenance_task", sa.Column("preparation_notes", sa.Text))


def downgrade() -> None:
    with op.batch_alter_table("maintenance_task") as batch_op:
        batch_op.drop_column("preparation_notes")
        batch_op.drop_column("replacement_part_source")
        batch_op.drop_column("replacement_part_name")
        batch_op.drop_column("needs_part_replacement")
