"""Assemblage des fiches, lieux et taches."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import utc_now_iso, utc_today
from ..models import Asset, HaLink, Intervention, Location, MaintenanceTask, TaskStatusRow
from .recurrence import (
    Recurrence,
    RecurrenceType,
    compute_next_due,
    hidden_anchor,
    initial_next_due,
)


def location_path(session: Session, location_id: int | None) -> str | None:
    if location_id is None:
        return None
    parts: list[str] = []
    current_id: int | None = location_id
    seen: set[int] = set()
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        location = session.get(Location, current_id)
        if location is None:
            break
        parts.append(location.name)
        current_id = location.parent_id
    if not parts:
        return None
    return " > ".join(reversed(parts))


def would_create_cycle(session: Session, location_id: int, new_parent_id: int) -> bool:
    current_id: int | None = new_parent_id
    seen: set[int] = set()
    while current_id is not None and current_id not in seen:
        if current_id == location_id:
            return True
        seen.add(current_id)
        parent = session.get(Location, current_id)
        current_id = None if parent is None else parent.parent_id
    return False


def recurrence_from_task(task: MaintenanceTask) -> Recurrence:
    return Recurrence(
        recurrence_type=task.recurrence_type,  # type: ignore[arg-type]
        interval=task.recurrence_interval,
        anchor=task.recurrence_anchor,  # type: ignore[arg-type]
        fixed_month=task.fixed_month,
        fixed_day=task.fixed_day,
        custom_due_date=date.fromisoformat(task.custom_due_date) if task.custom_due_date else None,
    )


def plan_task(
    *,
    recurrence_type: RecurrenceType,
    interval: int | None,
    fixed_month: int | None,
    fixed_day: int | None,
    last_completed_on: str | None,
) -> tuple[str, str | None]:
    recurrence = Recurrence(
        recurrence_type=recurrence_type,
        interval=interval,
        anchor=hidden_anchor(recurrence_type),
        fixed_month=fixed_month,
        fixed_day=fixed_day,
    )
    last = date.fromisoformat(last_completed_on) if last_completed_on else None
    nxt = initial_next_due(last_completed_on=last, today=utc_today(), recurrence=recurrence)
    return recurrence.anchor, nxt.isoformat() if nxt else None


def complete_task(
    session: Session,
    task: MaintenanceTask,
    *,
    performed_on: str,
    performed_by: str | None,
    notes: str | None,
) -> None:
    if task.asset_id is None:
        raise ValueError("tache sans equipement")
    now = utc_now_iso()
    session.add(
        Intervention(
            asset_id=task.asset_id,
            task_id=task.id,
            intervention_type="maintenance",
            performed_on=performed_on,
            performed_by=performed_by,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
    )
    previous = date.fromisoformat(task.next_due_on) if task.next_due_on else None
    nxt = compute_next_due(
        completed_on=date.fromisoformat(performed_on),
        previous_due=previous,
        today=utc_today(),
        recurrence=recurrence_from_task(task),
    )
    task.last_completed_on = performed_on
    task.next_due_on = nxt.isoformat() if nxt else None
    task.updated_at = now


def primary_ha_link(asset: Asset) -> HaLink | None:
    for link in asset.ha_links:
        if link.role == "primary":
            return link
    return asset.ha_links[0] if asset.ha_links else None


def task_status_map(session: Session, task_ids: list[int]) -> dict[int, TaskStatusRow]:
    if not task_ids:
        return {}
    rows = session.scalars(select(TaskStatusRow).where(TaskStatusRow.task_id.in_(task_ids))).all()
    return {row.task_id: row for row in rows}


def worst_status(statuses: list[str]) -> str:
    order = {"overdue": 0, "due_soon": 1, "ok": 2, "unscheduled": 3}
    if not statuses:
        return "unscheduled"
    return min(statuses, key=lambda item: order.get(item, 9))
