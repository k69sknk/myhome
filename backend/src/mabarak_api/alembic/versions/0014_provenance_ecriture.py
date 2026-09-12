"""Provenance des ecritures : l'interface, ou un agent externe.

MaBarak devient pilotable depuis Home Assistant (adr/0013) : un agent peut
desormais creer un equipement, planifier un entretien, ou le marquer fait. Rien
dans les tables ne permettait de distinguer ces ecritures de celles de
l'utilisateur. Six mois plus tard, devant une ligne d'historique fausse, c'est
pourtant la premiere question qu'on se pose.

La colonne est volontairement absente de `document` et de `cost` : l'agent ne
les cree jamais seuls, toujours dans le sillage d'une intervention qui, elle,
porte la provenance.

Revision ID: 0014_provenance_ecriture
Revises: 0013_metiers
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0014_provenance_ecriture"
down_revision: str | None = "0013_metiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("asset", "maintenance_task", "intervention")


def _missing(table: str, column: str) -> bool:
    return column not in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # NULL, et non 'ui' par defaut : les lignes anterieures a cette migration
    # sont forcement de l'utilisateur, mais le dire explicitement serait une
    # affirmation que la base ne peut pas soutenir. NULL se lit « avant que la
    # question se pose », ce qui est exactement le cas.
    for table in _TABLES:
        if _missing(table, "created_via"):
            op.add_column(table, sa.Column("created_via", sa.Text))


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("created_via")
