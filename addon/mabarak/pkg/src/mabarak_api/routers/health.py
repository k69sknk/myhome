"""Point de sante de l'API, lu par l'integration Home Assistant."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import API_SCHEMA_VERSION, APP_NAME

router = APIRouter(tags=["systeme"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str
    # Lu par le coordinator de l'integration pour detecter une version d'add-on
    # incompatible (ADR-0005).
    api_schema_version: int


@router.get("/health", response_model=HealthResponse, summary="Etat de l'API")
def health() -> HealthResponse:
    from .. import __version__

    return HealthResponse(
        status="ok",
        app=APP_NAME,
        version=__version__,
        api_schema_version=API_SCHEMA_VERSION,
    )
