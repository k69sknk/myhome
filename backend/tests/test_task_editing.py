"""Edition d'entretiens : date ponctuelle, PATCH, pieces multiples, delegation."""

import pytest
from fastapi.testclient import TestClient

from mabarak_api.routers import assets as assets_router


def _create_asset(client: TestClient, name: str = "Chaudiere") -> int:
    return int(client.post("/api/assets", json={"name": name}).json()["id"])


def test_entretien_ponctuel_a_une_date_et_apparait_dans_upcoming_tasks(
    client: TestClient,
) -> None:
    asset_id = _create_asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Reparation fuite",
            "recurrence_type": "custom_date",
            "custom_due_date": "2026-12-01",
        },
    )
    assert task.status_code == 201
    body = task.json()
    assert body["next_due_on"] == "2026-12-01"

    summary = client.get("/api/ha/summary").json()
    entry = next(item for item in summary["upcoming_tasks"] if item["id"] == body["id"])
    assert entry["due_date"] == "2026-12-01"


def test_entretien_ponctuel_sans_date_est_refuse(client: TestClient) -> None:
    asset_id = _create_asset(client)
    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Reparation fuite", "recurrence_type": "custom_date"},
    )
    assert response.status_code == 422


def test_patch_champ_simple_ne_recalcule_pas_lecheance(client: TestClient) -> None:
    asset_id = _create_asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Filtres",
            "recurrence_type": "months",
            "recurrence_interval": 3,
            "last_completed_on": "2026-01-01",
        },
    ).json()

    patched = client.patch(f"/api/tasks/{task['id']}", json={"notes": "Verifier le joint aussi"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["next_due_on"] == task["next_due_on"]
    assert body["notes"] == "Verifier le joint aussi"


def test_patch_frequence_recalcule_lecheance(client: TestClient) -> None:
    asset_id = _create_asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Filtres",
            "recurrence_type": "months",
            "recurrence_interval": 3,
            "last_completed_on": "2026-01-01",
        },
    ).json()
    assert task["next_due_on"] == "2026-04-01"

    patched = client.patch(f"/api/tasks/{task['id']}", json={"recurrence_interval": 6}).json()
    assert patched["next_due_on"] == "2026-07-01"


def test_patch_remplace_les_pieces_en_bloc(client: TestClient) -> None:
    asset_id = _create_asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Filtres",
            "replacement_parts": [{"name": "Filtre A"}, {"name": "Filtre B", "source": "Amazon"}],
        },
    ).json()
    assert [part["name"] for part in task["replacement_parts"]] == ["Filtre A", "Filtre B"]

    patched = client.patch(
        f"/api/tasks/{task['id']}", json={"replacement_parts": [{"name": "Filtre C"}]}
    ).json()
    assert [part["name"] for part in patched["replacement_parts"]] == ["Filtre C"]

    cleared = client.patch(f"/api/tasks/{task['id']}", json={"replacement_parts": []}).json()
    assert cleared["replacement_parts"] == []


def test_patch_entretien_introuvable_renvoie_404(client: TestClient) -> None:
    response = client.patch("/api/tasks/999", json={"notes": "x"})
    assert response.status_code == 404


def test_membres_crud(client: TestClient) -> None:
    created = client.post("/api/members", json={"name": "Alice", "member_type": "household"})
    assert created.status_code == 201
    member = created.json()
    assert member["member_type"] == "household"

    listed = client.get("/api/members").json()
    assert any(row["id"] == member["id"] for row in listed)

    patched = client.patch(
        f"/api/members/{member['id']}", json={"member_type": "company", "contact": "01 02 03"}
    ).json()
    assert patched["member_type"] == "company"
    assert patched["contact"] == "01 02 03"

    deleted = client.delete(f"/api/members/{member['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/members").json() == []


def test_assigner_un_entretien_desassigne_si_le_membre_est_supprime(client: TestClient) -> None:
    asset_id = _create_asset(client)
    member = client.post("/api/members", json={"name": "Bob"}).json()
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Tondre la pelouse", "assignee_id": member["id"]},
    ).json()
    assert task["assignee_name"] == "Bob"

    client.delete(f"/api/members/{member['id']}")

    refreshed = client.get("/api/tasks").json()[0]
    assert refreshed["assignee_id"] is None
    assert refreshed["assignee_name"] is None


def test_assignation_declenche_une_notification_best_effort(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.patch("/api/homes/current", json={"task_notifications_enabled": True})
    member = client.post(
        "/api/members", json={"name": "Alice", "ha_notify_service": "mobile_app_alice"}
    ).json()
    asset_id = _create_asset(client)

    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(
        assets_router,
        "notify_assignee",
        lambda home, task, m: calls.append((home.id, task.id, m.name)),
    )

    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Nettoyer la gouttiere", "assignee_id": member["id"]},
    ).json()

    assert len(calls) == 1
    assert calls[0][2] == "Alice"
    assert calls[0][1] == task["id"]


def test_priorite_par_defaut_normale_et_editable(client: TestClient) -> None:
    asset_id = _create_asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres"},
    ).json()
    assert task["priority"] == "normal"

    task_haute = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Detartrage", "priority": "high"},
    ).json()
    assert task_haute["priority"] == "high"

    patched = client.patch(f"/api/tasks/{task['id']}", json={"priority": "critical"}).json()
    assert patched["priority"] == "critical"


def test_priorite_invalide_est_refusee(client: TestClient) -> None:
    asset_id = _create_asset(client)
    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres", "priority": "extreme"},
    )
    assert response.status_code == 422


def test_liste_des_taches_triee_par_priorite_puis_echeance(client: TestClient) -> None:
    asset_id = _create_asset(client)
    low = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Faible",
            "priority": "low",
            "recurrence_type": "custom_date",
            "custom_due_date": "2026-01-01",
        },
    ).json()
    critical_late = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Urgente tardive",
            "priority": "critical",
            "recurrence_type": "custom_date",
            "custom_due_date": "2026-06-01",
        },
    ).json()
    critical_early = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Urgente proche",
            "priority": "critical",
            "recurrence_type": "custom_date",
            "custom_due_date": "2026-03-01",
        },
    ).json()

    ordered = [row["id"] for row in client.get("/api/tasks").json()]
    assert ordered == [critical_early["id"], critical_late["id"], low["id"]]


def test_assignation_notification_indisponible_ne_bloque_pas(client: TestClient) -> None:
    """`notify_assignee` est best-effort : HA injoignable ne doit jamais faire
    echouer la creation/edition de l'entretien (pas de SUPERVISOR_TOKEN en test)."""
    asset_id = _create_asset(client)
    member = client.post(
        "/api/members", json={"name": "Alice", "ha_notify_service": "mobile_app_alice"}
    ).json()
    client.patch("/api/homes/current", json={"task_notifications_enabled": True})

    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Nettoyer la gouttiere", "assignee_id": member["id"]},
    )
    assert response.status_code == 201
