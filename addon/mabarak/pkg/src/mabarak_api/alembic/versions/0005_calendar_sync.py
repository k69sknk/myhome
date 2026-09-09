"""Synchronisation des entretiens vers un calendrier Home Assistant existant.

Revision ID: 0005_calendar_sync
Revises: 0004_relative_due_soon
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0005_calendar_sync"
down_revision: str | None = "0004_relative_due_soon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in inspect(bind).get_columns("home")}
    if "ha_calendar_entity_id" in existing:
        # Deja cree par le schema.sql de la migration 0001 : installs neuves.
        return

    op.add_column("home", sa.Column("ha_calendar_entity_id", sa.Text))
    op.add_column(
        "home",
        sa.Column("ha_calendar_sync_enabled", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    with op.batch_alter_table("home") as batch_op:
        batch_op.drop_column("ha_calendar_sync_enabled")
        batch_op.drop_column("ha_calendar_entity_id")
