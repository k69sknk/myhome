"""Tests du squelette backend.

Ils ne couvrent volontairement aucune logique metier : il n'y en a pas encore.
Ils verifient ce que le squelette doit garantir, en particulier la resolution du
chemin d'ingress, qui est la source d'erreur la plus frequente sur les add-ons
Home Assistant.
"""

from fastapi.testclient import TestClient

from homekeeper_api.config import API_SCHEMA_VERSION
from homekeeper_api.ingress import INGRESS_HEADER, resolve_base_path


def test_health_repond_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "HomeKeeper"
    # L'integration s'appuie sur ce champ pour detecter un add-on incompatible.
    assert payload["api_schema_version"] == API_SCHEMA_VERSION


def test_openapi_est_sous_api(client: TestClient) -> None:
    """Tout doit vivre sous /api : nginx relaie le reste vers la coquille SPA."""
    assert client.get("/api/openapi.json").status_code == 200


class TestResolveBasePath:
    """L'en-tete X-Ingress-Path est controlable par le client si le port direct
    est ouvert : sa normalisation doit etre stricte."""

    def test_absente_retombe_sur_la_racine(self) -> None:
        assert resolve_base_path(None) == "/"
        assert resolve_base_path("") == "/"
        assert resolve_base_path("   ") == "/"

    def test_chemin_ingress_normalise_avec_slash_final(self) -> None:
        assert resolve_base_path("/api/hassio_ingress/abc123") == "/api/hassio_ingress/abc123/"

    def test_slash_final_deja_present_est_conserve(self) -> None:
        assert resolve_base_path("/api/hassio_ingress/abc123/") == "/api/hassio_ingress/abc123/"

    def test_slash_initial_ajoute(self) -> None:
        assert resolve_base_path("api/hassio_ingress/abc123") == "/api/hassio_ingress/abc123/"

    def test_injection_html_refusee(self) -> None:
        assert resolve_base_path('/x"><script>alert(1)</script>') == "/"

    def test_remontee_de_repertoire_refusee(self) -> None:
        assert resolve_base_path("/api/../../etc") == "/"


def test_index_injecte_le_chemin_ingress(client_avec_frontend: TestClient) -> None:
    response = client_avec_frontend.get("/", headers={INGRESS_HEADER: "/api/hassio_ingress/tok3n"})

    assert response.status_code == 200
    assert "/api/hassio_ingress/tok3n/" in response.text
    assert "__HOMEKEEPER_BASE__" not in response.text
    # La coquille porte un chemin d'ingress qui change a chaque instance.
    assert response.headers["cache-control"] == "no-store"


def test_index_sans_entete_utilise_la_racine(client_avec_frontend: TestClient) -> None:
    response = client_avec_frontend.get("/")

    assert response.status_code == 200
    assert '<base href="/">' in response.text


def test_routes_spa_servent_la_coquille(client_avec_frontend: TestClient) -> None:
    """Le routage cote client impose de renvoyer la coquille sur les chemins
    inconnus, sinon un rechargement de page produirait une 404."""
    response = client_avec_frontend.get("/equipements/7")

    assert response.status_code == 200
    assert "<html" in response.text
