"""Synchronisation (manuelle) des entretiens vers un calendrier Home Assistant.

L'utilisateur choisit un calendrier HA existant (Local Calendar, CalDAV...) dans
les reglages ; ce module y pousse un evenement par entretien a echeance, via les
services HA `calendar.create_event` / `calendar.delete_event`. Tous les
calendriers HA ne supportent pas ces services (Google Calendar, par exemple, est
en lecture seule cote HA) : la synchronisation est donc declenchee a la demande,
jamais en tache de fond, pour que l'utilisateur voie immediatement si son
calendrier choisi le permet.

Chaque evenement cree porte un marqueur `[mabarak:<task_id>]` dans sa
description : c'est le seul moyen de retrouver, au prochain lancement, quels
evenements du calendrier appartiennent a MaBarak (les services HA ne renvoient
pas d'identifiant a la creation). Les evenements sans ce marqueur ne sont jamais
touches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import utc_today
from ..ha_client import HaUnavailableError, call_ha_service, get_calendar_events
from ..models import Asset, TaskStatusRow
from ..schemas import CalendarSyncResult
from .home import ensure_home

_MARKER_RE = re.compile(r"\[mabarak:(\d+)\]")

# Meme fenetre que /api/ha/summary pour la creation, elargie vers le passe pour
# retrouver les evenements crees lors d'un run precedent sur des taches restees
# longtemps en retard.
_WINDOW_FUTURE_DAYS = 180
_WINDOW_PAST_DAYS = 400


class CalendarSyncConfigurationError(Exception):
    """Sync desactivee ou aucun calendrier choisi dans les reglages."""


@dataclass(frozen=True)
class DesiredEvent:
    task_id: int
    name: str
    asset_name: str | None
    due_date: str


@dataclass(frozen=True)
class ExistingEvent:
    uid: str | None
    task_id: int | None
    start_date: str | None


@dataclass
class DiffResult:
    to_create: list[DesiredEvent] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)
    skipped: int = 0


def parse_existing_events(raw_events: list[dict[str, Any]]) -> list[ExistingEvent]:
    """Ne garde que les evenements portant le marqueur MaBarak."""
    result: list[ExistingEvent] = []
    for raw in raw_events:
        match = _MARKER_RE.search(str(raw.get("description") or ""))
        if match is None:
            continue
        start = raw.get("start") or {}
        start_date = start.get("date") or str(start.get("dateTime") or "")[:10] or None
        result.append(
            ExistingEvent(uid=raw.get("uid"), task_id=int(match.group(1)), start_date=start_date)
        )
    return result


def diff(desired: list[DesiredEvent], existing: list[ExistingEvent]) -> DiffResult:
    """Calcule les creations/suppressions necessaires, sans effet de bord."""
    existing_by_task = {event.task_id: event for event in existing if event.task_id is not None}
    desired_ids = {event.task_id for event in desired}
    result = DiffResult()

    for wanted in desired:
        current = existing_by_task.get(wanted.task_id)
        if current is None:
            result.to_create.append(wanted)
        elif current.start_date != wanted.due_date:
            if current.uid:
                result.to_delete.append(current.uid)
            result.to_create.append(wanted)
        else:
            result.skipped += 1

    for task_id, current in existing_by_task.items():
        if task_id not in desired_ids and current.uid:
            result.to_delete.append(current.uid)

    return result


def _desired_events(session: Session, window_start: str, window_end: str) -> list[DesiredEvent]:
    asset_name_by_id = {asset.id: asset.name for asset in session.scalars(select(Asset)).all()}
    rows = session.scalars(select(TaskStatusRow)).all()
    return [
        DesiredEvent(
            task_id=row.task_id,
            name=row.name,
            asset_name=asset_name_by_id.get(row.asset_id) if row.asset_id else None,
            due_date=row.next_due_on,
        )
        for row in rows
        if row.next_due_on is not None and window_start <= row.next_due_on <= window_end
    ]


def run_calendar_sync(session: Session) -> CalendarSyncResult:
    home = ensure_home(session)
    if not home.ha_calendar_sync_enabled or not home.ha_calendar_entity_id:
        raise CalendarSyncConfigurationError(
            "Choisissez un calendrier et activez la synchronisation dans les reglages."
        )
    entity_id = home.ha_calendar_entity_id

    today = utc_today()
    window_start = (today - timedelta(days=_WINDOW_PAST_DAYS)).isoformat()
    window_end = (today + timedelta(days=_WINDOW_FUTURE_DAYS)).isoformat()
    desired = _desired_events(session, window_start, window_end)
    raw_events = get_calendar_events(entity_id, window_start, window_end)
    plan = diff(desired, parse_existing_events(raw_events))

    result = CalendarSyncResult(skipped=plan.skipped)

    for uid in plan.to_delete:
        try:
            call_ha_service("calendar", "delete_event", {"entity_id": entity_id, "uid": uid})
            result.deleted += 1
        except HaUnavailableError as exc:
            result.errors.append(f"Suppression impossible sur ce calendrier : {exc}")
            return result

    for wanted in plan.to_create:
        summary = f"{wanted.name} — {wanted.asset_name}" if wanted.asset_name else wanted.name
        end_date = (date.fromisoformat(wanted.due_date) + timedelta(days=1)).isoformat()
        try:
            call_ha_service(
                "calendar",
                "create_event",
                {
                    "entity_id": entity_id,
                    "summary": summary,
                    "description": f"Entretien MaBarak.\n\n[mabarak:{wanted.task_id}]",
                    "start_date": wanted.due_date,
                    "end_date": end_date,
                },
            )
            result.created += 1
        except HaUnavailableError as exc:
            result.errors.append(
                "Ce calendrier ne semble pas accepter la creation d'evenements "
                f"depuis Home Assistant : {exc}"
            )
            break

    return result
