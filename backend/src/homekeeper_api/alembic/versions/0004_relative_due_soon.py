"""Seuil "bientot" resserre automatiquement selon la frequence de l'entretien.

Le seuil de la maison (due_soon_threshold_days) devient un plafond : chaque
entretien recurrent (days/months/years) le resserre a un tiers de son propre
intervalle, jamais moins d'un jour. Sans ce resserrement, un seuil fixe de
30 jours laissait un entretien mensuel perpetuellement 'due_soon' des qu'il
etait marque fait.

Vue seulement (DROP VIEW / CREATE VIEW) : aucune table n'est touchee. Une
premiere version de ce correctif recreait la table `home` pour la rendre
nullable, ce qui a declenche une suppression en cascade de tout ce qui
reference home_id (asset ON DELETE CASCADE, et donc tout en dessous) --
SQLite n'y desactive pas les contraintes FK au milieu d'une transaction, et
cet environnement Alembic execute toutes les migrations dans une transaction
unique. Approche abandonnee au profit de ce plafond, qui ne modifie aucune
donnee ni aucune table.

Revision ID: 0004_relative_due_soon
Revises: 0003_task_prep_fields
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_relative_due_soon"
down_revision: str | None = "0003_task_prep_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_VIEW = """
CREATE VIEW v_task_status AS
    SELECT t.id                AS task_id,
           t.asset_id,
           t.home_id,
           t.name,
           t.priority,
           t.next_due_on,
           t.last_completed_on,
           COALESCE(t.lead_time_days, h.due_soon_threshold_days) AS effective_lead_time_days,
           CAST(julianday(t.next_due_on) - julianday(date('now')) AS INTEGER) AS days_until_due,
           CASE
               WHEN t.next_due_on IS NULL THEN 'unscheduled'
               WHEN julianday(t.next_due_on) < julianday(date('now')) THEN 'overdue'
               WHEN julianday(t.next_due_on) - julianday(date('now'))
                    <= COALESCE(t.lead_time_days, h.due_soon_threshold_days) THEN 'due_soon'
               ELSE 'ok'
           END AS status
    FROM       maintenance_task t
    LEFT JOIN  asset a ON a.id = t.asset_id
    LEFT JOIN  home  h ON h.id = COALESCE(a.home_id, t.home_id)
    WHERE      t.is_active = 1;
"""

_NEW_VIEW = """
CREATE VIEW v_task_status AS
    WITH base AS (
        SELECT t.id                AS task_id,
               t.asset_id,
               t.home_id,
               t.name,
               t.priority,
               t.next_due_on,
               t.last_completed_on,
               COALESCE(
                   t.lead_time_days,
                   MIN(
                       h.due_soon_threshold_days,
                       CASE t.recurrence_type
                           WHEN 'days'   THEN MAX(1, t.recurrence_interval / 3)
                           WHEN 'months' THEN MAX(1, (t.recurrence_interval * 30) / 3)
                           WHEN 'years'  THEN MAX(1, (t.recurrence_interval * 365) / 3)
                           ELSE h.due_soon_threshold_days
                       END
                   )
               ) AS effective_lead_time_days
        FROM       maintenance_task t
        LEFT JOIN  asset a ON a.id = t.asset_id
        LEFT JOIN  home  h ON h.id = COALESCE(a.home_id, t.home_id)
        WHERE      t.is_active = 1
    )
    SELECT task_id, asset_id, home_id, name, priority, next_due_on, last_completed_on,
           effective_lead_time_days,
           CAST(julianday(next_due_on) - julianday(date('now')) AS INTEGER) AS days_until_due,
           CASE
               WHEN next_due_on IS NULL THEN 'unscheduled'
               WHEN julianday(next_due_on) < julianday(date('now')) THEN 'overdue'
               WHEN julianday(next_due_on) - julianday(date('now')) <= effective_lead_time_days
                   THEN 'due_soon'
               ELSE 'ok'
           END AS status
    FROM base;
"""


def upgrade() -> None:
    op.execute("DROP VIEW v_task_status")
    op.execute(_NEW_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW v_task_status")
    op.execute(_OLD_VIEW)
