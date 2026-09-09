"""Parcours metier : maison, lieux, fiche, entretien, synthese HA."""

from io import BytesIO

from fastapi.testclient import TestClient


def test_maison_est_creee_au_demarrage(client: TestClient) -> None:
    home = client.get("/api/homes/current").json()
    assert home["name"] == "Ma maison"
    assert home["due_soon_threshold_days"] == 30


def test_lieux_arbre_et_fiche_equipement(client: TestClient) -> None:
    types = {row["slug"]: row["id"] for row in client.get("/api/location-types").json()}
    garage = client.post(
        "/api/locations", json={"name": "Garage", "location_type_id": types["technical"]}
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


def test_entretien_mensuel_sans_dernier_a_une_prochaine_date(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "VMC"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres", "recurrence_type": "months", "recurrence_interval": 3},
    ).json()
    assert task["next_due_on"] is not None
    assert task["status"] in {"ok", "due_soon"}


def test_supprimer_un_lieu_occupe_est_refuse(client: TestClient) -> None:
    location = client.post("/api/locations", json={"name": "Atelier"}).json()
    client.post("/api/assets", json={"name": "Perceuse", "location_id": location["id"]})
    response = client.delete(f"/api/locations/{location['id']}")
    assert response.status_code == 409


def test_ha_devices_sans_supervisor_renvoie_503(client: TestClient) -> None:
    response = client.get("/api/ha/devices")
    assert response.status_code == 503


def test_lister_les_lieux_avec_equipements_ne_plante_pas(client: TestClient) -> None:
    """Non-regression : dict(session.execute(...).tuples()) plantait avec
    'TypeError: ... object is not subscriptable' des que la requete de
    comptage renvoyait un Result SQLAlchemy (dict() le traite comme un
    mapping car il expose .keys())."""
    garage = client.post("/api/locations", json={"name": "Garage"}).json()
    vide = client.post("/api/locations", json={"name": "Grenier"}).json()
    client.post("/api/assets", json={"name": "Perceuse", "location_id": garage["id"]})
    client.post("/api/assets", json={"name": "Etabli", "location_id": garage["id"]})

    response = client.get("/api/locations")
    assert response.status_code == 200
    par_id = {row["id"]: row["asset_count"] for row in response.json()}
    assert par_id[garage["id"]] == 2
    assert par_id[vide["id"]] == 0


def test_deplacer_un_lieu_sous_son_propre_descendant_est_refuse(client: TestClient) -> None:
    rdc = client.post("/api/locations", json={"name": "RDC"}).json()
    cuisine = client.post("/api/locations", json={"name": "Cuisine", "parent_id": rdc["id"]}).json()

    response = client.patch(f"/api/locations/{rdc['id']}", json={"parent_id": cuisine["id"]})
    assert response.status_code == 422

    response = client.patch(f"/api/locations/{rdc['id']}", json={"parent_id": rdc["id"]})
    assert response.status_code == 422


def test_deplacer_un_lieu_vers_un_nouveau_parent(client: TestClient) -> None:
    rdc = client.post("/api/locations", json={"name": "RDC"}).json()
    etage = client.post("/api/locations", json={"name": "Etage"}).json()
    cuisine = client.post("/api/locations", json={"name": "Cuisine", "parent_id": rdc["id"]}).json()

    response = client.patch(f"/api/locations/{cuisine['id']}", json={"parent_id": etage["id"]})
    assert response.status_code == 200
    assert response.json()["path"] == "Etage > Cuisine"


def test_types_de_lieux_crud(client: TestClient) -> None:
    types = client.get("/api/location-types").json()
    assert {row["slug"] for row in types} == {
        "room",
        "floor",
        "zone",
        "building",
        "outdoor",
        "technical",
    }
    assert all(row["is_builtin"] for row in types)

    created = client.post("/api/location-types", json={"name": "Combles"})
    assert created.status_code == 201
    combles = created.json()
    assert combles["slug"] == "combles"
    assert combles["is_builtin"] is False

    renamed = client.patch(f"/api/location-types/{combles['id']}", json={"name": "Sous les toits"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Sous les toits"

    room_id = next(row["id"] for row in types if row["slug"] == "room")
    refused = client.delete(f"/api/location-types/{room_id}")
    assert refused.status_code == 409

    unused = client.delete(f"/api/location-types/{combles['id']}")
    assert unused.status_code == 200


def test_creer_une_categorie_a_la_volee(client: TestClient) -> None:
    created = client.post("/api/categories", json={"name": "Domotique"})
    assert created.status_code == 201
    category = created.json()
    assert category["slug"] == "domotique"
    assert category["is_builtin"] is False
    assert category["parent_id"] is None

    categories = client.get("/api/categories").json()
    assert any(row["id"] == category["id"] for row in categories)

    asset = client.post(
        "/api/assets", json={"name": "Hub Zigbee", "category_id": category["id"]}
    ).json()
    assert asset["category_name"] == "Domotique"


def test_supprimer_un_type_de_lieu_utilise_est_refuse(client: TestClient) -> None:
    created = client.post("/api/location-types", json={"name": "Cave"})
    cave = created.json()
    client.post("/api/locations", json={"name": "Cave a vin", "location_type_id": cave["id"]})

    response = client.delete(f"/api/location-types/{cave['id']}")
    assert response.status_code == 409


def test_completer_un_entretien_avec_montant_et_facture(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Revision annuelle", "recurrence_type": "months", "recurrence_interval": 12},
    ).json()

    completed = client.post(
        f"/api/tasks/{task['id']}/complete",
        json={
            "performed_on": "2026-03-01",
            "performed_by": "Dupont Chauffage",
            "amount_cents": 15000,
        },
    ).json()
    intervention_id = completed["last_intervention_id"]
    assert intervention_id is not None

    uploaded = client.post(
        f"/api/interventions/{intervention_id}/documents",
        files={"file": ("facture.pdf", BytesIO(b"%PDF-1.4 fake invoice"), "application/pdf")},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["name"] == "facture.pdf"

    history = client.get(f"/api/tasks/{task['id']}/interventions").json()
    assert len(history) == 1
    entry = history[0]
    assert entry["performed_by"] == "Dupont Chauffage"
    assert entry["cost"]["amount_cents"] == 15000
    assert entry["documents"][0]["name"] == "facture.pdf"

    downloaded = client.get(f"/api/documents/{document['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 fake invoice"


def test_upload_document_type_refuse(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "VMC"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres", "recurrence_type": "months", "recurrence_interval": 3},
    ).json()
    completed = client.post(f"/api/tasks/{task['id']}/complete", json={}).json()

    response = client.post(
        f"/api/interventions/{completed['last_intervention_id']}/documents",
        files={"file": ("virus.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_photo_equipement_remplace_la_precedente(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "Lave-linge"}).json()["id"]

    first = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"doc_type": "photo"},
        files={"file": ("avant.jpg", BytesIO(b"fake-jpg-1"), "image/jpeg")},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    asset = client.get(f"/api/assets/{asset_id}").json()
    assert asset["photo_document_id"] == first_id
    listed = client.get("/api/assets").json()
    assert next(row for row in listed if row["id"] == asset_id)["photo_document_id"] == first_id

    second = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"doc_type": "photo"},
        files={"file": ("apres.jpg", BytesIO(b"fake-jpg-2"), "image/jpeg")},
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    asset = client.get(f"/api/assets/{asset_id}").json()
    assert asset["photo_document_id"] == second_id
    downloaded = client.get(f"/api/documents/{second_id}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-jpg-2"


def test_manuel_equipement_upload_liste_et_suppression(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"]

    uploaded = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"doc_type": "manual"},
        files={"file": ("notice.pdf", BytesIO(b"%PDF-1.4 notice"), "application/pdf")},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["doc_type"] == "manual"

    documents = client.get(f"/api/assets/{asset_id}/documents").json()
    assert [row["id"] for row in documents] == [document["id"]]

    downloaded = client.get(f"/api/documents/{document['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.4 notice"

    deleted = client.delete(f"/api/documents/{document['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get(f"/api/assets/{asset_id}/documents").json() == []
    assert client.get(f"/api/documents/{document['id']}/file").status_code == 404


def test_upload_document_equipement_type_refuse(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "VMC"}).json()["id"]
    response = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"doc_type": "manual"},
        files={"file": ("virus.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_suppression_entretien(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Revision", "recurrence_type": "months", "recurrence_interval": 12},
    ).json()

    deleted = client.delete(f"/api/tasks/{task['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    assert all(row["id"] != task["id"] for row in client.get("/api/tasks").json())
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404


def test_suppression_intervention_historique(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"]
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Revision", "recurrence_type": "months", "recurrence_interval": 12},
    ).json()
    completed = client.post(
        f"/api/tasks/{task['id']}/complete", json={"performed_on": "2026-03-01"}
    ).json()
    intervention_id = completed["last_intervention_id"]

    uploaded = client.post(
        f"/api/interventions/{intervention_id}/documents",
        files={"file": ("facture.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    document_id = uploaded.json()["id"]

    deleted = client.delete(f"/api/interventions/{intervention_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    assert client.get(f"/api/tasks/{task['id']}/interventions").json() == []
    assert client.get(f"/api/documents/{document_id}/file").status_code == 404
    assert client.delete(f"/api/interventions/{intervention_id}").status_code == 404
