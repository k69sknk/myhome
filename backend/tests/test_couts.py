"""Le total par equipement, promis par la section 18 et jamais rendu.

`cost.cost_type` prevoit sept natures de depense depuis l'origine. Une seule
etait jamais ecrite — `maintenance`, par la validation d'un entretien — et rien
n'additionnait quoi que ce soit. Le prix d'achat d'un appareil n'existait nulle
part, alors que la fiche promet de dire ce qu'il a coute.
"""

from fastapi.testclient import TestClient


def _asset(client: TestClient, **champs: object) -> int:
    return int(client.post("/api/assets", json={"name": "Chaudiere", **champs}).json()["id"])


def test_sans_depense_le_total_est_nul(client: TestClient) -> None:
    asset_id = _asset(client)
    body = client.get(f"/api/assets/{asset_id}/costs").json()
    assert body == {"total_cents": 0, "currency": "EUR", "items": []}


def test_le_total_additionne_achat_pose_et_entretiens(client: TestClient) -> None:
    asset_id = _asset(client)
    client.post(
        f"/api/assets/{asset_id}/costs",
        json={"cost_type": "purchase", "amount_cents": 320000, "incurred_on": "2019-04-02"},
    )
    client.post(
        f"/api/assets/{asset_id}/costs",
        json={"cost_type": "installation", "amount_cents": 85000, "incurred_on": "2019-04-10"},
    )
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Entretien annuel", "recurrence_type": "years", "recurrence_interval": 1},
    ).json()
    client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-01", "amount_cents": 18000},
    )

    body = client.get(f"/api/assets/{asset_id}/costs").json()
    assert body["total_cents"] == 320000 + 85000 + 18000
    assert len(body["items"]) == 3


def test_une_depense_nee_d_un_entretien_dit_de_quel_entretien(client: TestClient) -> None:
    """Sans le nom, une ligne « maintenance, 180 € » ne dit rien de son origine."""
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Ramonage", "recurrence_type": "years", "recurrence_interval": 1},
    ).json()
    client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-01", "amount_cents": 9000},
    )

    ligne = client.get(f"/api/assets/{asset_id}/costs").json()["items"][0]
    assert ligne["task_name"] == "Ramonage"
    assert ligne["intervention_id"] is not None


def test_le_prix_d_achat_se_date_de_l_achat_par_defaut(client: TestClient) -> None:
    """Dater de ce matin une facture de 2019 fausserait la chronologie."""
    asset_id = _asset(client, purchase_date="2019-04-02")

    ligne = client.post(
        f"/api/assets/{asset_id}/costs", json={"cost_type": "purchase", "amount_cents": 320000}
    ).json()
    assert ligne["incurred_on"] == "2019-04-02"


def test_les_depenses_sont_rendues_de_la_plus_recente_a_la_plus_ancienne(
    client: TestClient,
) -> None:
    asset_id = _asset(client)
    for date in ("2019-04-02", "2026-01-15", "2022-08-30"):
        client.post(
            f"/api/assets/{asset_id}/costs",
            json={"cost_type": "other", "amount_cents": 1000, "incurred_on": date},
        )

    dates = [
        item["incurred_on"] for item in client.get(f"/api/assets/{asset_id}/costs").json()["items"]
    ]
    assert dates == ["2026-01-15", "2022-08-30", "2019-04-02"]


def test_supprimer_une_depense_saisie_a_la_main(client: TestClient) -> None:
    asset_id = _asset(client)
    cost = client.post(
        f"/api/assets/{asset_id}/costs", json={"cost_type": "parts", "amount_cents": 4500}
    ).json()

    assert client.delete(f"/api/costs/{cost['id']}").status_code == 200
    assert client.get(f"/api/assets/{asset_id}/costs").json()["total_cents"] == 0


def test_une_depense_d_entretien_ne_se_supprime_pas_d_ici(client: TestClient) -> None:
    """La retirer laisserait une ligne d'historique annoncant un montant introuvable."""
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Ramonage", "recurrence_type": "years", "recurrence_interval": 1},
    ).json()
    client.post(
        f"/api/tasks/{task['id']}/complete",
        json={"performed_on": "2026-03-01", "amount_cents": 9000},
    )
    cost_id = client.get(f"/api/assets/{asset_id}/costs").json()["items"][0]["id"]

    response = client.delete(f"/api/costs/{cost_id}")
    assert response.status_code == 409
    assert "historique" in response.json()["detail"]


def test_un_montant_nul_ou_negatif_est_refuse(client: TestClient) -> None:
    asset_id = _asset(client)
    for montant in (0, -100):
        response = client.post(
            f"/api/assets/{asset_id}/costs", json={"cost_type": "other", "amount_cents": montant}
        )
        assert response.status_code == 422


def test_une_nature_de_depense_inconnue_est_refusee(client: TestClient) -> None:
    asset_id = _asset(client)
    response = client.post(
        f"/api/assets/{asset_id}/costs", json={"cost_type": "pourboire", "amount_cents": 500}
    )
    assert response.status_code == 422


def test_supprimer_la_fiche_emporte_ses_depenses(client: TestClient) -> None:
    asset_id = _asset(client)
    client.post(f"/api/assets/{asset_id}/costs", json={"cost_type": "purchase", "amount_cents": 1})

    assert client.delete(f"/api/assets/{asset_id}").status_code == 200
    assert client.get(f"/api/assets/{asset_id}/costs").status_code == 404
