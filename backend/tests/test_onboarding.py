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


def _selection(client: TestClient, key: str, **overrides: object) -> dict:
    """Reprend la fiche pre-remplie du catalogue, comme le fait l'ecran de recap."""
    for proposal in client.get("/api/catalog/proposals").json():
        if proposal["maintenance"]["key"] == key:
            return {
                "key": key,
                "asset_id": proposal["asset_id"],
                "task": {**proposal["draft"], **overrides},
            }
    raise AssertionError(f"proposition absente : {key}")


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
    premiere = concernees[0]
    client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "key": "bouche_extraction_nettoyage",
                    "asset_id": premiere["asset_id"],
                    "task": premiere["draft"],
                }
            ]
        },
    )
    restantes = [
        p
        for p in client.get("/api/catalog/proposals").json()
        if p["maintenance"]["key"] == "bouche_extraction_nettoyage"
    ]
    assert len(restantes) == 1
    assert restantes[0]["asset_id"] == concernees[1]["asset_id"]


def test_creer_les_entretiens_remplit_le_planning(client: TestClient) -> None:
    _apply_room(client, "cuisine", ["hotte"])

    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                _selection(client, "hotte_filtre_graisse"),
                _selection(client, "maison_detecteurs_fumee"),
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
    _apply_room(client, "sejour", ["poele"])

    client.post(
        "/api/catalog/maintenances",
        json={"selections": [_selection(client, "poele_ramonage")]},
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
    _apply_room(client, "cuisine", ["hotte"])

    client.post(
        "/api/catalog/maintenances",
        json={"selections": [_selection(client, "hotte_filtre_graisse", recurrence_interval=1)]},
    )

    tache = client.get("/api/tasks").json()[0]
    assert tache["recurrence_interval"] == 1


def test_une_fiche_entierement_modifiee_est_creee_telle_quelle(client: TestClient) -> None:
    """Le crayon du recapitulatif laisse tout modifier, pas seulement la frequence."""
    _apply_room(client, "cuisine", ["hotte"])

    client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                _selection(
                    client,
                    "hotte_filtre_graisse",
                    name="Nettoyer la hotte a fond",
                    priority="high",
                    notes="Bac a graisse compris",
                    preparation_notes="Prevoir du degraissant",
                )
            ]
        },
    )

    tache = client.get("/api/tasks").json()[0]
    assert tache["name"] == "Nettoyer la hotte a fond"
    assert tache["priority"] == "high"
    assert tache["notes"] == "Bac a graisse compris"
    assert tache["preparation_notes"] == "Prevoir du degraissant"


def test_un_entretien_ajoute_de_toutes_pieces_est_cree(client: TestClient) -> None:
    """Le bouton + du recapitulatif : aucun modele de catalogue derriere."""
    created = _apply_room(client, "cuisine", ["hotte"])
    asset_id = created["created"][0]["id"]

    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "asset_id": asset_id,
                    "task": {
                        "name": "Changer l'ampoule de la hotte",
                        "recurrence_type": "months",
                        "recurrence_interval": 24,
                    },
                }
            ]
        },
    )

    assert response.status_code == 201, response.text
    tache = client.get("/api/tasks").json()[0]
    assert tache["name"] == "Changer l'ampoule de la hotte"
    assert tache["next_due_on"]


def test_un_entretien_inconnu_est_refuse(client: TestClient) -> None:
    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "key": "laver_le_dragon",
                    "task": {
                        "name": "Laver le dragon",
                        "recurrence_type": "months",
                        "recurrence_interval": 1,
                    },
                }
            ]
        },
    )

    assert response.status_code == 404


def test_relancer_le_tour_adopte_les_lieux_crees_a_la_main(client: TestClient) -> None:
    """Une maison deja remplie n'a pas de cle de catalogue sur ses lieux.

    Sans adoption par le nom, le tour creait une deuxieme « Cuisine » a cote de
    celle saisie a la main. La contrainte UNIQUE (home_id, parent_id, name) ne
    protege pas : sous SQLite deux NULL sont distincts, donc elle ne s'applique
    pas aux lieux de premier niveau, dont le parent est NULL.
    """
    existante = client.post("/api/locations", json={"name": "Cuisine"}).json()

    body = _apply_room(client, "cuisine", ["refrigerateur"])

    assert body["location_id"] == existante["id"]
    assert len(client.get("/api/locations").json()) == 1


def test_relancer_le_tour_ne_duplique_pas_une_fiche_saisie_a_la_main(client: TestClient) -> None:
    existante = client.post("/api/locations", json={"name": "Cuisine"}).json()
    client.post("/api/assets", json={"name": "Réfrigérateur", "location_id": existante["id"]})

    _apply_room(client, "cuisine", ["refrigerateur", "four"])

    noms = [asset["name"] for asset in client.get("/api/assets").json()]
    assert sorted(noms) == ["Four", "Réfrigérateur"]


def test_relancer_le_tour_propose_les_entretiens_des_fiches_deja_saisies(
    client: TestClient,
) -> None:
    """Le coeur de l'interet du bouton « refaire le tour ».

    Une fiche creee a la main n'a pas de cle de catalogue. Si le tour se contente
    de l'ignorer, il ne propose rien a une maison deja remplie. Il l'adopte donc,
    et ses entretiens types deviennent proposables.
    """
    lieu = client.post("/api/locations", json={"name": "Cuisine"}).json()
    client.post("/api/assets", json={"name": "Réfrigérateur", "location_id": lieu["id"]})

    _apply_room(client, "cuisine", ["refrigerateur"])

    proposals = client.get("/api/catalog/proposals").json()
    pour_le_frigo = [p for p in proposals if p["asset_name"] == "Réfrigérateur"]
    assert {p["maintenance"]["key"] for p in pour_le_frigo} == {
        "refrigerateur_degivrage",
        "refrigerateur_grille",
    }


def test_un_objet_present_dans_plusieurs_zones_est_distingue_par_son_lieu(
    client: TestClient,
) -> None:
    """Les volets existent dans quatre zones du catalogue.

    Sans le lieu, l'ecran de recapitulatif empilait quatre fois le meme libelle
    sous une seule carte « Volets », sans rien pour les distinguer.
    """
    _apply_room(client, "cuisine", ["volets"])
    _apply_room(client, "sejour", ["volets"])

    proposals = client.get("/api/catalog/proposals").json()
    volets = [p for p in proposals if p["maintenance"]["key"] == "volets_entretien"]

    assert len(volets) == 2
    assert {p["location_path"] for p in volets} == {"Cuisine", "Séjour"}
    # Deux fiches distinctes : le regroupement cote interface se fait dessus.
    assert len({p["asset_id"] for p in volets}) == 2


def test_l_etat_de_la_maison_signale_zones_et_objets_deja_presents(client: TestClient) -> None:
    _apply_room(client, "cuisine", ["refrigerateur", "hotte"])

    etat = {row["room_key"]: row for row in client.get("/api/catalog/state").json()}

    assert etat["cuisine"]["location_name"] == "Cuisine"
    assert set(etat["cuisine"]["present_items"]) == {"refrigerateur", "hotte"}
    # Une zone jamais visitee reste vide, sans lieu rattache.
    assert etat["garage"]["location_id"] is None
    assert etat["garage"]["present_items"] == []


def test_l_etat_reconnait_aussi_ce_qui_a_ete_saisi_a_la_main(client: TestClient) -> None:
    """Meme regle que la creation : cle de catalogue d'abord, nom en repli.

    Sans cela, une maison remplie a la main s'afficherait entierement vide.
    """
    lieu = client.post("/api/locations", json={"name": "Cuisine"}).json()
    client.post("/api/assets", json={"name": "Réfrigérateur", "location_id": lieu["id"]})

    etat = {row["room_key"]: row for row in client.get("/api/catalog/state").json()}

    assert etat["cuisine"]["location_id"] == lieu["id"]
    assert etat["cuisine"]["present_items"] == ["refrigerateur"]


def test_poser_des_objets_du_catalogue_dans_une_zone_personnalisee(client: TestClient) -> None:
    """Le catalogue ne couvre pas l'atelier, mais ses objets doivent pouvoir y aller."""
    atelier = client.post("/api/locations", json={"name": "Atelier"}).json()

    response = client.post(
        "/api/catalog/rooms",
        json={"location_id": atelier["id"], "item_keys": ["tableau_electrique"]},
    )

    assert response.status_code == 201, response.text
    assert response.json()["location_name"] == "Atelier"
    # La fiche garde sa cle de catalogue, donc ses entretiens seront proposes.
    proposals = client.get("/api/catalog/proposals").json()
    assert any(p["maintenance"]["key"] == "tableau_electrique_differentiels" for p in proposals)


def test_il_faut_choisir_entre_zone_du_catalogue_et_lieu(client: TestClient) -> None:
    response = client.post("/api/catalog/rooms", json={"item_keys": []})

    assert response.status_code == 422
