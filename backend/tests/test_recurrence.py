"""Calcul de la prochaine echeance (ADR-0004)."""

from datetime import date

from homekeeper_api.services.recurrence import Recurrence, compute_next_due, initial_next_due


def test_from_completion_decale_depuis_la_date_reelle() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 3, 20),
        previous_due=date(2026, 3, 1),
        today=date(2026, 3, 20),
        recurrence=Recurrence(recurrence_type="months", interval=3, anchor="from_completion"),
    )

    assert next_due == date(2026, 6, 20)


def test_from_due_date_garde_la_periode_theorique() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 3, 20),
        previous_due=date(2026, 3, 1),
        today=date(2026, 3, 20),
        recurrence=Recurrence(recurrence_type="months", interval=3, anchor="from_due_date"),
    )

    assert next_due == date(2026, 6, 1)


def test_from_due_date_rattrape_plusieurs_intervalles_deja_passes() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 3, 20),
        previous_due=date(2025, 3, 1),
        today=date(2026, 3, 20),
        recurrence=Recurrence(recurrence_type="months", interval=3, anchor="from_due_date"),
    )

    assert next_due == date(2026, 6, 1)


def test_ponctuel_n_a_plus_de_prochaine_date() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 3, 20),
        previous_due=date(2026, 3, 1),
        today=date(2026, 3, 20),
        recurrence=Recurrence(recurrence_type="none"),
    )

    assert next_due is None


def test_une_fois_par_an_reste_le_meme_jour() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 3, 20),
        previous_due=date(2026, 3, 1),
        today=date(2026, 3, 20),
        recurrence=Recurrence(
            recurrence_type="annual_fixed",
            anchor="from_due_date",
            fixed_month=3,
            fixed_day=1,
        ),
    )

    assert next_due == date(2027, 3, 1)


def test_29_fevrier_plus_un_an_donne_le_28() -> None:
    next_due = compute_next_due(
        completed_on=date(2024, 2, 29),
        previous_due=None,
        today=date(2024, 2, 29),
        recurrence=Recurrence(recurrence_type="years", interval=1, anchor="from_completion"),
    )

    assert next_due == date(2025, 2, 28)


def test_intervalle_sans_dernier_part_d_aujourd_hui() -> None:
    next_due = initial_next_due(
        last_completed_on=None,
        today=date(2026, 9, 8),
        recurrence=Recurrence(recurrence_type="months", interval=3, anchor="from_completion"),
    )

    assert next_due == date(2026, 12, 8)
