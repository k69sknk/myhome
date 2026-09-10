"""Le catalogue est du contenu livre : il doit casser la CI, jamais l'utilisateur."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from mabarak_api.catalog import Catalog, CatalogRecurrence, load_catalog
from mabarak_api.db import create_db_engine
from mabarak_api.migrate import upgrade_to_head


def test_le_catalogue_livre_est_valide() -> None:
    catalogue = load_catalog()

    assert catalogue.rooms
    assert catalogue.items
    assert catalogue.home_maintenances
    # Une piece sans objet ne sert a rien dans le didacticiel.
    assert all(room.items for room in catalogue.rooms)
    # Un objet sans entretien non plus : l'interet est de remplir le planning.
    assert all(item.maintenances for item in catalogue.items)


def test_les_categories_du_catalogue_existent_en_base(settings) -> None:
    """Un slug de categorie mal orthographie rangerait la fiche nulle part."""
    upgrade_to_head(settings)
    engine = create_db_engine(settings)
    with engine.connect() as connection:
        slugs = {row[0] for row in connection.execute(text("SELECT slug FROM category"))}

    used = {item.category for item in load_catalog().items if item.category is not None}
    assert used <= slugs


def test_les_types_de_lieu_du_catalogue_existent_en_base(settings) -> None:
    upgrade_to_head(settings)
    engine = create_db_engine(settings)
    with engine.connect() as connection:
        slugs = {row[0] for row in connection.execute(text("SELECT slug FROM location_type"))}

    used = {room.location_type for room in load_catalog().rooms}
    assert used <= slugs


def test_une_piece_qui_reference_un_objet_inconnu_est_refusee() -> None:
    with pytest.raises(ValidationError, match="objet inconnu"):
        Catalog(
            rooms=[{"key": "cuisine", "label": "Cuisine", "location_type": "room", "items": ["?"]}],
            items=[],
            home_maintenances=[],
        )


def test_une_cle_en_double_est_refusee() -> None:
    piece = {"key": "cuisine", "label": "Cuisine", "location_type": "room", "items": []}
    with pytest.raises(ValidationError, match="en double"):
        Catalog(rooms=[piece, piece], items=[], home_maintenances=[])


@pytest.mark.parametrize(
    "recurrence",
    [
        {"type": "annual_fixed", "month": 11},  # jour manquant
        {"type": "months"},  # intervalle manquant
        {"type": "months", "interval": 3, "month": 11},  # champs incompatibles
        {"type": "annual_fixed", "month": 11, "day": 15, "interval": 2},
    ],
)
def test_une_recurrence_incoherente_est_refusee(recurrence: dict[str, int | str]) -> None:
    """Meme regle que le CHECK de `maintenance_task`, verifiee au chargement."""
    with pytest.raises(ValidationError):
        CatalogRecurrence(**recurrence)  # type: ignore[arg-type]


def test_l_api_expose_le_catalogue(client: TestClient) -> None:
    response = client.get("/api/catalog")

    assert response.status_code == 200
    body = response.json()
    assert {room["key"] for room in body["rooms"]} == {r.key for r in load_catalog().rooms}
