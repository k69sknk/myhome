"""Une intervention peut concerner la maison, pas seulement un equipement.

`maintenance_task` accepte depuis l'origine un entretien rattache a la maison —
« tester les detecteurs de fumee », le ramonage quand aucun appareil ne le porte
— et le planning les affiche. Mais `intervention.asset_id` etait NOT NULL : ces
entretiens ne pouvaient donc jamais etre marques comme faits, ni dans
l'interface ni par un agent. Ce n'etait une regle metier nulle part, seulement
une contrainte heritee du moment ou tout pendait a un equipement.

`cost` suit, pour la meme raison : le cout saisi en validant un entretien de la
maison n'aurait eu nulle part ou aller.

**Pourquoi ce remaniement est ecrit a la main.** Rendre une colonne nullable
impose a SQLite de recreer la table. `batch_alter_table` sait le faire, mais il
reconstruit la table a partir de ce que la reflexion lui rend — et la reflexion
SQLite de SQLAlchemy ne rend pas les contraintes CHECK. Le passage aurait donc
silencieusement perdu le CHECK d'adr/0011 sur `intervention` et celui qui borne
`cost_type`. Les tables sont donc reecrites ici en toutes lettres.

**Et pourquoi elle est sure.** Un DROP TABLE sous `foreign_keys = ON` efface
d'abord en cascade tout ce qui reference la table : les documents d'une
intervention auraient disparu avec elle. C'est la perte de donnees dont la 0004
garde la trace. `alembic/env.py` coupe donc l'integrite le temps des migrations
et la verifie avant de rendre la main, comme le prescrit SQLite.

Revision ID: 0015_intervention_maison
Revises: 0014_provenance_ecriture
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "0015_intervention_maison"
down_revision: str | None = "0014_provenance_ecriture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INTERVENTION = """
CREATE TABLE intervention_nouvelle (
    id                INTEGER PRIMARY KEY,
    asset_id          INTEGER          REFERENCES asset(id) ON DELETE CASCADE,
    home_id           INTEGER          REFERENCES home(id)  ON DELETE CASCADE,
    task_id           INTEGER          REFERENCES maintenance_task(id) ON DELETE SET NULL,
    issue_id          INTEGER          REFERENCES issue(id) ON DELETE SET NULL,
    intervention_type TEXT    NOT NULL DEFAULT 'maintenance'
                      CHECK (intervention_type IN ('maintenance', 'repair', 'installation',
                                                   'inspection', 'replacement', 'other')),
    performed_on      TEXT    NOT NULL,
    performed_by      TEXT,
    performed_by_member_id   INTEGER   REFERENCES member(id)   ON DELETE SET NULL,
    performed_by_provider_id INTEGER   REFERENCES provider(id) ON DELETE SET NULL,
    notes             TEXT,
    created_via       TEXT    CHECK (created_via IS NULL OR created_via IN ('ui', 'agent')),
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK (performed_by_member_id IS NULL OR performed_by_provider_id IS NULL),
    CHECK ((asset_id IS NOT NULL) + (home_id IS NOT NULL) = 1)
);
"""

_COST = """
CREATE TABLE cost_nouvelle (
    id              INTEGER PRIMARY KEY,
    asset_id        INTEGER          REFERENCES asset(id) ON DELETE CASCADE,
    home_id         INTEGER          REFERENCES home(id)  ON DELETE CASCADE,
    intervention_id INTEGER          REFERENCES intervention(id) ON DELETE SET NULL,
    cost_type       TEXT    NOT NULL
                    CHECK (cost_type IN ('purchase', 'installation', 'maintenance',
                                         'repair', 'parts', 'subscription', 'other')),
    label           TEXT,
    amount_cents    INTEGER NOT NULL,
    currency        TEXT    NOT NULL DEFAULT 'EUR',
    incurred_on     TEXT    NOT NULL,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    CHECK ((asset_id IS NOT NULL) + (home_id IS NOT NULL) = 1)
);
"""

# La vue lit les deux tables : elle doit disparaitre avant elles, et revenir
# apres. Les lignes rattachees a la maison n'ont pas leur place dans la
# chronologie d'un equipement, d'ou les deux filtres ajoutes.
_VUE = """
CREATE VIEW v_asset_timeline AS

    SELECT a.id                AS asset_id,
           'installation'      AS event_type,
           a.install_date      AS occurred_on,
           'Installation'      AS title,
           a.name              AS detail,
           NULL                AS amount_cents,
           'asset'             AS source_table,
           a.id                AS source_id
    FROM   asset a
    WHERE  a.install_date IS NOT NULL

    UNION ALL

    SELECT i.asset_id,
           'intervention',
           i.performed_on,
           i.intervention_type,
           COALESCE(i.notes, i.performed_by),
           NULL,
           'intervention',
           i.id
    FROM   intervention i
    WHERE  i.asset_id IS NOT NULL

    UNION ALL

    SELECT s.asset_id,
           'issue_opened',
           s.opened_on,
           s.title,
           s.description,
           NULL,
           'issue',
           s.id
    FROM   issue s

    UNION ALL

    SELECT s.asset_id,
           'issue_resolved',
           s.resolved_on,
           s.title,
           COALESCE(s.result, s.action_taken),
           NULL,
           'issue',
           s.id
    FROM   issue s
    WHERE  s.resolved_on IS NOT NULL

    UNION ALL

    SELECT c.asset_id,
           'cost',
           c.incurred_on,
           c.cost_type,
           c.label,
           c.amount_cents,
           'cost',
           c.id
    FROM   cost c
    WHERE  c.intervention_id IS NULL AND c.asset_id IS NOT NULL

    UNION ALL

    SELECT w.asset_id,
           'warranty_end',
           w.end_date,
           'Fin de garantie',
           w.provider,
           NULL,
           'warranty',
           w.id
    FROM   warranty w
    WHERE  w.end_date IS NOT NULL;
"""


def _colonnes(table: str) -> set[str]:
    return {colonne["name"] for colonne in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "home_id" in _colonnes("intervention"):
        return

    op.execute("DROP VIEW IF EXISTS v_asset_timeline")

    op.execute(_INTERVENTION)
    # `home_id` reste NULL : toutes les interventions existantes designent un
    # equipement, par construction de la contrainte qu'on leve ici.
    op.execute(
        "INSERT INTO intervention_nouvelle (id, asset_id, home_id, task_id, issue_id, "
        "intervention_type, performed_on, performed_by, performed_by_member_id, "
        "performed_by_provider_id, notes, created_via, created_at, updated_at) "
        "SELECT id, asset_id, NULL, task_id, issue_id, intervention_type, performed_on, "
        "performed_by, performed_by_member_id, performed_by_provider_id, notes, "
        "created_via, created_at, updated_at FROM intervention"
    )
    op.execute("DROP TABLE intervention")
    op.execute("ALTER TABLE intervention_nouvelle RENAME TO intervention")
    op.execute("CREATE INDEX ix_intervention_asset ON intervention(asset_id, performed_on DESC)")
    op.execute("CREATE INDEX ix_intervention_home  ON intervention(home_id, performed_on DESC)")
    op.execute("CREATE INDEX ix_intervention_task  ON intervention(task_id)")
    op.execute("CREATE INDEX ix_intervention_issue ON intervention(issue_id)")

    op.execute(_COST)
    op.execute(
        "INSERT INTO cost_nouvelle (id, asset_id, home_id, intervention_id, cost_type, label, "
        "amount_cents, currency, incurred_on, notes, created_at, updated_at) "
        "SELECT id, asset_id, NULL, intervention_id, cost_type, label, amount_cents, currency, "
        "incurred_on, notes, created_at, updated_at FROM cost"
    )
    op.execute("DROP TABLE cost")
    op.execute("ALTER TABLE cost_nouvelle RENAME TO cost")
    op.execute("CREATE INDEX ix_cost_asset        ON cost(asset_id)")
    op.execute("CREATE INDEX ix_cost_home         ON cost(home_id)")
    op.execute("CREATE INDEX ix_cost_intervention ON cost(intervention_id)")

    op.execute(_VUE)


def downgrade() -> None:
    # Revenir en arriere perdrait les interventions de la maison, qui n'auraient
    # plus de colonne pour se rattacher. Les effacer en silence serait pire que
    # de refuser : un journal d'entretien ne se defait pas sans le dire.
    restantes = (
        op.get_bind()
        .exec_driver_sql("SELECT COUNT(*) FROM intervention WHERE asset_id IS NULL")
        .scalar()
    )
    if restantes:
        raise RuntimeError(
            f"{restantes} intervention(s) de la maison empechent le retour arriere : "
            "elles n'ont pas d'equipement ou se rattacher. Supprimez-les d'abord si "
            "vous acceptez de les perdre."
        )
    raise NotImplementedError(
        "Retour arriere non ecrit : il faudrait recreer les deux tables avec "
        "asset_id NOT NULL, pour un chemin que personne n'emprunte."
    )
