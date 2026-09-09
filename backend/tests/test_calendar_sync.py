"""Synchronisation manuelle des entretiens vers un calendrier Home Assistant."""

import pytest
from fastapi.testclient import TestClient

from mabarak_api.ha_client import HaUnavailableError
from mabarak_api.services import calendar_sync
from mabarak_api.services.calendar_sync import (
    DesiredEvent,
    ExistingEvent,
    diff,
    parse_existing_events,
)


def test_diff_cree_les_evenements_manquants() -> None:
    desired = [DesiredEvent(task_id=1, name="Filtres", asset_name="VMC", due_date="2026-06-01")]
    result = diff(desired, existing=[])

    assert [event.task_id for event in result.to_create] == [1]
    assert result.to_delete == []
    assert result.skipped == 0


def test_diff_ne_touche_pas_un_evenement_deja_a_jour() -> None:
    desired = [DesiredEvent(task_id=1, name="Filtres", asset_name="VMC", due_date="2026-06-01")]
    existing = [ExistingEvent(uid="abc", task_id=1, start_date="2026-06-01")]

    result = diff(desired, existing)

    assert result.to_create == []
    assert result.to_delete == []
    assert result.skipped == 1


def test_diff_recree_quand_la_date_a_change() -> None:
    desired = [DesiredEvent(task_id=1, name="Filtres", asset_name="VMC", due_date="2026-09-01")]
    existing = [ExistingEvent(uid="abc", task_id=1, start_date="2026-06-01")]

    result = diff(desired, existing)

    assert result.to_delete == ["abc"]
    assert [event.task_id for event in result.to_create] == [1]


def test_diff_supprime_les_evenements_dont_la_tache_a_disparu() -> None:
    existing = [ExistingEvent(uid="abc", task_id=1, start_date="2026-06-01")]
    result = diff(desired=[], existing=existing)

    assert result.to_delete == ["abc"]
    assert result.to_create == []


def test_parse_existing_events_ignore_les_evenements_sans_marqueur() -> None:
    raw = [
        {"uid": "abc", "description": "Anniversaire", "start": {"date": "2026-06-01"}},
        {
            "uid": "def",
            "description": "Entretien MaBarak.\n\n[mabarak:42]",
            "start": {"date": "2026-07-01"},
        },
    ]

    parsed = parse_existing_events(raw)

    assert len(parsed) == 1
    assert parsed[0] == ExistingEvent(uid="def", task_id=42, start_date="2026-07-01")


def test_calendar_sync_run_sans_configuration_renvoie_409(client: TestClient) -> None:
    response = client.post("/api/ha/calendar-sync/run")
    assert response.status_code == 409


def test_calendar_sync_run_signale_un_calendrier_non_reactif(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.patch(
        "/api/homes/current",
        json={"ha_calendar_entity_id": "calendar.maison", "ha_calendar_sync_enabled": True},
    )

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise HaUnavailableError("SUPERVISOR_TOKEN absent")

    monkeypatch.setattr(calendar_sync, "get_calendar_events", _boom)

    response = client.post("/api/ha/calendar-sync/run")

    assert response.status_code == 503


def test_calendars_sans_supervisor_renvoie_503(client: TestClient) -> None:
    response = client.get("/api/ha/calendars")
    assert response.status_code == 503
