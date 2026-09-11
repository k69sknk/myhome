"""Intervention rattachee au membre qui l'a realisee.

Revision ID: 0011_intervention_membre
Revises: 0010_saison_entretiens
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0011_intervention_membre"
down_revision: str | None = "0010_saison_entretiens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _missing(table: str, column: str) -> bool:
    return column not in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # ALTER TABLE ADD COLUMN est natif sous SQLite et ne recree pas la table : pas
    # de risque de cascade sur `document.maintenance_task_id` (voir 0004). La
    # colonne arrive donc SANS sa clause REFERENCES, que SQLite ne sait pas
    # ajouter apres coup ; la contrainte vit dans schema.sql pour les installations
    # neuves, et le seul chemin d'ecriture (`CompleteIn`) verifie le membre.
    if _missing("intervention", "performed_by_member_id"):
        op.add_column("intervention", sa.Column("performed_by_member_id", sa.Integer))


def downgrade() -> None:
    with op.batch_alter_table("intervention") as batch_op:
        batch_op.drop_column("performed_by_member_id")
