"""Tests du contrat consomme par l'integration Home Assistant.

Ce contrat doit rester stable entre une version d'add-on et une version
d'integration installees separement (ADR-0005). Ces tests fixent sa forme sur
une base vide : le contenu metier est couvert dans `test_metier.py`.
"""

from fastapi.testclient import TestClient

from mabarak_api.config import API_SCHEMA_VERSION


def test_summary_expose_la_version_du_contrat(client: TestClient) -> None:
    payload = client.get("/api/ha/summary").json()

    assert payload["api_schema_version"] == API_SCHEMA_VERSION


def test_summary_expose_tous_les_compteurs_de_statut(client: TestClient) -> None:
    """Les quatre statuts doivent toujours etre presents, meme a zero : sinon le
    coordinator devrait deviner les valeurs manquantes."""
    counts = client.get("/api/ha/summary").json()["counts"]

    assert set(counts) == {"overdue", "due_soon", "ok", "unscheduled"}
    assert all(value == 0 for value in counts.values())


def test_summary_a_la_forme_attendue_sans_donnees(client: TestClient) -> None:
    payload = client.get("/api/ha/summary").json()

    assert payload["next_task"] is None
    assert payload["assets"] == []
    assert payload["warranties_expiring"] == []
    assert payload["upcoming_tasks"] == []
    assert payload["generated_at"]


def test_le_resume_porte_de_quoi_repondre_sans_autre_appel(client) -> None:
    """Les attributs du capteur par equipement viennent d'ici.

    Un connecteur qui ne sait que lire un etat Home Assistant doit pouvoir
    repondre « quand la VMC a-t-elle ete entretenue, et quand revient-elle ? »
    sans appeler de service : tous ne savent pas en demander la reponse
    (adr/0013).
    """
    client.post("/api/locations", json={"name": "Combles"})
    lieu = client.get("/api/locations").json()[0]["id"]
    client.post(
        "/api/assets",
        json={"name": "VMC", "location_id": lieu, "brand": "Aldes", "model": "EasyHOME"},
    )
    asset = client.get("/api/assets").json()[0]["id"]
    client.post(
        f"/api/assets/{asset}/tasks",
        json={
            "name": "Nettoyer les bouches",
            "recurrence_type": "months",
            "recurrence_interval": 6,
            "last_completed_on": "2026-03-01",
        },
    )

    fiche = next(a for a in client.get("/api/ha/summary").json()["assets"] if a["name"] == "VMC")

    assert fiche["location"] == "Combles"
    assert fiche["brand"] == "Aldes"
    assert fiche["model"] == "EasyHOME"
    assert fiche["last_maintenance_on"] == "2026-03-01"
    assert fiche["next_due_on"] == "2026-09-01"

    entretien = fiche["tasks"][0]
    assert entretien["name"] == "Nettoyer les bouches"
    assert entretien["last_done"] == "2026-03-01"
    # La frequence en francais, pour etre relue telle quelle par un agent.
    assert entretien["frequency"] == "tous les 6 mois"


def test_un_equipement_sans_entretien_ne_ment_pas(client) -> None:
    """Aucune date inventee : `null` se lit « on ne sait pas », ce qui est vrai."""
    client.post("/api/assets", json={"name": "Spa"})
    fiche = next(a for a in client.get("/api/ha/summary").json()["assets"] if a["name"] == "Spa")

    assert fiche["status"] == "unscheduled"
    assert fiche["last_maintenance_on"] is None
    assert fiche["next_due_on"] is None
    assert fiche["tasks"] == []


def test_la_fiche_retient_la_date_la_plus_proche_et_le_dernier_passage(client) -> None:
    """Avec plusieurs entretiens, ce sont ces deux dates-la qu'on cherche."""
    client.post("/api/assets", json={"name": "Chaudiere"})
    asset = client.get("/api/assets").json()[0]["id"]
    for nom, derniere in (("Ramonage", "2026-01-10"), ("Revision", "2026-04-20")):
        client.post(
            f"/api/assets/{asset}/tasks",
            json={
                "name": nom,
                "recurrence_type": "years",
                "recurrence_interval": 1,
                "last_completed_on": derniere,
            },
        )

    fiche = next(
        a for a in client.get("/api/ha/summary").json()["assets"] if a["name"] == "Chaudiere"
    )
    assert fiche["last_maintenance_on"] == "2026-04-20"
    assert fiche["next_due_on"] == "2027-01-10"
    assert len(fiche["tasks"]) == 2
