"""Catalogue de demarrage et application du didacticiel « Configurer MaBarak »."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..catalog import Catalog, CatalogMaintenance, CatalogRecurrence, load_catalog
from ..db import get_session
from ..services.home import ensure_home
from ..services.onboarding import (
    UnknownCatalogKeyError,
    apply_items_to_location,
    apply_maintenance,
    apply_room,
    house_state,
    pending_proposals,
)

router = APIRouter(tags=["catalogue"])


class ApplyRoomIn(BaseModel):
    # Une zone du catalogue, ou un lieu que l'utilisateur a cree lui-meme.
    room_key: str | None = None
    location_id: int | None = None
    item_keys: list[str] = Field(default_factory=list)


class CreatedAsset(BaseModel):
    id: int
    name: str
    catalog_key: str


class ApplyRoomOut(BaseModel):
    location_id: int
    location_name: str
    created: list[CreatedAsset]


class RoomStateOut(BaseModel):
    room_key: str
    location_id: int | None
    location_name: str | None
    present_items: list[str]


class ProposalOut(BaseModel):
    maintenance: CatalogMaintenance
    asset_id: int | None
    asset_name: str | None
    location_path: str | None


class MaintenanceSelection(BaseModel):
    key: str
    asset_id: int | None = None
    # Frequence ajustee par l'utilisateur dans l'ecran de recapitulatif.
    recurrence: CatalogRecurrence | None = None


class ApplyMaintenancesIn(BaseModel):
    selections: list[MaintenanceSelection] = Field(default_factory=list)


class ApplyMaintenancesOut(BaseModel):
    created: int


@router.get("/catalog", response_model=Catalog, summary="Catalogue de demarrage")
def catalog() -> Catalog:
    # Contenu statique livre avec l'application : ni base, ni session.
    return load_catalog()


@router.post("/catalog/rooms", response_model=ApplyRoomOut, status_code=201)
def apply_room_endpoint(body: ApplyRoomIn, session: Session = Depends(get_session)) -> ApplyRoomOut:
    """Cree une zone et les fiches cochees. Rejouable sans creer de doublon."""
    home = ensure_home(session)
    if (body.room_key is None) == (body.location_id is None):
        raise HTTPException(422, "renseignez soit 'room_key', soit 'location_id'")
    try:
        if body.room_key is not None:
            location, created = apply_room(session, home, body.room_key, body.item_keys)
        else:
            location, created = apply_items_to_location(
                session, home, body.location_id or 0, body.item_keys
            )
    except UnknownCatalogKeyError as error:
        raise HTTPException(404, str(error)) from error
    return ApplyRoomOut(
        location_id=location.id,
        location_name=location.name,
        created=[
            CreatedAsset(id=a.id, name=a.name, catalog_key=a.catalog_key or "") for a in created
        ],
    )


@router.get("/catalog/state", response_model=list[RoomStateOut])
def state(session: Session = Depends(get_session)) -> list[RoomStateOut]:
    """Ce qui est deja enregistre, zone par zone, pour un second passage."""
    home = ensure_home(session)
    return [
        RoomStateOut(
            room_key=row.room_key,
            location_id=row.location_id,
            location_name=row.location_name,
            present_items=row.present_items,
        )
        for row in house_state(session, home)
    ]


@router.get("/catalog/proposals", response_model=list[ProposalOut])
def proposals(session: Session = Depends(get_session)) -> list[ProposalOut]:
    """Entretiens types restant a proposer pour ce qui a deja ete cree."""
    home = ensure_home(session)
    return [
        ProposalOut(
            maintenance=proposal.maintenance,
            asset_id=proposal.asset_id,
            asset_name=proposal.asset_name,
            location_path=proposal.location_path,
        )
        for proposal in pending_proposals(session, home)
    ]


@router.post("/catalog/maintenances", response_model=ApplyMaintenancesOut, status_code=201)
def apply_maintenances_endpoint(
    body: ApplyMaintenancesIn, session: Session = Depends(get_session)
) -> ApplyMaintenancesOut:
    """Cree les entretiens retenus a la fin du didacticiel."""
    home = ensure_home(session)
    try:
        for selection in body.selections:
            apply_maintenance(
                session,
                home,
                key=selection.key,
                asset_id=selection.asset_id,
                recurrence_override=selection.recurrence,
            )
    except UnknownCatalogKeyError as error:
        raise HTTPException(404, str(error)) from error
    return ApplyMaintenancesOut(created=len(body.selections))
