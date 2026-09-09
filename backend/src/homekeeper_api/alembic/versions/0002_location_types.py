"""Types de lieux personnalisables.

Revision ID: 0002_location_types
Revises: 0001_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from homekeeper_api.clock import utc_now_iso

revision: str = "0002_location_types"
down_revision: str | None = "0001_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BUILTIN_TYPES = [
    ("room", "Piece", 10),
    ("floor", "Etage", 20),
    ("zone", "Zone", 30),
    ("building", "Batiment", 40),
    ("outdoor", "Exterieur", 50),
    ("technical", "Technique", 60),
]


def upgrade() -> None:
    bind = op.get_bind()
    if "location_type" in inspect(bind).get_table_names():
        # Deja cree par le schema.sql de la migration 0001 : installs neuves.
        return

    now = utc_now_iso()

    op.create_table(
        "location_type",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("is_builtin", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )

    location_type = sa.table(
        "location_type",
        sa.column("slug", sa.Text),
        sa.column("name", sa.Text),
        sa.column("is_builtin", sa.Integer),
        sa.column("sort_order", sa.Integer),
        sa.column("created_at", sa.Text),
        sa.column("updated_at", sa.Text),
    )
    op.bulk_insert(
        location_type,
        [
            {
                "slug": slug,
                "name": name,
                "is_builtin": 1,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            for slug, name, sort_order in _BUILTIN_TYPES
        ],
    )

    op.add_column("location", sa.Column("location_type_id", sa.Integer))
    op.execute(
        "UPDATE location SET location_type_id = "
        "(SELECT id FROM location_type WHERE slug = location.location_type)"
    )

    with op.batch_alter_table("location") as batch_op:
        batch_op.alter_column("location_type_id", existing_type=sa.Integer, nullable=False)
        batch_op.create_foreign_key(
            "fk_location_location_type",
            "location_type",
            ["location_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("location_type")

    op.create_index("ix_location_location_type", "location", ["location_type_id"])


def downgrade() -> None:
    op.add_column("location", sa.Column("location_type", sa.Text))
    op.execute(
        "UPDATE location SET location_type = "
        "(SELECT slug FROM location_type WHERE id = location.location_type_id)"
    )
    op.drop_index("ix_location_location_type", table_name="location")
    with op.batch_alter_table("location") as batch_op:
        batch_op.drop_constraint("fk_location_location_type", type_="foreignkey")
        batch_op.drop_column("location_type_id")
        batch_op.alter_column(
            "location_type",
            existing_type=sa.Text,
            nullable=False,
            server_default="room",
        )
    op.drop_table("location_type")
