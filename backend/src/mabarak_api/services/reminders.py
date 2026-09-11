"""Rappel des entretiens qui arrivent a echeance, ou qui sont en retard.

Complement du rappel a l'assignation (`notifications.py`), qui ne se declenche
qu'une fois, au moment ou l'entretien est confie a quelqu'un. Ici c'est le temps
qui passe qui declenche : un passage par jour, a heure fixe, lance par
`scheduler.py` (adr/0009 pour le choix du planificateur).

Trois regles portent tout le module, et elles existent pour la meme raison — un
rappel qu'on apprend a ignorer ne rappelle plus rien :

1.  **Un message par personne, pas un par entretien.** Le didacticiel cree des
    dizaines d'echeances ; les notifier une par une viderait la boite de
    reception de l'utilisateur le jour ou plusieurs tombent ensemble.
2.  **Pas de relance quotidienne.** `maintenance_task.last_reminded_on` retient la
    date du dernier rappel pour l'echeance en cours ; un entretien deja rappele
    se tait pendant `RELANCE_DAYS` jours. La colonne est remise a NULL des que
    `next_due_on` change, donc une nouvelle echeance a toujours droit a la parole.
3.  **Jamais bloquant.** Home Assistant injoignable n'est pas une erreur de
    l'application : l'envoi rate est signale, la trace n'est pas ecrite, et le
    rappel repart au passage suivant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import local_now
from ..ha_client import HaUnavailableError
from ..models import Asset, Home, MaintenanceTask, Member, TaskStatusRow
from .home import ensure_home
from .notifications import send_notification

# Delai avant de re-parler d'un entretien deja rappele. Une semaine : assez long
# pour ne pas harceler sur un entretien qu'on repousse sciemment, assez court pour
# qu'un oubli reel refasse surface.
RELANCE_DAYS = 7

# Au-dela, le message devient une liste qu'on ne lit plus. Le reste est compte.
MAX_LINES = 8

_REMINDED_STATUSES = frozenset({"overdue", "due_soon"})


@dataclass(frozen=True)
class Reminder:
    """Le message destine a UN service de notification."""

    service: str
    title: str
    message: str
    task_ids: tuple[int, ...]


@dataclass(frozen=True)
class ReminderPlan:
    """Ce qu'un passage enverrait, sans rien envoyer."""

    reminders: tuple[Reminder, ...] = ()
    # Entretiens a rappeler que personne ne recevra : ni la personne assignee ni
    # la maison n'a de service de notification. Affiche dans les reglages, sinon
    # le rappel serait silencieusement inutile.
    without_recipient: int = 0


@dataclass
class ReminderRun:
    """Ce qu'un passage a reellement fait."""

    sent: int = 0
    tasks: int = 0
    without_recipient: int = 0
    errors: list[str] = field(default_factory=list)


class ReminderConfigurationError(Exception):
    """Notifications desactivees dans les reglages de la maison."""


@dataclass(frozen=True)
class _Line:
    task_id: int
    status: str
    days_until_due: int
    text: str


def is_pass_due(home: Home, now: datetime) -> bool:
    """Un passage est-il attendu maintenant ?

    Vrai si aucun passage n'a eu lieu aujourd'hui et que l'heure choisie est
    atteinte. C'est cette formulation — et non « il est exactement 8h » — qui
    donne le rattrapage : un add-on eteint toute la matinee rappelle au demarrage
    plutot que de sauter la journee.
    """
    if home.last_reminder_run_on == now.date().isoformat():
        return False
    return now.hour >= home.reminder_hour


def plan_reminders(session: Session, *, today: date | None = None) -> ReminderPlan:
    """Les messages a envoyer, sans rien envoyer ni ecrire.

    Separe de l'envoi pour rester testable sans Home Assistant, et parce que
    l'ecran des reglages a besoin de dire ce qu'un passage ferait.
    """
    home = ensure_home(session)
    day = today if today is not None else local_now().date()
    tasks = {task.id: task for task in session.scalars(select(MaintenanceTask)).all()}
    members = {member.id: member for member in session.scalars(select(Member)).all()}
    asset_names = {asset.id: asset.name for asset in session.scalars(select(Asset)).all()}

    by_service: dict[str, list[_Line]] = {}
    without_recipient = 0
    for row in session.scalars(select(TaskStatusRow)).all():
        task = tasks.get(row.task_id)
        if task is None or not _needs_reminder(row, task, today=day):
            continue
        service = _recipient(task, home, members)
        if service is None:
            without_recipient += 1
            continue
        asset_name = asset_names.get(task.asset_id) if task.asset_id is not None else None
        by_service.setdefault(service, []).append(_line(row, asset_name))

    return ReminderPlan(
        reminders=tuple(_message(service, lines) for service, lines in sorted(by_service.items())),
        without_recipient=without_recipient,
    )


def run_reminders(session: Session, *, today: date | None = None) -> ReminderRun:
    """Envoie les rappels dus et note la date sur chaque entretien rappele."""
    home = ensure_home(session)
    if not home.task_notifications_enabled:
        raise ReminderConfigurationError(
            "Activez les notifications dans les reglages pour recevoir les rappels."
        )

    day = today if today is not None else local_now().date()
    plan = plan_reminders(session, today=day)
    result = ReminderRun(without_recipient=plan.without_recipient)

    for reminder in plan.reminders:
        try:
            send_notification(reminder.service, reminder.title, reminder.message)
        except HaUnavailableError as exc:
            result.errors.append(f"Envoi impossible vers notify.{reminder.service} : {exc}")
            continue
        result.sent += 1
        result.tasks += len(reminder.task_ids)
        for task_id in reminder.task_ids:
            task = session.get(MaintenanceTask, task_id)
            if task is not None:
                task.last_reminded_on = day.isoformat()

    session.flush()
    return result


def _needs_reminder(row: TaskStatusRow, task: MaintenanceTask, *, today: date) -> bool:
    if row.status not in _REMINDED_STATUSES:
        return False
    if task.last_reminded_on is None:
        return True
    return date.fromisoformat(task.last_reminded_on) <= today - timedelta(days=RELANCE_DAYS)


def _recipient(task: MaintenanceTask, home: Home, members: dict[int, Member]) -> str | None:
    """Le service `notify.*` a prevenir pour cet entretien.

    La personne assignee d'abord ; a defaut le service par defaut de la maison —
    y compris quand l'entretien EST assigne mais que la personne n'a pas de
    service renseigne, cas ou se taire ferait disparaitre l'entretien du radar.
    """
    if task.assignee_id is not None:
        member = members.get(task.assignee_id)
        if member is not None and member.ha_notify_service:
            return member.ha_notify_service
    return home.default_notify_service or None


def _line(row: TaskStatusRow, asset_name: str | None) -> _Line:
    days = row.days_until_due if row.days_until_due is not None else 0
    label = f"{row.name} — {asset_name}" if asset_name else row.name
    if row.status == "overdue":
        late = abs(days)
        delay = "depuis hier" if late == 1 else f"depuis {late} jours"
        text = f"⚠ {label}, en retard {delay}"
    elif days <= 0:
        text = f"{label}, a faire aujourd'hui"
    elif days == 1:
        text = f"{label}, demain"
    else:
        text = f"{label}, dans {days} jours"
    return _Line(task_id=row.task_id, status=row.status, days_until_due=days, text=text)


def _message(service: str, lines: list[_Line]) -> Reminder:
    # Le plus urgent en tete : le plus en retard d'abord.
    ordered = sorted(lines, key=lambda line: (line.days_until_due, line.text))
    shown = ordered[:MAX_LINES]
    body = "\n".join(line.text for line in shown)
    hidden = len(ordered) - len(shown)
    if hidden > 0:
        body += f"\n… et {hidden} autre{'s' if hidden > 1 else ''}."

    late = sum(1 for line in ordered if line.status == "overdue")
    if late == len(ordered):
        title = "Entretiens en retard" if late > 1 else "Entretien en retard"
    elif late > 0:
        title = f"Entretiens a faire, dont {late} en retard"
    else:
        title = "Entretiens a faire" if len(ordered) > 1 else "Entretien a faire"

    return Reminder(
        service=service,
        title=title,
        message=body,
        task_ids=tuple(line.task_id for line in ordered),
    )
