"""Les prestataires quittent l'annuaire des membres pour leur propre table.

Revision ID: 0012_prestataires
Revises: 0011_intervention_membre

Voir adr/0011. Cette migration ne fait pas que creer une table : les entreprises
saisies en 0.22 et 0.23 sont des lignes de `member`, deja referencees par des
entretiens et des interventions. Il faut les demenager ET reecrire ce qui les
designe, sans quoi l'utilisateur perdrait l'assignation de son entretien de
chaudiere au passage.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0012_prestataires"
down_revision: str | None = "0011_intervention_membre"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _missing(table: str, column: str) -> bool:
    return column not in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "provider" not in tables:
        op.create_table(
            "provider",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("home_id", sa.Integer, sa.ForeignKey("home.id", ondelete="CASCADE")),
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("specialty", sa.Text),
            sa.Column("phone", sa.Text),
            sa.Column("email", sa.Text),
            sa.Column("website", sa.Text),
            sa.Column("address", sa.Text),
            sa.Column("customer_ref", sa.Text),
            sa.Column("notes", sa.Text),
            sa.Column("created_at", sa.Text, nullable=False),
            sa.Column("updated_at", sa.Text, nullable=False),
        )
        op.create_index("ix_provider_home", "provider", ["home_id"])

    # ADD COLUMN est natif sous SQLite et ne recree pas la table (voir 0004). Les
    # colonnes arrivent donc sans leur clause REFERENCES ni le CHECK d'exclusivite,
    # que SQLite ne sait pas ajouter apres coup : les deux vivent dans schema.sql
    # pour les installations neuves, et l'exclusivite est tenue par TaskIn,
    # TaskPatch et CompleteIn, seuls chemins d'ecriture (meme parti qu'en 0010).
    if _missing("maintenance_task", "assignee_provider_id"):
        op.add_column("maintenance_task", sa.Column("assignee_provider_id", sa.Integer))
    if _missing("intervention", "performed_by_provider_id"):
        op.add_column("intervention", sa.Column("performed_by_provider_id", sa.Integer))

    _move_companies()


def _move_companies() -> None:
    """Recopie les membres de type 'company' dans `provider`, puis reporte les
    references et supprime les lignes d'origine.

    `contact` etait un champ libre cense contenir 'telephone/email'. Il part dans
    `email` s'il contient une arobase, dans `phone` sinon : seule heuristique de
    cette migration, appliquee a un champ qui ne contenait de toute facon qu'une
    seule chose.
    """
    bind = op.get_bind()
    companies = bind.execute(
        sa.text(
            "SELECT id, home_id, name, contact, created_at, updated_at "
            "FROM member WHERE member_type = 'company'"
        )
    ).all()

    for row in companies:
        contact = (row.contact or "").strip()
        email = contact if "@" in contact else None
        phone = None if "@" in contact else (contact or None)
        provider_id = bind.execute(
            sa.text(
                "INSERT INTO provider (home_id, name, phone, email, created_at, updated_at) "
                "VALUES (:home_id, :name, :phone, :email, :created_at, :updated_at) "
                "RETURNING id"
            ),
            {
                "home_id": row.home_id,
                "name": row.name,
                "phone": phone,
                "email": email,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        ).scalar_one()

        bind.execute(
            sa.text(
                "UPDATE maintenance_task SET assignee_provider_id = :provider_id, "
                "assignee_id = NULL WHERE assignee_id = :member_id"
            ),
            {"provider_id": provider_id, "member_id": row.id},
        )
        bind.execute(
            sa.text(
                "UPDATE intervention SET performed_by_provider_id = :provider_id, "
                "performed_by_member_id = NULL WHERE performed_by_member_id = :member_id"
            ),
            {"provider_id": provider_id, "member_id": row.id},
        )
        bind.execute(sa.text("DELETE FROM member WHERE id = :member_id"), {"member_id": row.id})


def downgrade() -> None:
    # Les prestataires redeviennent des membres de type 'company'. Les champs que
    # `member` ne sait pas porter (metier, site, adresse, numero de client) sont
    # perdus : c'est le prix d'un retour en arriere, et la raison pour laquelle il
    # ne doit servir qu'a deboguer une montee de version.
    bind = op.get_bind()
    providers = bind.execute(
        sa.text("SELECT id, home_id, name, phone, email, created_at, updated_at FROM provider")
    ).all()
    for row in providers:
        member_id = bind.execute(
            sa.text(
                "INSERT INTO member (home_id, name, member_type, contact, created_at, updated_at) "
                "VALUES (:home_id, :name, 'company', :contact, :created_at, :updated_at) "
                "RETURNING id"
            ),
            {
                "home_id": row.home_id,
                "name": row.name,
                "contact": row.phone or row.email,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        ).scalar_one()
        bind.execute(
            sa.text(
                "UPDATE maintenance_task SET assignee_id = :member_id "
                "WHERE assignee_provider_id = :provider_id"
            ),
            {"member_id": member_id, "provider_id": row.id},
        )
        bind.execute(
            sa.text(
                "UPDATE intervention SET performed_by_member_id = :member_id "
                "WHERE performed_by_provider_id = :provider_id"
            ),
            {"member_id": member_id, "provider_id": row.id},
        )

    with op.batch_alter_table("intervention") as batch_op:
        batch_op.drop_column("performed_by_provider_id")
    with op.batch_alter_table("maintenance_task") as batch_op:
        batch_op.drop_column("assignee_provider_id")
    op.drop_index("ix_provider_home", table_name="provider")
    op.drop_table("provider")
