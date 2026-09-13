"""Supprimer : un entretien de la maison, puis une fiche et tout ce qui pend apres elle.

Deux trous qui se ressemblaient. Le planning affichait depuis toujours les
entretiens rattaches a la maison — « purger les radiateurs » — mais les routes
par entretien exigeaient un `asset_id` et repondaient « Entretien introuvable »
sur une ligne pourtant visible a l'ecran. Et une fiche, une fois creee, ne
pouvait plus disparaitre : ni doublon, ni erreur de saisie, ni appareil vendu.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from mabarak_api.config import Settings


def _asset(client: TestClient, name: str = "Chaudiere") -> int:
    return int(client.post("/api/assets", json={"name": name}).json()["id"])


def _entretien_de_la_maison(client: TestClient, name: str = "Purger les radiateurs") -> int:
    """Un entretien sans equipement, comme le didacticiel en cree."""
    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "asset_id": None,
                    "task": {
                        "name": name,
                        "recurrence_type": "annual_fixed",
                        "fixed_month": 10,
                        "fixed_day": 1,
                    },
                }
            ]
        },
    )
    assert response.status_code == 201
    tasks = client.get("/api/tasks").json()
    return int(next(task for task in tasks if task["name"] == name)["id"])


# --- Entretiens de la maison -------------------------------------------------


def test_un_entretien_de_la_maison_apparait_sans_equipement(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)
    task = next(item for item in client.get("/api/tasks").json() if item["id"] == task_id)
    assert task["asset_id"] is None
    assert task["asset_name"] is None


def test_supprimer_un_entretien_de_la_maison(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)

    response = client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 200

    assert all(task["id"] != task_id for task in client.get("/api/tasks").json())


def test_modifier_un_entretien_de_la_maison(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)

    response = client.patch(f"/api/tasks/{task_id}", json={"notes": "Avant la remise en chauffe"})
    assert response.status_code == 200
    assert response.json()["notes"] == "Avant la remise en chauffe"
    assert response.json()["asset_name"] is None


def test_historique_dun_entretien_de_la_maison_est_vide_et_non_introuvable(
    client: TestClient,
) -> None:
    task_id = _entretien_de_la_maison(client)

    response = client.get(f"/api/tasks/{task_id}/interventions")
    assert response.status_code == 200
    assert response.json() == []


def test_valider_un_entretien_de_la_maison(client: TestClient) -> None:
    """La limite a saute avec la migration 0015 : `intervention.asset_id` accepte
    NULL, et l'intervention se rattache alors a la maison."""
    task_id = _entretien_de_la_maison(client)

    response = client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-10-01"})
    assert response.status_code == 200
    assert response.json()["last_completed_on"] == "2026-10-01"


def test_un_entretien_qui_nexiste_pas_reste_introuvable(client: TestClient) -> None:
    assert client.delete("/api/tasks/9999").status_code == 404
    assert client.patch("/api/tasks/9999", json={"notes": "x"}).status_code == 404


# --- Suppression d'une fiche -------------------------------------------------


def test_supprimer_une_fiche_emporte_entretiens_interventions_et_couts(
    client: TestClient,
) -> None:
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres", "recurrence_type": "months", "recurrence_interval": 3},
    ).json()
    client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-01", "amount_cents": 4500},
    )

    response = client.delete(f"/api/assets/{asset_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_tasks"] == 1
    assert body["deleted_interventions"] == 1

    assert client.get(f"/api/assets/{asset_id}").status_code == 404
    assert client.get("/api/tasks").json() == []
    assert client.get("/api/interventions").json() == []


def test_supprimer_une_fiche_efface_aussi_les_fichiers_sur_le_disque(
    client: TestClient, settings: Settings
) -> None:
    """`ON DELETE CASCADE` retire les lignes, pas les octets. Une facture laissee
    sous /data/documents/ repartirait dans chaque sauvegarde Home Assistant."""
    asset_id = _asset(client)
    created = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "local_file", "doc_type": "invoice", "name": "Facture"},
        files={"file": ("facture.pdf", b"%PDF-1.4 contenu", "application/pdf")},
    )
    assert created.status_code == 201

    fichiers = list((settings.documents_dir / str(asset_id)).glob("*.pdf"))
    assert len(fichiers) == 1
    chemin: Path = fichiers[0]

    response = client.delete(f"/api/assets/{asset_id}")
    assert response.status_code == 200
    assert response.json()["deleted_files"] == 1
    assert not chemin.exists()


def test_supprimer_une_fiche_laisse_les_documents_de_la_maison(
    client: TestClient, settings: Settings
) -> None:
    """Le nettoyage vise les documents de la fiche, pas le repertoire commun."""
    client.post(
        "/api/homes/current/documents",
        data={"storage_mode": "local_file", "doc_type": "other", "name": "Acte"},
        files={"file": ("acte.pdf", b"%PDF-1.4 acte", "application/pdf")},
    )
    asset_id = _asset(client)

    assert client.delete(f"/api/assets/{asset_id}").status_code == 200

    assert len(client.get("/api/homes/current/documents").json()) == 1
    assert len(list((settings.documents_dir / "divers").glob("*.pdf"))) == 1


def test_supprimer_une_fiche_qui_nexiste_pas(client: TestClient) -> None:
    assert client.delete("/api/assets/9999").status_code == 404


def test_retirer_une_fiche_la_garde_en_base_avec_son_historique(client: TestClient) -> None:
    """La sortie normale d'un equipement reste `status = 'removed'` : c'est ce que
    prevoit schema.sql, et c'est ce que l'interface propose en premier."""
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Filtres", "recurrence_type": "months", "recurrence_interval": 3},
    ).json()
    client.post(f"/api/tasks/{task['id']}/complete", json={"performed_on": "2026-03-01"})

    response = client.patch(f"/api/assets/{asset_id}", json={"status": "removed"})
    assert response.status_code == 200
    assert response.json()["status"] == "removed"

    # La fiche reste consultable, et son historique avec elle.
    assert client.get(f"/api/assets/{asset_id}").status_code == 200
    assert len(client.get("/api/interventions").json()) == 1
    # Mais ses entretiens quittent le planning.
    assert client.get("/api/tasks").json() == []
