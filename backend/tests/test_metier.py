"""Parcours metier : maison, lieux, fiche, entretien, synthese HA."""

from fastapi.testclient import TestClient


def test_maison_est_creee_au_demarrage(client: TestClient) -> None:
    home = client.get("/api/homes/current").json()
    assert home["name"] == "Ma maison"
    assert home["due_soon_threshold_days"] == 30


def test_lieux_arbre_et_fiche_equipement(client: TestClient) -> None:
    garage = client.post(
        "/api/locations", json={"name": "Garage", "location_type": "technical"}
    ).json()
    assert garage["path"] == "Garage"

    categories = client.get("/api/categories").json()
    heat_pump = next(row for row in categories if row["slug"] == "heat_pump")

    created = client.post(
        "/api/assets",
        json={
            "name": "Pompe a chaleur",
            "category_id": heat_pump["id"],
            "location_id": garage["id"],
            "brand": "Mitsubishi",
            "install_date": "2024-05-12",
            "warranty": {"start_date": "2024-05-12", "duration_months": 60},
        },
    )
    assert created.status_code == 201
    asset = created.json()
    assert asset["location_path"] == "Garage"
    assert asset["warranty"]["end_date"] == "2029-05-12"

    task = client.post(
        f"/api/assets/{asset['id']}/tasks",
        json={
            "name": "Entretien annuel",
            "recurrence_type": "annual_fixed",
            "fixed_month": 1,
            "fixed_day": 15,
            "last_completed_on": "2025-01-15",
        },
    ).json()
    assert task["next_due_on"] == "2026-01-15"

    done = client.post(
        f"/api/tasks/{task['id']}/complete", json={"performed_on": "2026-01-20"}
    ).json()
    assert done["last_completed_on"] == "2026-01-20"
    assert done["next_due_on"] == "2027-01-15"

    summary = client.get("/api/ha/summary").json()
    assert (
        summary["counts"]["ok"] + summary["counts"]["due_soon"] + summary["counts"]["overdue"] >= 1
    )
    assert summary["assets"][0]["name"] == "Pompe a chaleur"
    assert summary["next_task"] is not None
    assert summary["next_task"]["asset_id"] == asset["id"]
    assert summary["next_task"]["name"] == "Entretien annuel"


def test_fait_filtre_vmc_decale_depuis_la_realisation(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "VMC"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Filtres",
            "recurrence_type": "months",
            "recurrence_interval": 3,
            "last_completed_on": "2026-03-01",
        },
    ).json()
    done = client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-20"},
    ).json()
    assert done["next_due_on"] == "2026-06-20"


def test_supprimer_un_lieu_occupe_est_refuse(client: TestClient) -> None:
    location = client.post("/api/locations", json={"name": "Atelier"}).json()
    client.post("/api/assets", json={"name": "Perceuse", "location_id": location["id"]})
    response = client.delete(f"/api/locations/{location['id']}")
    assert response.status_code == 409


def test_ha_devices_sans_supervisor_renvoie_503(client: TestClient) -> None:
    response = client.get("/api/ha/devices")
    assert response.status_code == 503
