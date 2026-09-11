"""Maison unique, lieux et categories."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import utc_now_iso
from ..config import Settings
from ..db import get_app_settings, get_session
from ..models import Asset, Category, Document, Home, Location, LocationType
from ..schemas import (
    CategoryIn,
    CategoryOut,
    DocType,
    DocumentOut,
    HomeOut,
    HomePatch,
    LocationIn,
    LocationOut,
    LocationPatch,
    LocationTypeIn,
    LocationTypeOut,
    LocationTypePatch,
    StorageMode,
)
from ..services.catalog import (
    location_path,
    unique_category_slug,
    unique_location_type_slug,
    would_create_cycle,
)
from ..services.documents import UNSCOPED_DIR, contenu_a_la_creation, document_out
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


@router.post("/homes/current/documents", response_model=DocumentOut, status_code=201)
async def create_home_document(
    storage_mode: StorageMode = Form("local_file"),
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    reference_note: str | None = Form(None),
    doc_type: DocType = Form("other"),
    name: str | None = Form(None),
    notes: str | None = Form(None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentOut:
    """Les papiers de la maison elle-meme : acte, assurance, DPE, diagnostics.

    Ils ne relevent d'aucun appareil, et les ranger sur une fiche d'equipement
    serait leur faire perdre leur sens. Le schema prevoyait `home_id` depuis
    l'origine, rien ne l'ecrivait.
    """
    home = _home(session)
    contenu, label = await contenu_a_la_creation(
        settings,
        scope=UNSCOPED_DIR,
        storage_mode=storage_mode,
        file=file,
        url=url,
        reference_note=reference_note,
        name=name,
    )
    now = utc_now_iso()
    row = Document(
        home_id=home.id,
        name=label,
        doc_type=doc_type,
        notes=(notes or "").strip() or None,
        created_at=now,
        updated_at=now,
        **contenu,
    )
    session.add(row)
    session.flush()
    return document_out(row)


@router.get("/homes/current/documents", response_model=list[DocumentOut])
def list_home_documents(session: Session = Depends(get_session)) -> list[DocumentOut]:
    home = _home(session)
    rows = session.scalars(
        select(Document)
        .where(Document.home_id == home.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return [document_out(row) for row in rows]


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


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, session: Session = Depends(get_session)) -> CategoryOut:
    now = utc_now_iso()
    name = body.name.strip()
    row = Category(
        parent_id=None,
        name=name,
        slug=unique_category_slug(session, name),
        icon=None,
        is_builtin=0,
        is_hidden=0,
        sort_order=0,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return CategoryOut(
        id=row.id,
        parent_id=row.parent_id,
        name=row.name,
        slug=row.slug,
        icon=row.icon,
        is_builtin=False,
        sort_order=row.sort_order,
    )


def _default_location_type(session: Session) -> LocationType:
    row = session.scalar(select(LocationType).where(LocationType.slug == "room"))
    if row is None:
        row = session.scalars(select(LocationType).order_by(LocationType.sort_order)).first()
    if row is None:
        raise HTTPException(500, "Aucun type de lieu configure")
    return row


def _location_type_or_404(session: Session, location_type_id: int) -> LocationType:
    row = session.get(LocationType, location_type_id)
    if row is None:
        raise HTTPException(404, "Type de lieu introuvable")
    return row


def _location_out(session: Session, row: Location, asset_count: int) -> LocationOut:
    return LocationOut(
        id=row.id,
        name=row.name,
        parent_id=row.parent_id,
        location_type_id=row.location_type_id,
        location_type_name=row.location_type.name,
        sort_order=row.sort_order,
        notes=row.notes,
        path=location_path(session, row.id) or row.name,
        asset_count=asset_count,
    )


@router.get("/location-types", response_model=list[LocationTypeOut])
def list_location_types(session: Session = Depends(get_session)) -> list[LocationTypeOut]:
    rows = session.scalars(
        select(LocationType).order_by(LocationType.sort_order, LocationType.name)
    ).all()
    return [
        LocationTypeOut(
            id=row.id,
            slug=row.slug,
            name=row.name,
            is_builtin=bool(row.is_builtin),
            sort_order=row.sort_order,
        )
        for row in rows
    ]


@router.post("/location-types", response_model=LocationTypeOut, status_code=201)
def create_location_type(
    body: LocationTypeIn, session: Session = Depends(get_session)
) -> LocationTypeOut:
    now = utc_now_iso()
    name = body.name.strip()
    row = LocationType(
        slug=unique_location_type_slug(session, name),
        name=name,
        is_builtin=0,
        sort_order=0,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return LocationTypeOut(
        id=row.id, slug=row.slug, name=row.name, is_builtin=False, sort_order=row.sort_order
    )


@router.patch("/location-types/{location_type_id}", response_model=LocationTypeOut)
def patch_location_type(
    location_type_id: int, body: LocationTypePatch, session: Session = Depends(get_session)
) -> LocationTypeOut:
    row = _location_type_or_404(session, location_type_id)
    row.name = body.name.strip()
    row.updated_at = utc_now_iso()
    session.flush()
    return LocationTypeOut(
        id=row.id,
        slug=row.slug,
        name=row.name,
        is_builtin=bool(row.is_builtin),
        sort_order=row.sort_order,
    )


@router.delete("/location-types/{location_type_id}")
def delete_location_type(
    location_type_id: int, session: Session = Depends(get_session)
) -> dict[str, bool]:
    row = _location_type_or_404(session, location_type_id)
    if row.is_builtin:
        raise HTTPException(409, "Ce type integre ne peut pas etre supprime")
    used = session.scalars(
        select(Location).where(Location.location_type_id == row.id).limit(1)
    ).first()
    if used is not None:
        raise HTTPException(409, "Reaffectez d'abord les lieux utilisant ce type")
    session.delete(row)
    return {"ok": True}


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
        )
        .tuples()
        .all()
    )
    return [_location_out(session, row, int(counts.get(row.id, 0))) for row in rows]


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(body: LocationIn, session: Session = Depends(get_session)) -> LocationOut:
    home = _home(session)
    if body.parent_id is not None:
        parent = session.get(Location, body.parent_id)
        if parent is None or parent.home_id != home.id:
            raise HTTPException(404, "Lieu parent introuvable")
    location_type = (
        _location_type_or_404(session, body.location_type_id)
        if body.location_type_id is not None
        else _default_location_type(session)
    )
    now = utc_now_iso()
    row = Location(
        home_id=home.id,
        parent_id=body.parent_id,
        name=body.name.strip(),
        location_type_id=location_type.id,
        sort_order=body.sort_order,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _location_out(session, row, 0)


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
    if "location_type_id" in data:
        _location_type_or_404(session, data["location_type_id"])
    for key, value in data.items():
        setattr(row, key, value.strip() if key == "name" and isinstance(value, str) else value)
    row.updated_at = utc_now_iso()
    session.flush()
    count = (
        session.scalar(select(func.count()).select_from(Asset).where(Asset.location_id == row.id))
        or 0
    )
    return _location_out(session, row, count)


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
