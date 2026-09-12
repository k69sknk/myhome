"""Rattacher un document depuis un agent (adr/0015).

L'essentiel de ce fichier porte sur le refus : MaBarak ne telecharge que depuis
le reseau local, et c'est cette regle qui empeche la route de devenir un moyen
de faire sortir des donnees de la maison — ou d'aller chercher n'importe quoi
sur Internet au nom de l'add-on.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from mabarak_api.services import fetch
from mabarak_api.services.fetch import TelechargementRefuseError, verifier_source


def creer_equipement(client: TestClient, nom: str) -> None:
    assert client.post("/api/agent/equipements", json={"nom": nom}).status_code == 201


# --- Le garde-fou ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.10/facture.pdf",
        "http://10.0.0.5:8080/notice.pdf",
        "http://172.16.4.4/garantie.pdf",
        "http://127.0.0.1:9000/facture.pdf",
    ],
)
def test_les_adresses_privees_passent(url):
    verifier_source(url)


def test_une_adresse_publique_est_refusee():
    """La regle qui tient tout le reste : sans elle, l'add-on irait chercher
    n'importe quoi sur Internet."""
    with pytest.raises(TelechargementRefuseError) as erreur:
        verifier_source("http://93.184.216.34/facture.pdf")
    # Le message doit proposer l'alternative, pas seulement refuser.
    assert "lien" in erreur.value.args[0]


def test_un_nom_qui_resout_en_public_est_refuse(monkeypatch):
    """Un nom d'hote n'est pas une adresse : c'est la resolution qui decide."""
    import ipaddress

    monkeypatch.setattr(fetch, "_adresses", lambda hote: [ipaddress.ip_address("93.184.216.34")])
    with pytest.raises(TelechargementRefuseError):
        verifier_source("http://cortex.exemple.fr/facture.pdf")


def test_un_nom_a_deux_adresses_dont_une_publique_est_refuse(monkeypatch):
    """On verifie TOUTES les adresses resolues, pas la premiere : sinon l'ordre
    de resolution suffirait a contourner la regle."""
    import ipaddress

    monkeypatch.setattr(
        fetch,
        "_adresses",
        lambda hote: [ipaddress.ip_address("192.168.1.10"), ipaddress.ip_address("93.184.216.34")],
    )
    with pytest.raises(TelechargementRefuseError):
        verifier_source("http://ambigu.local/facture.pdf")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://192.168.1.10/x.pdf", "pas-une-url"])
def test_les_autres_protocoles_sont_refuses(url):
    with pytest.raises(TelechargementRefuseError):
        verifier_source(url)


# --- Telechargement -------------------------------------------------------------


@pytest.fixture
def serveur(monkeypatch):
    """Un serveur de fichiers en toc, sur une adresse privee."""
    etat: dict = {"contenu": b"%PDF-1.4 facture", "entetes": {}, "code": 200}

    def transport(requete: httpx.Request) -> httpx.Response:
        if etat["code"] >= 300 and etat["code"] < 400:
            return httpx.Response(etat["code"], headers={"location": "http://ailleurs/x.pdf"})
        return httpx.Response(etat["code"], content=etat["contenu"], headers=etat["entetes"])

    vrai_client = httpx.Client
    monkeypatch.setattr(
        fetch.httpx,
        "Client",
        lambda **k: vrai_client(transport=httpx.MockTransport(transport), **k),
    )
    return etat


def test_un_fichier_local_est_copie_dans_mabarak(client: TestClient, serveur):
    creer_equipement(client, "Chaudiere")
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "chaudiere",
            "nom": "Facture revision 2026",
            "type": "facture",
            "fichier_a_telecharger": "http://192.168.1.10:8080/facture.pdf",
        },
    )
    assert reponse.status_code == 201, reponse.text
    assert "copie dans MaBarak" in reponse.json()["message"]

    document = client.get("/api/documents").json()[0]
    assert document["storage_mode"] == "local_file"
    assert document["doc_type"] == "invoice"
    assert document["file_size"] == len(b"%PDF-1.4 facture")

    # Et il se retelecharge vraiment : la chaine entiere tient, pas seulement la
    # ligne en base.
    fichier = client.get(f"/api/documents/{document['id']}/file")
    assert fichier.status_code == 200
    assert fichier.content == b"%PDF-1.4 facture"


def test_un_fichier_trop_gros_est_refuse(client: TestClient, serveur):
    creer_equipement(client, "Chaudiere")
    serveur["contenu"] = b"x" * (11 * 1024 * 1024)
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "chaudiere",
            "nom": "Scan enorme",
            "fichier_a_telecharger": "http://192.168.1.10/scan.pdf",
        },
    )
    assert reponse.status_code == 422
    assert "lien" in reponse.json()["detail"]


def test_une_redirection_est_refusee(client: TestClient, serveur):
    """Une redirection peut sortir du reseau local apres la verification."""
    creer_equipement(client, "Chaudiere")
    serveur["code"] = 302
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "chaudiere",
            "nom": "Facture",
            "fichier_a_telecharger": "http://192.168.1.10/facture.pdf",
        },
    )
    assert reponse.status_code == 422
    assert "redirige" in reponse.json()["detail"]


def test_une_extension_inconnue_est_refusee(client: TestClient, serveur):
    creer_equipement(client, "Chaudiere")
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "chaudiere",
            "nom": "Archive",
            "fichier_a_telecharger": "http://192.168.1.10/facture.zip",
        },
    )
    assert reponse.status_code == 422
    assert ".pdf" in reponse.json()["detail"]


def test_le_nom_transmis_par_le_serveur_donne_l_extension(client: TestClient, serveur):
    """Une adresse sans extension reste exploitable si le serveur nomme le fichier."""
    creer_equipement(client, "Chaudiere")
    serveur["entetes"] = {"content-disposition": 'attachment; filename="facture-2026.pdf"'}
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "chaudiere",
            "nom": "Facture",
            "fichier_a_telecharger": "http://192.168.1.10/telecharger?id=42",
        },
    )
    assert reponse.status_code == 201, reponse.text


# --- Les deux autres modes ------------------------------------------------------


def test_un_lien_est_garde_tel_quel(client: TestClient):
    """Le mode qui vaut pour un document qui vit ailleurs : aucune copie."""
    creer_equipement(client, "Spa")
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "Spa",
            "nom": "Notice constructeur",
            "type": "notice",
            "lien": "https://exemple.fr/notice.pdf",
        },
    )
    assert reponse.status_code == 201
    assert "garde comme lien" in reponse.json()["message"]

    document = client.get("/api/documents").json()[0]
    assert document["storage_mode"] == "external_link"
    assert document["url"] == "https://exemple.fr/notice.pdf"


def test_une_note_suffit_quand_le_papier_est_dans_un_classeur(client: TestClient):
    creer_equipement(client, "Spa")
    reponse = client.post(
        "/api/agent/documents",
        json={
            "equipement": "Spa",
            "nom": "Facture d'achat",
            "type": "facture",
            "note": "Classeur bleu, intercalaire 3",
        },
    )
    assert reponse.status_code == 201
    document = client.get("/api/documents").json()[0]
    assert document["storage_mode"] == "reference_note"
    assert document["reference_note"] == "Classeur bleu, intercalaire 3"


@pytest.mark.parametrize(
    "corps",
    [
        {},
        {"lien": "https://x.fr/a.pdf", "note": "Classeur"},
        {"fichier_a_telecharger": "http://192.168.1.1/a.pdf", "lien": "https://x.fr/a.pdf"},
    ],
)
def test_il_faut_exactement_un_mode(client: TestClient, corps):
    """Ni zero ni deux : le mode de stockage n'est pas un detail (adr/0002)."""
    creer_equipement(client, "Spa")
    reponse = client.post("/api/agent/documents", json={"equipement": "Spa", "nom": "X", **corps})
    assert reponse.status_code == 422


def test_un_equipement_ambigu_n_ecrit_rien(client: TestClient):
    creer_equipement(client, "Chaudiere gaz")
    creer_equipement(client, "Chaudiere bois")
    reponse = client.post(
        "/api/agent/documents",
        json={"equipement": "chaudiere", "nom": "Facture", "note": "Classeur"},
    )
    assert reponse.status_code == 409
    assert client.get("/api/documents").json() == []
