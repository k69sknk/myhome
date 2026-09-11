"""Metiers ajoutables par l'utilisateur.

La liste integree reste versionnee avec le catalogue ; cette table recoit ce
qu'elle ignore — un vitrier, un cuisiniste — pour que « Autre » cesse d'etre
une impasse. Le seed des metiers integres se fait au demarrage
(`services/catalog.ensure_trades`), pas ici : une entree ajoutee plus tard a
`trades.yaml` doit pouvoir rejoindre une base deja installee.

Revision ID: 0013_metiers
Revises: 0012_prestataires
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0013_metiers"
down_revision: str | None = "0012_prestataires"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "trade" in inspect(bind).get_table_names():
        # Deja creee par le schema.sql de la migration 0001 : installs neuves.
        return

    op.create_table(
        "trade",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("is_builtin", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="500"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("trade")
