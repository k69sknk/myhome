"""Calcul de `next_due_on` (ADR-0004, ADR-0010).

Point d'entree unique : validation d'entretien et changement de planification.

Deux notions s'y croisent, et elles sont volontairement independantes :

*   l'**ancrage** (ADR-0004) decide DEPUIS QUOI l'echeance se calcule — la date
    reelle de realisation ou la date theorique ;
*   la **saison** (ADR-0010) decide QUAND cette echeance a un sens. Une tonte
    revient toutes les semaines, mais pas en janvier.

La saison n'est donc pas un type de recurrence de plus : elle s'applique APRES le
calcul, en repoussant a l'ouverture de la saison suivante une echeance qui
tomberait hors saison. L'ancrage garde ainsi exactement le comportement decrit
par l'ADR-0004.
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

    # Fenetre de saison, bornes incluses, ou None si l'entretien vaut toute
    # l'annee. Les deux vont ensemble. La fenetre peut enjamber le nouvel an
    # (11 -> 2 pour un entretien d'hiver).
    season_start_month: int | None = None
    season_end_month: int | None = None

    @property
    def has_season(self) -> bool:
        return self.season_start_month is not None and self.season_end_month is not None


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
        # Une date fixe porte deja son mois : la saison ne s'y applique pas.
        return _next_annual_fixed(completed_on, previous_due, today, recurrence)

    if recurrence.anchor == "from_completion":
        return in_season_or_next_opening(_add_interval(completed_on, recurrence), recurrence)

    origin = previous_due if previous_due is not None else completed_on
    candidate = _add_interval(origin, recurrence)
    while candidate < today:
        candidate = _add_interval(candidate, recurrence)
    return in_season_or_next_opening(candidate, recurrence)


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
        return in_season_or_next_opening(_add_interval(today, recurrence), recurrence)
    return None


def in_season(month: int, recurrence: Recurrence) -> bool:
    """Ce mois tombe-t-il dans la fenetre de saison ? Vrai s'il n'y en a pas."""
    start, end = recurrence.season_start_month, recurrence.season_end_month
    if start is None or end is None:
        return True
    if start <= end:
        return start <= month <= end
    # Fenetre a cheval sur le nouvel an : novembre -> fevrier.
    return month >= start or month <= end


def in_season_or_next_opening(candidate: date, recurrence: Recurrence) -> date:
    """`candidate` telle quelle si elle est en saison, sinon l'ouverture suivante.

    Repousser plutot que decaler de proche en proche : une tonte hebdomadaire
    interrompue en novembre reprend le 1er mars, elle ne rattrape pas les vingt
    tontes que l'hiver a sautees.
    """
    start = recurrence.season_start_month
    if start is None or in_season(candidate.month, recurrence):
        return candidate
    opening = date(candidate.year, start, 1)
    if opening < candidate:
        opening = date(candidate.year + 1, start, 1)
    return opening


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
