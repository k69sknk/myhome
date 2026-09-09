"""Notification Home Assistant a la personne assignee a un entretien.

Best-effort : ne doit jamais faire echouer la creation/edition d'un entretien.
Declenchee uniquement au moment de l'assignation (evenement synchrone) — pas de
rappel recurrent a l'approche de l'echeance, qui necessiterait un scheduler
(inexistant dans cet add-on a ce jour).
"""

from __future__ import annotations

import contextlib

from ..ha_client import HaUnavailableError, call_ha_service
from ..models import Home, MaintenanceTask, Member


def notify_assignee(home: Home, task: MaintenanceTask, member: Member) -> None:
    if not home.task_notifications_enabled or not member.ha_notify_service:
        return
    due = task.next_due_on or "a definir"
    with contextlib.suppress(HaUnavailableError):
        call_ha_service(
            "notify",
            member.ha_notify_service,
            {
                "title": "Entretien qui vous est assigne",
                "message": f"{task.name} — echeance {due}",
            },
        )
