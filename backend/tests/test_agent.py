"""La surface de pilotage par agent externe (adr/0013).

Ce qui est verifie ici n'est pas tant que les ecritures aboutissent — les
routes de l'interface le garantissent deja — que le contraire : qu'un nom
approximatif ne se resout JAMAIS en silence sur la mauvaise fiche.
"""

import pytest
from fastapi.testclient import TestClient

from mabarak_api.services.resolve import (
    AmbiguiteError,
    Candidat,
    IntrouvableError,
    resolve,
)


def creer_equipement(client: TestClient, nom: str, **extra: object) -> None:
    reponse = client.post("/api/agent/equipements", json={"nom": nom, **extra})
    assert reponse.status_code == 201, reponse.text


def creer_entretien(client: TestClient, equipement: str, nom: str, **freq: object) -> dict:
    reponse = client.post(
        "/api/agent/entretiens",
        json={"equipement": equipement, "nom": nom, "frequence": freq},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


# --- Resolution de noms -------------------------------------------------------


def test_les_accents_et_la_casse_ne_comptent_pas():
    candidats = [Candidat(id=1, nom="Chaudière gaz")]
    assert resolve("chaudiere GAZ", candidats, quoi="equipement").id == 1


def test_le_nom_exact_gagne_sur_un_nom_plus_long():
    """« Chaudiere » ne doit pas devenir ambigu parce qu'une autre fiche
    s'appelle « Chaudiere d'appoint » : l'egalite stricte tranche."""
    candidats = [Candidat(id=1, nom="Chaudiere"), Candidat(id=2, nom="Chaudiere d'appoint")]
    assert resolve("chaudiere", candidats, quoi="equipement").id == 1


def test_tous_les_mots_doivent_se_retrouver():
    candidats = [
        Candidat(id=1, nom="Changer le filtre de la PAC"),
        Candidat(id=2, nom="Changer le filtre du VMC"),
    ]
    assert resolve("filtre pac", candidats, quoi="entretien").id == 1


def test_une_requete_plus_bavarde_que_la_fiche():
    candidats = [Candidat(id=7, nom="Chaudiere gaz")]
    assert resolve("la chaudiere gaz de la cave", candidats, quoi="equipement").id == 7


def test_deux_correspondances_refusent_de_trancher():
    candidats = [
        Candidat(id=1, nom="Chaudiere gaz", precision="Cave"),
        Candidat(id=2, nom="Chaudiere d'appoint", precision="Garage"),
    ]
    with pytest.raises(AmbiguiteError) as erreur:
        resolve("chaudiere", candidats, quoi="equipement")
    # Le message doit nommer les deux candidats ET leur precision : c'est la
    # seule information avec laquelle un agent peut reformuler sa demande.
    assert "Chaudiere gaz (Cave)" in erreur.value.message
    assert "Chaudiere d'appoint (Garage)" in erreur.value.message
    assert len(erreur.value.candidats) == 2


def test_aucune_correspondance_enumere_ce_qui_existe():
    candidats = [Candidat(id=1, nom="Chaudiere"), Candidat(id=2, nom="VMC")]
    with pytest.raises(IntrouvableError) as erreur:
        resolve("aspirateur", candidats, quoi="equipement")
    assert "Chaudiere" in erreur.value.message and "VMC" in erreur.value.message


# --- Apercu -------------------------------------------------------------------


def test_apercu_donne_le_vocabulaire_de_la_maison(client: TestClient):
    """Sans la liste des lieux, un agent invente des noms de piece et echoue
    a la resolution suivante."""
    client.post("/api/locations", json={"name": "Cave"})
    creer_equipement(client, "Chaudiere", lieu="Cave")

    apercu = client.get("/api/agent/apercu").json()
    assert apercu["nombre_equipements"] == 1
    assert "Cave" in apercu["lieux"]
    assert apercu["compteurs"]["en_retard"] == 0


def test_apercu_compte_et_trie_les_retards(client: TestClient):
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", le="2020-01-01")

    apercu = client.get("/api/agent/apercu").json()
    assert apercu["compteurs"]["en_retard"] == 1
    assert apercu["en_retard"][0]["entretien"] == "Entretien annuel"
    assert apercu["en_retard"][0]["equipement"] == "Chaudiere"


# --- Creation -----------------------------------------------------------------


def test_creer_un_equipement_dans_un_lieu_existant(client: TestClient):
    client.post("/api/locations", json={"name": "Garage"})
    reponse = client.post(
        "/api/agent/equipements",
        json={"nom": "Tondeuse", "lieu": "garage", "marque": "Husqvarna"},
    )
    assert reponse.status_code == 201
    assert "Garage" in reponse.json()["message"]

    fiches = client.get("/api/agent/equipements").json()
    assert fiches[0]["lieu"] == "Garage"
    assert fiches[0]["marque"] == "Husqvarna"


def test_un_lieu_inconnu_est_refuse_par_defaut(client: TestClient):
    """Le garde-fou central de la creation : un agent qui se trompe de nom de
    piece creerait sinon un doublon silencieux dans l'arbre des lieux."""
    client.post("/api/locations", json={"name": "Garage"})
    reponse = client.post("/api/agent/equipements", json={"nom": "Tondeuse", "lieu": "Jardin"})
    assert reponse.status_code == 404
    assert "Garage" in reponse.json()["detail"]

    # Le lieu n'a pas ete cree au passage.
    assert [lieu["name"] for lieu in client.get("/api/locations").json()] == ["Garage"]


def test_un_lieu_inconnu_peut_etre_cree_si_c_est_voulu(client: TestClient):
    reponse = client.post(
        "/api/agent/equipements",
        json={"nom": "Tondeuse", "lieu": "Jardin", "creer_le_lieu": True},
    )
    assert reponse.status_code == 201
    assert [lieu["name"] for lieu in client.get("/api/locations").json()] == ["Jardin"]


def test_un_doublon_de_fiche_est_refuse(client: TestClient):
    creer_equipement(client, "Chaudiere")
    reponse = client.post("/api/agent/equipements", json={"nom": "Chaudiere"})
    assert reponse.status_code == 409
    assert "existe deja" in reponse.json()["detail"]


def test_la_garantie_est_calculee_a_la_creation(client: TestClient):
    creer_equipement(client, "Lave-linge", date_achat="2024-05-12", garantie_mois=60)
    fiche = client.get("/api/agent/equipements").json()[0]
    assert fiche["garantie_jusqu_au"] == "2029-05-12"


# --- Frequences ---------------------------------------------------------------


def test_tous_les_six_mois(client: TestClient):
    creer_equipement(client, "VMC")
    resultat = creer_entretien(client, "VMC", "Nettoyer les bouches", tous_les=6, unite="mois")
    assert "tous les 6 mois" in resultat["message"]


def test_chaque_annee_a_date_fixe(client: TestClient):
    creer_equipement(client, "Cheminee")
    resultat = creer_entretien(client, "Cheminee", "Ramonage", chaque_annee_le="15-09")
    assert "chaque annee le 15 septembre" in resultat["message"]


def test_une_saison_se_relit_en_francais(client: TestClient):
    creer_equipement(client, "Pelouse")
    resultat = creer_entretien(
        client,
        "Pelouse",
        "Tonte",
        tous_les=7,
        unite="jours",
        saison_du_mois=3,
        saison_au_mois=10,
    )
    assert "tous les 7 jours, de mars a octobre" in resultat["message"]


def test_deux_facons_de_dire_la_frequence_sont_refusees(client: TestClient):
    creer_equipement(client, "VMC")
    reponse = client.post(
        "/api/agent/entretiens",
        json={
            "equipement": "VMC",
            "nom": "Nettoyage",
            "frequence": {"tous_les": 6, "unite": "mois", "chaque_annee_le": "15-09"},
        },
    )
    assert reponse.status_code == 422


def test_un_nombre_sans_unite_est_refuse(client: TestClient):
    creer_equipement(client, "VMC")
    reponse = client.post(
        "/api/agent/entretiens",
        json={"equipement": "VMC", "nom": "Nettoyage", "frequence": {"tous_les": 6}},
    )
    assert reponse.status_code == 422


def test_un_entretien_du_meme_nom_est_refuse(client: TestClient):
    creer_equipement(client, "VMC")
    creer_entretien(client, "VMC", "Nettoyage", tous_les=6, unite="mois")
    reponse = client.post(
        "/api/agent/entretiens",
        json={
            "equipement": "VMC",
            "nom": "nettoyage",
            "frequence": {"tous_les": 3, "unite": "mois"},
        },
    )
    assert reponse.status_code == 409
    assert "deja un entretien" in reponse.json()["detail"]


# --- Validation d'un entretien ------------------------------------------------


def test_valider_replanifie_et_le_dit(client: TestClient):
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")

    reponse = client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "entretien annuel", "date": "2025-03-10"},
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["prochaine_echeance"] == "2026-03-10"
    assert "2026-03-10" in corps["message"]


def test_valider_sans_nommer_l_equipement(client: TestClient):
    """Le cas courant : « marque le ramonage comme fait », sans savoir a quelle
    fiche il est rattache."""
    creer_equipement(client, "Cheminee")
    creer_entretien(client, "Cheminee", "Ramonage", tous_les=1, unite="ans")

    reponse = client.post("/api/agent/entretiens/valider", json={"entretien": "ramonage"})
    assert reponse.status_code == 200
    assert reponse.json()["equipement"] == "Cheminee"


def test_un_entretien_homonyme_sur_deux_fiches_refuse_de_trancher(client: TestClient):
    """Le scenario qui justifie tout le module de resolution."""
    creer_equipement(client, "PAC")
    creer_equipement(client, "VMC")
    creer_entretien(client, "PAC", "Changer le filtre", tous_les=6, unite="mois")
    creer_entretien(client, "VMC", "Changer le filtre", tous_les=6, unite="mois")

    reponse = client.post("/api/agent/entretiens/valider", json={"entretien": "changer le filtre"})
    assert reponse.status_code == 409
    detail = reponse.json()["detail"]
    assert "PAC" in detail and "VMC" in detail

    # Et surtout : rien n'a ete ecrit.
    assert client.get("/api/interventions").json() == []


def test_l_equipement_leve_l_ambiguite(client: TestClient):
    creer_equipement(client, "PAC")
    creer_equipement(client, "VMC")
    creer_entretien(client, "PAC", "Changer le filtre", tous_les=6, unite="mois")
    creer_entretien(client, "VMC", "Changer le filtre", tous_les=6, unite="mois")

    reponse = client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "changer le filtre", "equipement": "PAC"},
    )
    assert reponse.status_code == 200
    assert reponse.json()["equipement"] == "PAC"


def test_un_entretien_inconnu_enumere_ceux_qui_existent(client: TestClient):
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")

    reponse = client.post("/api/agent/entretiens/valider", json={"entretien": "vidange"})
    assert reponse.status_code == 404
    assert "Entretien annuel" in reponse.json()["detail"]


def test_le_cout_est_enregistre_en_centimes(client: TestClient):
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")
    client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "entretien annuel", "montant_euros": 149.90},
    )
    historique = client.get("/api/interventions").json()
    assert historique[0]["cost"]["amount_cents"] == 14990


def test_un_prestataire_connu_est_rattache_a_sa_fiche(client: TestClient):
    """Sans ce rattachement, la meme entreprise s'ecrit de trois facons dans
    l'historique selon la dictee du jour."""
    client.post("/api/providers", json={"name": "Dupont Chauffage"})
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")

    client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "entretien annuel", "fait_par": "dupont chauffage"},
    )
    entree = client.get("/api/interventions").json()[0]
    assert entree["performed_by"] == "Dupont Chauffage"
    assert entree["performed_by_provider_id"] is not None


def test_un_intervenant_inconnu_reste_du_texte_libre(client: TestClient):
    """« le voisin » n'a pas de fiche et n'en merite pas : ce n'est pas un echec."""
    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")

    reponse = client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "entretien annuel", "fait_par": "le voisin"},
    )
    assert reponse.status_code == 200
    entree = client.get("/api/interventions").json()[0]
    assert entree["performed_by"] == "le voisin"
    assert entree["performed_by_provider_id"] is None


# --- Interventions ponctuelles ------------------------------------------------


def test_consigner_une_reparation(client: TestClient):
    creer_equipement(client, "Lave-linge")
    reponse = client.post(
        "/api/agent/interventions",
        json={
            "equipement": "lave-linge",
            "type": "reparation",
            "date": "2025-06-02",
            "notes": "Remplacement de la pompe",
            "montant_euros": 210,
        },
    )
    assert reponse.status_code == 201, reponse.text
    entree = client.get("/api/interventions").json()[0]
    assert entree["notes"] == "Remplacement de la pompe"
    assert entree["cost"]["amount_cents"] == 21000


# --- Provenance ---------------------------------------------------------------


def test_les_ecritures_de_l_agent_sont_tracees(client: TestClient, settings):
    """Six mois plus tard, devant une ligne fausse, c'est la premiere question."""
    import sqlite3

    creer_equipement(client, "Chaudiere")
    creer_entretien(client, "Chaudiere", "Entretien annuel", tous_les=1, unite="ans")
    client.post("/api/agent/entretiens/valider", json={"entretien": "entretien annuel"})

    base = sqlite3.connect(settings.data_dir / "mabarak.db")
    for table in ("asset", "maintenance_task", "intervention"):
        via = base.execute(f"SELECT created_via FROM {table}").fetchall()
        assert via == [("agent",)], f"{table} : {via}"

    # L'interface, elle, n'est pas marquee : NULL se lit « saisi par l'humain ».
    client.post("/api/assets", json={"name": "VMC"})
    assert base.execute("SELECT created_via FROM asset WHERE name='VMC'").fetchone() == (None,)
    base.close()


# --- Ce que l'agent relira a voix haute ---------------------------------------


@pytest.mark.parametrize(
    ("frequence", "attendu"),
    [
        ({"tous_les": 1, "unite": "ans"}, "tous les ans"),
        ({"tous_les": 1, "unite": "mois"}, "tous les mois"),
        ({"tous_les": 1, "unite": "jours"}, "tous les jours"),
        ({"tous_les": 2, "unite": "ans"}, "tous les 2 ans"),
        ({"tous_les": 6, "unite": "mois"}, "tous les 6 mois"),
        ({"chaque_annee_le": "01-11"}, "chaque annee le 1 novembre"),
    ],
)
def test_la_frequence_se_relit_sans_faute(client: TestClient, frequence, attendu):
    """« tous les an » se dit a l'oral et se lit mal : le pluriel est commande
    par « tous les », pas par l'intervalle."""
    creer_equipement(client, "Appareil")
    resultat = creer_entretien(client, "Appareil", "Verification", **frequence)
    assert attendu in resultat["message"]
