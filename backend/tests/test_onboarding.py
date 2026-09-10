"""Didacticiel de demarrage : du catalogue vers de vraies lignes en base."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from mabarak_api.db import create_db_engine


def _apply_room(client: TestClient, room_key: str, item_keys: list[str]) -> dict:
    response = client.post(
        "/api/catalog/rooms", json={"room_key": room_key, "item_keys": item_keys}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cocher_une_zone_cree_le_lieu_et_les_fiches(client: TestClient) -> None:
    body = _apply_room(client, "cuisine", ["refrigerateur", "hotte"])

    assert body["location_name"] == "Cuisine"
    assert {asset["catalog_key"] for asset in body["created"]} == {"refrigerateur", "hotte"}

    assets = client.get("/api/assets").json()
    assert {asset["name"] for asset in assets} == {"Réfrigérateur", "Hotte aspirante"}
    # La categorie du catalogue a bien ete resolue en categorie reelle.
    assert all(asset["category_name"] for asset in assets)


def test_rejouer_une_zone_ne_cree_pas_de_doublon(client: TestClient) -> None:
    """Reprendre le didacticiel ou revenir en arriere ne doit rien dupliquer."""
    _apply_room(client, "cuisine", ["refrigerateur"])
    second = _apply_room(client, "cuisine", ["refrigerateur", "four"])

    assert [asset["catalog_key"] for asset in second["created"]] == ["four"]
    assert len(client.get("/api/assets").json()) == 2


def test_un_element_du_bati_sans_categorie_reste_sans_categorie(client: TestClient) -> None:
    """Aucune categorie ne couvre la plomberie : mieux vaut vide que faux."""
    _apply_room(client, "cuisine", ["evier_siphon"])

    element = client.get("/api/assets", params={"kind": "building_element"}).json()[0]
    assert element["name"] == "Évier (siphon)"
    assert element["category_name"] is None


def test_une_zone_inconnue_est_refusee(client: TestClient) -> None:
    response = client.post("/api/catalog/rooms", json={"room_key": "donjon", "item_keys": []})

    assert response.status_code == 404


def test_les_propositions_couvrent_les_fiches_creees_et_la_maison(client: TestClient) -> None:
    _apply_room(client, "cuisine", ["hotte"])

    proposals = client.get("/api/catalog/proposals").json()
    par_cle = {p["maintenance"]["key"]: p for p in proposals}

    assert par_cle["hotte_filtre_graisse"]["asset_name"] == "Hotte aspirante"
    # Les entretiens de la maison sont proposes sans fiche rattachee.
    assert par_cle["maison_detecteurs_fumee"]["asset_id"] is None


def test_un_meme_objet_dans_deux_zones_garde_ses_deux_entretiens(client: TestClient) -> None:
    """La bouche d'extraction existe en salle de bain et aux WC : deux fiches."""
    _apply_room(client, "salle_de_bain", ["bouche_extraction"])
    _apply_room(client, "wc", ["bouche_extraction"])

    proposals = client.get("/api/catalog/proposals").json()
    concernees = [p for p in proposals if p["maintenance"]["key"] == "bouche_extraction_nettoyage"]
    assert len(concernees) == 2

    # En creer un ne doit pas faire disparaitre l'autre de la liste.
    premiere = concernees[0]["asset_id"]
    client.post(
        "/api/catalog/maintenances",
        json={"selections": [{"key": "bouche_extraction_nettoyage", "asset_id": premiere}]},
    )
    restantes = [
        p
        for p in client.get("/api/catalog/proposals").json()
        if p["maintenance"]["key"] == "bouche_extraction_nettoyage"
    ]
    assert len(restantes) == 1
    assert restantes[0]["asset_id"] == concernees[1]["asset_id"]


def test_creer_les_entretiens_remplit_le_planning(client: TestClient) -> None:
    created = _apply_room(client, "cuisine", ["hotte"])
    asset_id = created["created"][0]["id"]

    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {"key": "hotte_filtre_graisse", "asset_id": asset_id},
                {"key": "maison_detecteurs_fumee"},
            ]
        },
    )

    assert response.status_code == 201
    assert response.json()["created"] == 2
    taches = client.get("/api/tasks").json()
    assert {t["name"] for t in taches} == {
        "Dégraisser le filtre métallique",
        "Tester les détecteurs de fumée",
    }
    # Chaque tache repart d'aujourd'hui : pas de rattrapage, pas d'echeance vide.
    assert all(t["next_due_on"] for t in taches)


def test_l_ancrage_du_catalogue_prime_sur_celui_deduit_du_type(
    client: TestClient, settings
) -> None:
    """Le ramonage est annuel ET reglementaire : il ne doit pas deriver (adr/0004).

    `hidden_anchor` rendrait 'from_completion' pour une recurrence annuelle ; seul
    le catalogue sait que celle-ci est ancree sur la date theorique. L'ancrage
    n'etant volontairement pas expose par l'API, on le verifie en base.
    """
    created = _apply_room(client, "sejour", ["poele"])
    asset_id = created["created"][0]["id"]

    client.post(
        "/api/catalog/maintenances",
        json={"selections": [{"key": "poele_ramonage", "asset_id": asset_id}]},
    )

    engine = create_db_engine(settings)
    with engine.connect() as connection:
        anchor = connection.execute(
            text(
                "SELECT recurrence_anchor FROM maintenance_task "
                "WHERE catalog_key = 'poele_ramonage'"
            )
        ).scalar_one()
    assert anchor == "from_due_date"


def test_une_frequence_ajustee_par_l_utilisateur_est_respectee(client: TestClient) -> None:
    created = _apply_room(client, "cuisine", ["hotte"])
    asset_id = created["created"][0]["id"]

    client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "key": "hotte_filtre_graisse",
                    "asset_id": asset_id,
                    "recurrence": {"type": "months", "interval": 1},
                }
            ]
        },
    )

    tache = client.get("/api/tasks").json()[0]
    assert tache["recurrence_interval"] == 1


def test_un_entretien_inconnu_est_refuse(client: TestClient) -> None:
    response = client.post(
        "/api/catalog/maintenances", json={"selections": [{"key": "laver_le_dragon"}]}
    )

    assert response.status_code == 404
