"""La table `issue`, enfin ecrite et relue.

Elle existait dans schema.sql depuis l'origine — index, CHECK sur `resolved_on`,
place dans `v_asset_timeline` — sans aucun modele ni aucune route. Elle n'etait
citee que comme litteral dans `DocumentScope`, si bien qu'un document pouvait se
declarer rattache a un probleme qui ne pouvait pas exister.
"""

from fastapi.testclient import TestClient


def _asset(client: TestClient, nom: str = "VMC") -> int:
    return int(client.post("/api/assets", json={"name": nom}).json()["id"])


def _probleme(client: TestClient, asset_id: int, **champs: object) -> dict:
    response = client.post(
        f"/api/assets/{asset_id}/issues",
        json={"title": "La VMC fait beaucoup de bruit", **champs},
    )
    assert response.status_code == 201
    return dict(response.json())


def test_ouvrir_un_probleme(client: TestClient) -> None:
    asset_id = _asset(client)
    body = _probleme(client, asset_id, description="Sifflement continu depuis lundi")

    assert body["status"] == "open"
    assert body["severity"] == "normal"
    assert body["resolved_on"] is None
    assert body["opened_on"]


def test_resoudre_date_automatiquement_la_resolution(client: TestClient) -> None:
    """Le CHECK exige `resolved_on` renseigne si et seulement si resolu : laisser
    l'appelant s'en souvenir, c'est se garantir une IntegrityError un jour."""
    asset_id = _asset(client)
    issue = _probleme(client, asset_id)

    resolu = client.patch(
        f"/api/issues/{issue['id']}",
        json={"status": "resolved", "action_taken": "Nettoyage", "result": "Plus de bruit"},
    )
    assert resolu.status_code == 200
    assert resolu.json()["resolved_on"] is not None
    assert resolu.json()["action_taken"] == "Nettoyage"


def test_rouvrir_efface_la_date_de_resolution(client: TestClient) -> None:
    asset_id = _asset(client)
    issue = _probleme(client, asset_id)
    client.patch(f"/api/issues/{issue['id']}", json={"status": "resolved"})

    rouvert = client.patch(f"/api/issues/{issue['id']}", json={"status": "in_progress"})
    assert rouvert.status_code == 200
    assert rouvert.json()["resolved_on"] is None


def test_dater_la_resolution_d_un_probleme_ouvert_est_refuse(client: TestClient) -> None:
    asset_id = _asset(client)
    issue = _probleme(client, asset_id)

    response = client.patch(f"/api/issues/{issue['id']}", json={"resolved_on": "2026-01-01"})
    assert response.status_code == 422


def test_les_problemes_ouverts_passent_devant_les_resolus(client: TestClient) -> None:
    """Une fuite en cours ne doit pas se retrouver sous un probleme clos en 2019."""
    asset_id = _asset(client)
    vieux = _probleme(client, asset_id, title="Ancien", opened_on="2026-06-01")
    client.patch(f"/api/issues/{vieux['id']}", json={"status": "resolved"})
    _probleme(client, asset_id, title="En cours", opened_on="2019-01-01")

    titres = [row["title"] for row in client.get(f"/api/assets/{asset_id}/issues").json()]
    assert titres == ["En cours", "Ancien"]


def test_une_gravite_inconnue_est_refusee(client: TestClient) -> None:
    asset_id = _asset(client)
    response = client.post(
        f"/api/assets/{asset_id}/issues", json={"title": "x", "severity": "catastrophique"}
    )
    assert response.status_code == 422


def test_un_titre_vide_est_refuse(client: TestClient) -> None:
    asset_id = _asset(client)
    assert client.post(f"/api/assets/{asset_id}/issues", json={"title": "  "}).status_code == 422


def test_un_probleme_d_une_autre_fiche_reste_introuvable(client: TestClient) -> None:
    assert client.get("/api/assets/9999/issues").status_code == 404
    assert client.patch("/api/issues/9999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/issues/9999").status_code == 404


def test_supprimer_un_probleme(client: TestClient) -> None:
    asset_id = _asset(client)
    issue = _probleme(client, asset_id)

    assert client.delete(f"/api/issues/{issue['id']}").status_code == 200
    assert client.get(f"/api/assets/{asset_id}/issues").json() == []


def test_un_document_peut_enfin_se_rattacher_a_un_probleme(client: TestClient) -> None:
    """`DocumentScope` acceptait « issue » alors qu'aucun probleme ne pouvait
    exister : le rattachement etait declarable et jamais joignable."""
    asset_id = _asset(client)
    issue = _probleme(client, asset_id)

    created = client.post(
        f"/api/issues/{issue['id']}/documents",
        data={
            "storage_mode": "reference_note",
            "name": "Devis du plombier",
            "reference_note": "classeur bleu",
        },
    )
    assert created.status_code == 201

    documents = client.get("/api/documents").json()
    devis = next(row for row in documents if row["name"] == "Devis du plombier")
    assert devis["scope"] == "issue"
    assert [row["name"] for row in client.get(f"/api/issues/{issue['id']}/documents").json()] == [
        "Devis du plombier"
    ]


def test_supprimer_la_fiche_emporte_ses_problemes(client: TestClient) -> None:
    asset_id = _asset(client)
    _probleme(client, asset_id)

    assert client.delete(f"/api/assets/{asset_id}").status_code == 200
    assert client.get(f"/api/assets/{asset_id}/issues").status_code == 404


def test_le_probleme_apparait_dans_la_chronologie_de_la_fiche(client: TestClient) -> None:
    """`v_asset_timeline` lit `issue` depuis toujours ; la vue restait vide."""
    from sqlalchemy import text

    asset_id = _asset(client)
    issue = _probleme(client, asset_id, opened_on="2026-05-01")
    client.patch(f"/api/issues/{issue['id']}", json={"status": "resolved"})

    session = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        evenements = session.execute(
            text("SELECT event_type FROM v_asset_timeline WHERE asset_id = :a"),
            {"a": asset_id},
        ).scalars()
        assert {"issue_opened", "issue_resolved"} <= set(evenements)
    finally:
        session.close()
