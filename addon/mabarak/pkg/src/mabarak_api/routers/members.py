"""Annuaire des membres (delegation d'entretiens)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..clock import utc_now_iso
from ..db import get_session
from ..models import Intervention, Member
from ..schemas import MemberIn, MemberOut, MemberPatch
from ..services.home import ensure_home

router = APIRouter(tags=["membres"])


def _member_out(row: Member) -> MemberOut:
    return MemberOut(
        id=row.id,
        name=row.name,
        member_type=row.member_type,  # type: ignore[arg-type]
        contact=row.contact,
        ha_person_entity_id=row.ha_person_entity_id,
        ha_notify_service=row.ha_notify_service,
    )


def _member_or_404(session: Session, member_id: int) -> Member:
    row = session.get(Member, member_id)
    if row is None:
        raise HTTPException(404, "Membre introuvable")
    return row


@router.get("/members", response_model=list[MemberOut])
def list_members(session: Session = Depends(get_session)) -> list[MemberOut]:
    home = ensure_home(session)
    rows = session.scalars(
        select(Member).where(Member.home_id == home.id).order_by(Member.name)
    ).all()
    return [_member_out(row) for row in rows]


@router.post("/members", response_model=MemberOut, status_code=201)
def create_member(body: MemberIn, session: Session = Depends(get_session)) -> MemberOut:
    home = ensure_home(session)
    now = utc_now_iso()
    row = Member(
        home_id=home.id,
        name=body.name.strip(),
        member_type=body.member_type,
        contact=body.contact,
        ha_person_entity_id=body.ha_person_entity_id,
        ha_notify_service=body.ha_notify_service,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _member_out(row)


@router.patch("/members/{member_id}", response_model=MemberOut)
def patch_member(
    member_id: int, body: MemberPatch, session: Session = Depends(get_session)
) -> MemberOut:
    row = _member_or_404(session, member_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and isinstance(data["name"], str):
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = utc_now_iso()
    session.flush()
    return _member_out(row)


@router.delete("/members/{member_id}")
def delete_member(member_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    row = _member_or_404(session, member_id)
    # Le ON DELETE SET NULL de schema.sql ne vaut que pour les installations
    # neuves : la colonne ajoutee par la migration 0011 n'a pas pu emporter sa
    # clause REFERENCES (SQLite ne sait pas l'ajouter apres coup). On coupe donc
    # le lien ici, sur les deux schemas a la fois. L'historique garde son texte :
    # `performed_by` reste rempli, l'entretien ne perd pas son auteur.
    session.execute(
        update(Intervention)
        .where(Intervention.performed_by_member_id == member_id)
        .values(performed_by_member_id=None)
    )
    session.delete(row)
    session.flush()
    return {"ok": True}
