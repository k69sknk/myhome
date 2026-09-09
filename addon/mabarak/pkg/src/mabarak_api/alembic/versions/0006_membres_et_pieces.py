"""Annuaire des membres (delegation d'entretien) et pieces multiples.

Revision ID: 0006_membres_et_pieces
Revises: 0005_calendar_sync
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0006_membres_et_pieces"
down_revision: str | None = "0005_calendar_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "member" not in existing_tables:
        op.create_table(
            "member",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("home_id", sa.Integer, sa.ForeignKey("home.id", ondelete="CASCADE")),
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("member_type", sa.Text, nullable=False, server_default="household"),
            sa.Column("contact", sa.Text),
            sa.Column("ha_person_entity_id", sa.Text),
            sa.Column("ha_notify_service", sa.Text),
            sa.Column("created_at", sa.Text, nullable=False),
            sa.Column("updated_at", sa.Text, nullable=False),
        )
        op.create_index("ix_member_home", "member", ["home_id"])

    if "replacement_part" not in existing_tables:
        op.create_table(
            "replacement_part",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "task_id",
                sa.Integer,
                sa.ForeignKey("maintenance_task.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("source", sa.Text),
            sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        )
        op.create_index("ix_replacement_part_task", "replacement_part", ["task_id"])

        # Reprise des pieces deja saisies via les anciennes colonnes uniques,
        # pour ne rien perdre lors du passage au modele a plusieurs pieces.
        connection = op.get_bind()
        rows = connection.execute(
            sa.text(
                "SELECT id, replacement_part_name, replacement_part_source "
                "FROM maintenance_task "
                "WHERE needs_part_replacement = 1 "
                "AND replacement_part_name IS NOT NULL AND replacement_part_name != ''"
            )
        ).fetchall()
        for task_id, name, source in rows:
            connection.execute(
                sa.text(
                    "INSERT INTO replacement_part (task_id, name, source, sort_order) "
                    "VALUES (:task_id, :name, :source, 0)"
                ),
                {"task_id": task_id, "name": name, "source": source},
            )

    task_columns = {c["name"] for c in inspector.get_columns("maintenance_task")}
    if "assignee_id" not in task_columns:
        op.add_column(
            "maintenance_task",
            sa.Column("assignee_id", sa.Integer, sa.ForeignKey("member.id", ondelete="SET NULL")),
        )
        op.create_index("ix_task_assignee", "maintenance_task", ["assignee_id"])

    home_columns = {c["name"] for c in inspector.get_columns("home")}
    if "task_notifications_enabled" not in home_columns:
        op.add_column(
            "home",
            sa.Column("task_notifications_enabled", sa.Integer, nullable=False, server_default="0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("home") as batch_op:
        batch_op.drop_column("task_notifications_enabled")
    with op.batch_alter_table("maintenance_task") as batch_op:
        batch_op.drop_index("ix_task_assignee")
        batch_op.drop_column("assignee_id")
    op.drop_table("replacement_part")
    op.drop_table("member")
