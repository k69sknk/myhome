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
    assert payload["generated_at"]
