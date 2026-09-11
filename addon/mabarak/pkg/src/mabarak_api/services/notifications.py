"""Envoi de notifications Home Assistant (`notify.*`).

Deux declencheurs, deux modules : ici l'evenement synchrone — un entretien vient
d'etre confie a quelqu'un, on le lui dit tout de suite. Le rappel a l'approche de
l'echeance, lui, depend du temps qui passe et vit dans `reminders.py`.

Best-effort dans les deux cas : une notification ratee ne doit jamais faire
echouer la creation ou l'edition d'un entretien.
"""

from __future__ import annotations

import contextlib

from ..ha_client import HaUnavailableError, call_ha_service
from ..models import Home, MaintenanceTask, Member


def send_notification(service: str, title: str, message: str) -> None:
    """Appelle `notify.<service>`. Laisse remonter `HaUnavailableError`.

    L'appelant decide quoi en faire : le silence pour une notification d'assignation,
    un compte-rendu d'erreur pour un passage de rappel.
    """
    call_ha_service("notify", service, {"title": title, "message": message})


def notify_assignee(home: Home, task: MaintenanceTask, member: Member) -> None:
    if not home.task_notifications_enabled or not member.ha_notify_service:
        return
    due = task.next_due_on or "a definir"
    with contextlib.suppress(HaUnavailableError):
        send_notification(
            member.ha_notify_service,
            "Entretien qui vous est assigne",
            f"{task.name} — echeance {due}",
        )
