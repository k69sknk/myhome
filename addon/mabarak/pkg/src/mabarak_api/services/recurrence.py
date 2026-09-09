"""Calcul de `next_due_on` (ADR-0004).

Point d'entree unique : validation d'entretien et changement de planification.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

RecurrenceType = Literal["none", "days", "months", "years", "annual_fixed", "custom_date"]
RecurrenceAnchor = Literal["from_completion", "from_due_date"]


@dataclass(frozen=True)
class Recurrence:
    recurrence_type: RecurrenceType
    interval: int | None = None
    anchor: RecurrenceAnchor = "from_completion"
    fixed_month: int | None = None
    fixed_day: int | None = None
    custom_due_date: date | None = None


def hidden_anchor(recurrence_type: RecurrenceType) -> RecurrenceAnchor:
    """Ancrage impose par l'UI, jamais saisi par l'utilisateur."""
    if recurrence_type == "annual_fixed":
        return "from_due_date"
    return "from_completion"


def compute_next_due(
    *,
    completed_on: date,
    previous_due: date | None,
    today: date,
    recurrence: Recurrence,
) -> date | None:
    """Prochaine echeance apres une realisation le `completed_on`."""
    if recurrence.recurrence_type in {"none", "custom_date"}:
        return None

    if recurrence.recurrence_type == "annual_fixed":
        return _next_annual_fixed(completed_on, previous_due, today, recurrence)

    if recurrence.anchor == "from_completion":
        return _add_interval(completed_on, recurrence)

    origin = previous_due if previous_due is not None else completed_on
    candidate = _add_interval(origin, recurrence)
    while candidate < today:
        candidate = _add_interval(candidate, recurrence)
    return candidate


def initial_next_due(
    *, last_completed_on: date | None, today: date, recurrence: Recurrence
) -> date | None:
    """Echeance a la creation d'une tache, avant toute validation."""
    if last_completed_on is not None:
        return compute_next_due(
            completed_on=last_completed_on,
            previous_due=None,
            today=last_completed_on,
            recurrence=recurrence,
        )
    if recurrence.recurrence_type == "annual_fixed":
        month = recurrence.fixed_month
        day = recurrence.fixed_day
        if month is None or day is None:
            return None
        candidate = _clamp_day(today.year, month, day)
        if candidate < today:
            candidate = _clamp_day(today.year + 1, month, day)
        return candidate
    if recurrence.recurrence_type == "custom_date":
        return recurrence.custom_due_date
    if recurrence.recurrence_type in {"days", "months", "years"}:
        # Sans dernier entretien, la premiere echeance est dans un intervalle
        # a partir d'aujourd'hui (pas de rattrapage, pas de tache orpheline).
        return _add_interval(today, recurrence)
    return None


def _add_interval(origin: date, recurrence: Recurrence) -> date:
    interval = recurrence.interval if recurrence.interval is not None else 1
    if recurrence.recurrence_type == "days":
        return origin + timedelta(days=interval)
    if recurrence.recurrence_type == "months":
        return _add_months(origin, interval)
    if recurrence.recurrence_type == "years":
        return _add_months(origin, interval * 12)
    raise ValueError(f"intervalle inapplicable a {recurrence.recurrence_type}")


def _add_months(origin: date, months: int) -> date:
    month_index = origin.month - 1 + months
    year = origin.year + month_index // 12
    month = month_index % 12 + 1
    day = min(origin.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _next_annual_fixed(
    completed_on: date,
    previous_due: date | None,
    today: date,
    recurrence: Recurrence,
) -> date:
    month = recurrence.fixed_month
    day = recurrence.fixed_day
    if month is None or day is None:
        raise ValueError("annual_fixed exige fixed_month et fixed_day")

    if recurrence.anchor == "from_due_date" and previous_due is not None:
        year = previous_due.year + 1
        candidate = _clamp_day(year, month, day)
        while candidate < today:
            year += 1
            candidate = _clamp_day(year, month, day)
        return candidate

    year = completed_on.year
    candidate = _clamp_day(year, month, day)
    if candidate <= completed_on:
        candidate = _clamp_day(year + 1, month, day)
    while candidate < today:
        year += 1
        candidate = _clamp_day(year, month, day)
        if candidate <= completed_on:
            candidate = _clamp_day(year + 1, month, day)
    return candidate
