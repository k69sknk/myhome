"""Rappels a l'approche de l'echeance : reglages de la maison et trace par tache.

Revision ID: 0009_rappels_echeances
Revises: 0008_provenance_catalogue
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0009_rappels_echeances"
down_revision: str | None = "0008_provenance_catalogue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HOME_COLUMNS = ("reminder_hour", "default_notify_service", "last_reminder_run_on")


def _missing(table: str, column: str) -> bool:
    return column not in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # ALTER TABLE ADD COLUMN est natif sous SQLite et ne recree pas la table : pas
    # de risque de cascade sur `document.maintenance_task_id` (voir 0004).
    if _missing("home", "reminder_hour"):
        # server_default : la colonne est NOT NULL et des lignes existent deja.
        # Elle arrive en revanche SANS le CHECK (0-23) que porte schema.sql, SQLite
        # ne sachant pas ajouter une contrainte a une table existante et la recreer
        # coutant la cascade ci-dessus. La borne est tenue par `HomePatch`, seul
        # chemin d'ecriture de ce reglage.
        op.add_column(
            "home", sa.Column("reminder_hour", sa.Integer, nullable=False, server_default="8")
        )
    if _missing("home", "default_notify_service"):
        op.add_column("home", sa.Column("default_notify_service", sa.Text))
    if _missing("home", "last_reminder_run_on"):
        op.add_column("home", sa.Column("last_reminder_run_on", sa.Text))
    if _missing("maintenance_task", "last_reminded_on"):
        op.add_column("maintenance_task", sa.Column("last_reminded_on", sa.Text))


def downgrade() -> None:
    with op.batch_alter_table("maintenance_task") as batch_op:
        batch_op.drop_column("last_reminded_on")
    with op.batch_alter_table("home") as batch_op:
        for column in reversed(_HOME_COLUMNS):
            batch_op.drop_column(column)
