"""`v_asset_timeline`, creee depuis l'origine et jamais interrogee.

`test_migrate.py` verifiait que la vue existe ; rien ne lisait son contenu. Elle
reunit ce que six tables savent chacune de leur cote — pose, interventions,
problemes, depenses autonomes, fin de garantie — en une seule histoire, et c'est
le SQL qui en fait foi (adr/0003).
"""

from fastapi.testclient import TestClient


def _fiche_complete(client: TestClient) -> int:
    asset_id = int(
        client.post(
            "/api/assets",
            json={
                "name": "Pompe a chaleur",
                "install_date": "2019-04-10",
                "warranty": {"start_date": "2019-04-10", "duration_months": 24},
            },
        ).json()["id"]
    )
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Entretien annuel", "recurrence_type": "years", "recurrence_interval": 1},
    ).json()
    client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-01", "notes": "Filtres changes", "amount_cents": 18000},
    )
    issue = client.post(
        f"/api/assets/{asset_id}/issues",
        json={"title": "Bruit a la mise en route", "opened_on": "2025-11-02"},
    ).json()
    client.patch(f"/api/issues/{issue['id']}", json={"status": "resolved"})
    client.post(
        f"/api/assets/{asset_id}/costs",
        json={"cost_type": "purchase", "amount_cents": 980000, "incurred_on": "2019-04-02"},
    )
    return asset_id


def test_la_chronologie_reunit_les_six_sources(client: TestClient) -> None:
    asset_id = _fiche_complete(client)

    lignes = client.get(f"/api/assets/{asset_id}/timeline").json()
    types = {ligne["event_type"] for ligne in lignes}

    assert "installation" in types
    assert "intervention" in types
    assert "issue_opened" in types
    assert "issue_resolved" in types
    assert "cost" in types, "le prix d'achat, qui ne pend a aucune intervention"
    assert "warranty_end" in types


def test_du_plus_recent_au_plus_ancien(client: TestClient) -> None:
    asset_id = _fiche_complete(client)

    dates = [
        ligne["occurred_on"] for ligne in client.get(f"/api/assets/{asset_id}/timeline").json()
    ]
    assert dates == sorted(dates, reverse=True)


def test_une_depense_nee_d_un_entretien_n_apparait_pas_deux_fois(client: TestClient) -> None:
    """La vue les exclut : la ligne d'intervention porte deja l'evenement."""
    asset_id = _fiche_complete(client)

    couts = [
        ligne
        for ligne in client.get(f"/api/assets/{asset_id}/timeline").json()
        if ligne["event_type"] == "cost"
    ]
    assert len(couts) == 1
    assert couts[0]["amount_cents"] == 980000


def test_une_fiche_neuve_a_une_chronologie_vide(client: TestClient) -> None:
    asset_id = int(client.post("/api/assets", json={"name": "Grille-pain"}).json()["id"])
    assert client.get(f"/api/assets/{asset_id}/timeline").json() == []


def test_les_lignes_sans_date_sont_ecartees(client: TestClient) -> None:
    """Une garantie sans fin, une fiche sans date de pose : `occurred_on` est
    alors NULL, et une ligne sans date n'a pas de place dans une chronologie."""
    asset_id = int(
        client.post(
            "/api/assets",
            json={"name": "Adoucisseur", "warranty": {"start_date": "2020-01-01"}},
        ).json()["id"]
    )

    lignes = client.get(f"/api/assets/{asset_id}/timeline").json()
    assert all(ligne["occurred_on"] for ligne in lignes)


def test_la_chronologie_d_une_fiche_inconnue(client: TestClient) -> None:
    assert client.get("/api/assets/9999/timeline").status_code == 404
