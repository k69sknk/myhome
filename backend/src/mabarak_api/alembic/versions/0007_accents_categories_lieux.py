"""Accents manquants dans les noms de categories et types de lieux integres.

Revision ID: 0007_accents_categories_lieux
Revises: 0006_membres_et_pieces
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_accents_categories_lieux"
down_revision: str | None = "0006_membres_et_pieces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (slug, ancien nom sans accent, nouveau nom) — uniquement les entrees inchangees
# depuis leur creation : si l'utilisateur a renomme une categorie ou un type de
# lieu integre, son choix n'est pas ecrase.
_CATEGORY_RENAMES = [
    ("electricity", "Electricite", "Électricité"),
    ("outdoor", "Exterieur", "Extérieur"),
    ("appliances", "Electromenager", "Électroménager"),
    ("structure", "Batiment", "Bâtiment"),
    ("heat_pump", "Pompe a chaleur", "Pompe à chaleur"),
    ("boiler", "Chaudiere", "Chaudière"),
    ("stove", "Poele", "Poêle"),
    ("electrical_panel", "Tableau electrique", "Tableau électrique"),
    ("generator", "Groupe electrogene", "Groupe électrogène"),
    ("fridge", "Refrigerateur", "Réfrigérateur"),
    ("gutters", "Gouttieres", "Gouttières"),
    ("facade", "Facade", "Façade"),
    ("windows", "Fenetres", "Fenêtres"),
    ("fence", "Cloture", "Clôture"),
]

_LOCATION_TYPE_RENAMES = [
    ("room", "Piece", "Pièce"),
    ("floor", "Etage", "Étage"),
    ("building", "Batiment", "Bâtiment"),
    ("outdoor", "Exterieur", "Extérieur"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for slug, old_name, new_name in _CATEGORY_RENAMES:
        bind.execute(
            sa.text("UPDATE category SET name = :new WHERE slug = :slug AND name = :old"),
            {"new": new_name, "slug": slug, "old": old_name},
        )
    for slug, old_name, new_name in _LOCATION_TYPE_RENAMES:
        bind.execute(
            sa.text("UPDATE location_type SET name = :new WHERE slug = :slug AND name = :old"),
            {"new": new_name, "slug": slug, "old": old_name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for slug, old_name, new_name in _CATEGORY_RENAMES:
        bind.execute(
            sa.text("UPDATE category SET name = :old WHERE slug = :slug AND name = :new"),
            {"new": new_name, "slug": slug, "old": old_name},
        )
    for slug, old_name, new_name in _LOCATION_TYPE_RENAMES:
        bind.execute(
            sa.text("UPDATE location_type SET name = :old WHERE slug = :slug AND name = :new"),
            {"new": new_name, "slug": slug, "old": old_name},
        )
