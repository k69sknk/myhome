"""Prestataires : les entreprises et artisans qui interviennent (adr/0011)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..catalog import load_trades
from ..clock import utc_now_iso
from ..db import get_session
from ..models import Intervention, MaintenanceTask, Provider
from ..schemas import ProviderIn, ProviderOut, ProviderPatch, TradeOut
from ..services.home import ensure_home

router = APIRouter(tags=["prestataires"])


def _provider_out(row: Provider) -> ProviderOut:
    return ProviderOut(
        id=row.id,
        name=row.name,
        specialty=row.specialty,
        phone=row.phone,
        email=row.email,
        website=row.website,
        address=row.address,
        customer_ref=row.customer_ref,
        notes=row.notes,
    )


def _provider_or_404(session: Session, provider_id: int) -> Provider:
    row = session.get(Provider, provider_id)
    if row is None:
        raise HTTPException(404, "Prestataire introuvable")
    return row


@router.get("/trades", response_model=list[TradeOut])
def list_trades() -> list[TradeOut]:
    # Contenu statique livre avec l'application : ni base, ni session (adr/0008).
    return [TradeOut(slug=trade.slug, label=trade.label) for trade in load_trades()]


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(session: Session = Depends(get_session)) -> list[ProviderOut]:
    home = ensure_home(session)
    rows = session.scalars(
        select(Provider).where(Provider.home_id == home.id).order_by(Provider.name)
    ).all()
    return [_provider_out(row) for row in rows]


@router.post("/providers", response_model=ProviderOut, status_code=201)
def create_provider(body: ProviderIn, session: Session = Depends(get_session)) -> ProviderOut:
    home = ensure_home(session)
    now = utc_now_iso()
    row = Provider(
        home_id=home.id,
        name=body.name.strip(),
        specialty=body.specialty,
        phone=body.phone,
        email=body.email,
        website=body.website,
        address=body.address,
        customer_ref=body.customer_ref,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _provider_out(row)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def patch_provider(
    provider_id: int, body: ProviderPatch, session: Session = Depends(get_session)
) -> ProviderOut:
    row = _provider_or_404(session, provider_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and isinstance(data["name"], str):
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = utc_now_iso()
    session.flush()
    return _provider_out(row)


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    row = _provider_or_404(session, provider_id)
    # Le ON DELETE SET NULL de schema.sql ne vaut que pour les installations
    # neuves : les colonnes ajoutees par la migration 0012 n'ont pas pu emporter
    # leur clause REFERENCES. On coupe donc les liens ici, sur les deux schemas a
    # la fois. L'historique garde son texte : `performed_by` reste rempli, et
    # l'entretien realise ne perd pas son auteur (meme parti qu'en 0011).
    session.execute(
        update(Intervention)
        .where(Intervention.performed_by_provider_id == provider_id)
        .values(performed_by_provider_id=None)
    )
    session.execute(
        update(MaintenanceTask)
        .where(MaintenanceTask.assignee_provider_id == provider_id)
        .values(assignee_provider_id=None)
    )
    session.delete(row)
    session.flush()
    return {"ok": True}
