"""Fenetre de saison sur les entretiens (tonte, piscine).

Revision ID: 0010_saison_entretiens
Revises: 0009_rappels_echeances
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0010_saison_entretiens"
down_revision: str | None = "0009_rappels_echeances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("season_start_month", "season_end_month")


def upgrade() -> None:
    # ALTER TABLE ADD COLUMN est natif sous SQLite et ne recree pas la table : pas
    # de risque de cascade sur `document.maintenance_task_id` (voir 0004).
    #
    # Les trois CHECK que schema.sql porte sur ces colonnes (bornes 1-12, les deux
    # ensemble ou aucune, seulement sur une recurrence a intervalle) n'arrivent pas
    # ici : SQLite ne sait pas ajouter une contrainte a une table existante, et la
    # recreer couterait la cascade ci-dessus. Ils sont tenus cote application par
    # `TaskIn`/`TaskPatch` et `_validate_recurrence`, seul chemin d'ecriture, et par
    # `CatalogRecurrence` pour le catalogue.
    existing = {c["name"] for c in inspect(op.get_bind()).get_columns("maintenance_task")}
    for column in _COLUMNS:
        if column not in existing:
            op.add_column("maintenance_task", sa.Column(column, sa.Integer))


def downgrade() -> None:
    with op.batch_alter_table("maintenance_task") as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_column(column)
