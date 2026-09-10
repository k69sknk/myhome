"""Catalogue de demarrage, lu par le didacticiel « Configurer MaBarak »."""

from fastapi import APIRouter

from ..catalog import Catalog, load_catalog

router = APIRouter(tags=["catalogue"])


@router.get("/catalog", response_model=Catalog, summary="Catalogue de demarrage")
def catalog() -> Catalog:
    # Contenu statique livre avec l'application : ni base, ni session.
    return load_catalog()
