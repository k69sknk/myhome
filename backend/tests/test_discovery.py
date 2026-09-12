"""L'annonce de l'add-on au Supervisor (adr/0014).

Elle repare un defaut discret : `config.yaml` declarait la decouverte depuis
l'origine, `config_flow.py` savait la recevoir, mais rien ne l'emettait.
L'integration retombait donc sur la saisie manuelle, avec un nom d'hote par
defaut qui ne pouvait pas etre juste — le prefixe du slug est un hash du depot
d'origine, inconnu de l'integration.
"""

import httpx
import pytest

from mabarak_api.services import discovery


@pytest.fixture
def superviseur(monkeypatch):
    """Un Supervisor en toc, qui note ce qu'on lui envoie."""
    monkeypatch.setenv("SUPERVISOR_TOKEN", "jeton-de-test")
    monkeypatch.setenv("MABARAK_SUPERVISOR_URL", "http://supervisor")
    recu: dict = {}

    def transport(requete: httpx.Request) -> httpx.Response:
        recu["auth"] = requete.headers.get("Authorization")
        if requete.url.path == "/addons/self/info":
            return httpx.Response(200, json={"data": {"hostname": "1f2e3d4c-mabarak"}})
        if requete.url.path == "/discovery":
            import json

            recu["corps"] = json.loads(requete.content)
            return httpx.Response(200, json={"result": "ok"})
        return httpx.Response(404)

    vrai_client = httpx.Client

    def client_mocke(*args, **kwargs):
        return vrai_client(transport=httpx.MockTransport(transport))

    monkeypatch.setattr(discovery.httpx, "Client", client_mocke)
    return recu


def test_annonce_le_nom_d_hote_donne_par_le_superviseur(superviseur):
    """Le point crucial : l'hote vient du Supervisor, il n'est jamais devine."""
    assert discovery.annoncer_au_superviseur(8099) == "1f2e3d4c-mabarak"
    assert superviseur["corps"] == {
        "service": "mabarak",
        "config": {"host": "1f2e3d4c-mabarak", "port": 8099},
    }
    assert superviseur["auth"] == "Bearer jeton-de-test"


def test_le_service_annonce_est_celui_declare_dans_config_yaml():
    """Une divergence ici rendrait l'annonce muette : le Supervisor ne relaie
    que les services declares par l'add-on."""
    from pathlib import Path

    import yaml

    config = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "addon" / "mabarak" / "config.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert discovery.SERVICE in config["discovery"]


def test_le_port_annonce_est_celui_de_nginx():
    """L'integration joint nginx, pas uvicorn : annoncer 8000 la ferait echouer."""
    from pathlib import Path

    from mabarak_api.config import INGRESS_PORT

    nginx = (
        Path(__file__).resolve().parents[2]
        / "addon"
        / "mabarak"
        / "rootfs"
        / "etc"
        / "nginx"
        / "nginx.conf"
    ).read_text(encoding="utf-8")
    assert f"listen {INGRESS_PORT}" in nginx


def test_hors_add_on_l_annonce_est_silencieuse(monkeypatch):
    """En developpement il n'y a pas de Supervisor : ce n'est pas une panne."""
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    assert discovery.annoncer_au_superviseur(8099) is None


def test_un_superviseur_en_panne_n_empeche_pas_le_demarrage(monkeypatch):
    """L'interface fonctionne sans integration : un echec d'annonce ne doit pas
    faire tomber l'add-on."""
    monkeypatch.setenv("SUPERVISOR_TOKEN", "jeton-de-test")

    def transport(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    vrai_client = httpx.Client
    monkeypatch.setattr(
        discovery.httpx,
        "Client",
        lambda *a, **k: vrai_client(transport=httpx.MockTransport(transport)),
    )
    assert discovery.annoncer_au_superviseur(8099) is None


def test_un_superviseur_sans_nom_d_hote_est_refuse(monkeypatch):
    """Plutot que d'annoncer un hote vide, on n'annonce rien."""
    monkeypatch.setenv("SUPERVISOR_TOKEN", "jeton-de-test")

    def transport(requete: httpx.Request) -> httpx.Response:
        if requete.url.path == "/addons/self/info":
            return httpx.Response(200, json={"data": {}})
        raise AssertionError("le message de decouverte n'aurait pas du etre envoye")

    vrai_client = httpx.Client
    monkeypatch.setattr(
        discovery.httpx,
        "Client",
        lambda *a, **k: vrai_client(transport=httpx.MockTransport(transport)),
    )
    assert discovery.annoncer_au_superviseur(8099) is None
