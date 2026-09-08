"""Maison unique, lieux et categories."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import utc_now_iso
from ..db import get_session
from ..models import Asset, Category, Home, Location
from ..schemas import (
    CategoryOut,
    HomeOut,
    HomePatch,
    LocationIn,
    LocationOut,
    LocationPatch,
)
from ..services.catalog import location_path, would_create_cycle
from ..services.home import ensure_home

router = APIRouter(tags=["maison"])


def _home(session: Session) -> Home:
    return ensure_home(session)


@router.get("/homes/current", response_model=HomeOut)
def read_home(session: Session = Depends(get_session)) -> HomeOut:
    home = _home(session)
    return HomeOut.model_validate(home, from_attributes=True)


@router.patch("/homes/current", response_model=HomeOut)
def patch_home(body: HomePatch, session: Session = Depends(get_session)) -> HomeOut:
    home = _home(session)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(home, key, value)
    home.updated_at = utc_now_iso()
    session.flush()
    return HomeOut.model_validate(home, from_attributes=True)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_session)) -> list[CategoryOut]:
    rows = session.scalars(
        select(Category).where(Category.is_hidden == 0).order_by(Category.sort_order, Category.name)
    ).all()
    return [
        CategoryOut(
            id=row.id,
            parent_id=row.parent_id,
            name=row.name,
            slug=row.slug,
            icon=row.icon,
            is_builtin=bool(row.is_builtin),
            sort_order=row.sort_order,
        )
        for row in rows
    ]


@router.get("/locations", response_model=list[LocationOut])
def list_locations(session: Session = Depends(get_session)) -> list[LocationOut]:
    home = _home(session)
    rows = session.scalars(
        select(Location)
        .where(Location.home_id == home.id)
        .order_by(Location.sort_order, Location.name)
    ).all()
    counts: dict[int | None, int] = dict(
        session.execute(
            select(Asset.location_id, func.count())
            .where(Asset.location_id.is_not(None))
            .group_by(Asset.location_id)
        ).tuples()
    )
    return [
        LocationOut(
            id=row.id,
            name=row.name,
            parent_id=row.parent_id,
            location_type=row.location_type,
            sort_order=row.sort_order,
            notes=row.notes,
            path=location_path(session, row.id) or row.name,
            asset_count=int(counts.get(row.id, 0)),
        )
        for row in rows
    ]


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(body: LocationIn, session: Session = Depends(get_session)) -> LocationOut:
    home = _home(session)
    if body.parent_id is not None:
        parent = session.get(Location, body.parent_id)
        if parent is None or parent.home_id != home.id:
            raise HTTPException(404, "Lieu parent introuvable")
    now = utc_now_iso()
    row = Location(
        home_id=home.id,
        parent_id=body.parent_id,
        name=body.name.strip(),
        location_type=body.location_type,
        sort_order=body.sort_order,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return LocationOut(
        id=row.id,
        name=row.name,
        parent_id=row.parent_id,
        location_type=row.location_type,
        sort_order=row.sort_order,
        notes=row.notes,
        path=location_path(session, row.id) or row.name,
        asset_count=0,
    )


@router.patch("/locations/{location_id}", response_model=LocationOut)
def patch_location(
    location_id: int, body: LocationPatch, session: Session = Depends(get_session)
) -> LocationOut:
    home = _home(session)
    row = session.get(Location, location_id)
    if row is None or row.home_id != home.id:
        raise HTTPException(404, "Lieu introuvable")
    data = body.model_dump(exclude_unset=True)
    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id == row.id:
            raise HTTPException(422, "Un lieu ne peut pas etre son propre parent")
        if parent_id is not None:
            parent = session.get(Location, parent_id)
            if parent is None or parent.home_id != home.id:
                raise HTTPException(404, "Lieu parent introuvable")
            if would_create_cycle(session, row.id, parent_id):
                raise HTTPException(422, "Ce rattachement creerait un cycle")
    for key, value in data.items():
        setattr(row, key, value.strip() if key == "name" and isinstance(value, str) else value)
    row.updated_at = utc_now_iso()
    session.flush()
    count = (
        session.scalar(select(func.count()).select_from(Asset).where(Asset.location_id == row.id))
        or 0
    )
    return LocationOut(
        id=row.id,
        name=row.name,
        parent_id=row.parent_id,
        location_type=row.location_type,
        sort_order=row.sort_order,
        notes=row.notes,
        path=location_path(session, row.id) or row.name,
        asset_count=count,
    )


@router.delete("/locations/{location_id}")
def delete_location(location_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    home = _home(session)
    row = session.get(Location, location_id)
    if row is None or row.home_id != home.id:
        raise HTTPException(404, "Lieu introuvable")
    child = session.scalars(select(Location).where(Location.parent_id == row.id).limit(1)).first()
    if child is not None:
        raise HTTPException(409, "Deplacez ou supprimez d'abord les lieux enfants")
    used = session.scalars(select(Asset).where(Asset.location_id == row.id).limit(1)).first()
    if used is not None:
        raise HTTPException(409, "Deplacez d'abord les equipements de ce lieu")
    session.delete(row)
    return {"ok": True}
