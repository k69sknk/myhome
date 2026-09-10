"""Fiches d'equipements et taches d'entretien."""

from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..clock import utc_now_iso, utc_today
from ..config import Settings
from ..db import get_app_settings, get_session
from ..ha_client import HaUnavailableError, list_ha_devices
from ..models import (
    Asset,
    Category,
    Cost,
    Document,
    HaLink,
    Home,
    Intervention,
    Location,
    MaintenanceTask,
    Member,
    ReplacementPart,
    TaskStatusRow,
    Warranty,
)
from ..schemas import (
    AssetIn,
    AssetListItem,
    AssetOut,
    AssetPatch,
    CompleteIn,
    CostOut,
    DocumentOut,
    HaDeviceOut,
    HaLinkIn,
    HaLinkOut,
    HistoryEntryOut,
    InterventionOut,
    ReplacementPartIn,
    ReplacementPartOut,
    TaskIn,
    TaskOut,
    TaskPatch,
    TaskStatus,
    WarrantyIn,
    WarrantyOut,
)
from ..services.catalog import (
    complete_task,
    location_path,
    plan_task,
    primary_ha_link,
    task_status_map,
    worst_status,
)
from ..services.home import ensure_home
from ..services.notifications import notify_assignee
from ..services.recurrence import RecurrenceType

router = APIRouter(tags=["equipements"])


def _home(session: Session) -> Home:
    return ensure_home(session)


def _get_asset(session: Session, asset_id: int) -> Asset:
    home = _home(session)
    asset = session.get(
        Asset,
        asset_id,
        options=(
            selectinload(Asset.tasks).selectinload(MaintenanceTask.replacement_parts),
            selectinload(Asset.tasks).selectinload(MaintenanceTask.assignee),
            selectinload(Asset.warranty),
            selectinload(Asset.ha_links),
            selectinload(Asset.category),
        ),
    )
    if asset is None or asset.home_id != home.id:
        raise HTTPException(404, "Equipement introuvable")
    return asset


def _warranty_out(row: Warranty | None) -> WarrantyOut | None:
    if row is None:
        return None
    return WarrantyOut(
        start_date=row.start_date,
        duration_months=row.duration_months,
        end_date=row.end_date,
        provider=row.provider,
        terms_url=row.terms_url,
        notes=row.notes,
    )


def _task_out(
    task: MaintenanceTask,
    status_row: TaskStatusRow | None,
    *,
    asset_name: str | None = None,
    loc_path: str | None = None,
    last_intervention_id: int | None = None,
) -> TaskOut:
    status: TaskStatus = "unscheduled"
    days: int | None = None
    if status_row is not None:
        status = status_row.status  # type: ignore[assignment]
        days = status_row.days_until_due
    return TaskOut(
        id=task.id,
        asset_id=task.asset_id,
        asset_name=asset_name,
        location_path=loc_path,
        name=task.name,
        priority=task.priority,  # type: ignore[arg-type]
        last_completed_on=task.last_completed_on,
        next_due_on=task.next_due_on,
        status=status,
        days_until_due=days,
        recurrence_type=task.recurrence_type,
        recurrence_interval=task.recurrence_interval,
        fixed_month=task.fixed_month,
        fixed_day=task.fixed_day,
        custom_due_date=task.custom_due_date,
        last_intervention_id=last_intervention_id,
        replacement_parts=[
            ReplacementPartOut(id=part.id, name=part.name, source=part.source)
            for part in task.replacement_parts
        ],
        preparation_notes=task.preparation_notes,
        notes=task.description,
        assignee_id=task.assignee_id,
        assignee_name=task.assignee.name if task.assignee is not None else None,
    )


def _photo_document_id(session: Session, asset_id: int) -> int | None:
    return session.scalars(
        select(Document.id).where(Document.asset_id == asset_id, Document.doc_type == "photo")
    ).first()


def _asset_out(session: Session, asset: Asset) -> AssetOut:
    statuses = task_status_map(session, [task.id for task in asset.tasks])
    link = primary_ha_link(asset)
    return AssetOut(
        id=asset.id,
        name=asset.name,
        kind=asset.kind,
        status=asset.status,
        category_id=asset.category_id,
        category_name=asset.category.name if asset.category is not None else None,
        category_slug=asset.category.slug if asset.category is not None else None,
        location_id=asset.location_id,
        location_path=location_path(session, asset.location_id),
        brand=asset.brand,
        model=asset.model,
        reference=asset.reference,
        serial_number=asset.serial_number,
        purchase_date=asset.purchase_date,
        install_date=asset.install_date,
        notes=asset.notes,
        warranty=_warranty_out(asset.warranty),
        photo_document_id=_photo_document_id(session, asset.id),
        ha_link=(
            HaLinkOut(
                ha_device_id=link.ha_device_id,
                name_at_link=link.name_at_link,
                entity_id_at_link=link.entity_id_at_link,
                resolution_status=link.resolution_status,
            )
            if link
            else None
        ),
        tasks=[_task_out(task, statuses.get(task.id)) for task in asset.tasks],
    )


def _upsert_warranty(session: Session, asset: Asset, body: WarrantyIn | None) -> None:
    if body is None:
        return
    now = utc_now_iso()
    if asset.warranty is None:
        asset.warranty = Warranty(
            asset_id=asset.id,
            start_date=body.start_date,
            duration_months=body.duration_months,
            provider=body.provider,
            terms_url=body.terms_url,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        session.add(asset.warranty)
    else:
        asset.warranty.start_date = body.start_date
        asset.warranty.duration_months = body.duration_months
        asset.warranty.provider = body.provider
        asset.warranty.terms_url = body.terms_url
        asset.warranty.notes = body.notes
        asset.warranty.updated_at = now


@router.get("/assets", response_model=list[AssetListItem])
def list_assets(
    kind: Literal["equipment", "building_element"] = "equipment",
    session: Session = Depends(get_session),
) -> list[AssetListItem]:
    home = _home(session)
    rows = session.scalars(
        select(Asset)
        .where(Asset.home_id == home.id, Asset.kind == kind, Asset.status != "removed")
        .options(
            selectinload(Asset.category), selectinload(Asset.tasks), selectinload(Asset.warranty)
        )
        .order_by(Asset.name)
    ).all()
    all_ids = [task.id for asset in rows for task in asset.tasks]
    statuses = task_status_map(session, all_ids)
    asset_ids = [asset.id for asset in rows]
    photo_ids: dict[int, int] = dict(
        session.execute(
            select(Document.asset_id, Document.id).where(
                Document.asset_id.in_(asset_ids), Document.doc_type == "photo"
            )
        ).all()  # type: ignore[arg-type]
    )
    items: list[AssetListItem] = []
    for asset in rows:
        task_statuses = [statuses[task.id].status for task in asset.tasks if task.id in statuses]
        items.append(
            AssetListItem(
                id=asset.id,
                name=asset.name,
                kind=asset.kind,  # type: ignore[arg-type]
                category_name=asset.category.name if asset.category is not None else None,
                category_slug=asset.category.slug if asset.category is not None else None,
                location_path=location_path(session, asset.location_id),
                install_date=asset.install_date,
                status=asset.status,
                task_status=worst_status(task_statuses),  # type: ignore[arg-type]
                photo_document_id=photo_ids.get(asset.id),
                warranty_end_date=asset.warranty.end_date if asset.warranty is not None else None,
            )
        )
    return items


@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(body: AssetIn, session: Session = Depends(get_session)) -> AssetOut:
    home = _home(session)
    if body.location_id is not None:
        location = session.get(Location, body.location_id)
        if location is None or location.home_id != home.id:
            raise HTTPException(404, "Lieu introuvable")
    if body.category_id is not None and session.get(Category, body.category_id) is None:
        raise HTTPException(404, "Catégorie introuvable")
    now = utc_now_iso()
    asset = Asset(
        home_id=home.id,
        kind=body.kind,
        name=body.name.strip(),
        category_id=body.category_id,
        location_id=body.location_id,
        status="active",
        brand=body.brand,
        model=body.model,
        reference=body.reference,
        serial_number=body.serial_number,
        purchase_date=body.purchase_date,
        install_date=body.install_date,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    session.add(asset)
    session.flush()
    _upsert_warranty(session, asset, body.warranty)
    session.flush()
    return _asset_out(session, _get_asset(session, asset.id))


@router.get("/assets/{asset_id}", response_model=AssetOut)
def read_asset(asset_id: int, session: Session = Depends(get_session)) -> AssetOut:
    return _asset_out(session, _get_asset(session, asset_id))


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def patch_asset(
    asset_id: int, body: AssetPatch, session: Session = Depends(get_session)
) -> AssetOut:
    asset = _get_asset(session, asset_id)
    data = body.model_dump(exclude_unset=True)
    warranty = data.pop("warranty", None)
    if "location_id" in data and data["location_id"] is not None:
        location = session.get(Location, data["location_id"])
        if location is None or location.home_id != asset.home_id:
            raise HTTPException(404, "Lieu introuvable")
    if "name" in data and isinstance(data["name"], str):
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(asset, key, value)
    asset.updated_at = utc_now_iso()
    if "warranty" in body.model_fields_set:
        _upsert_warranty(session, asset, WarrantyIn.model_validate(warranty) if warranty else None)
    session.flush()
    return _asset_out(session, _get_asset(session, asset.id))


def _get_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise HTTPException(404, "Membre introuvable")
    return member


def _replacement_part_rows(parts: list[ReplacementPartIn]) -> list[ReplacementPart]:
    return [
        ReplacementPart(
            name=part.name.strip(),
            source=(part.source or "").strip() or None,
            sort_order=index,
        )
        for index, part in enumerate(parts)
    ]


@router.post("/assets/{asset_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(asset_id: int, body: TaskIn, session: Session = Depends(get_session)) -> TaskOut:
    asset = _get_asset(session, asset_id)
    _validate_recurrence(
        body.recurrence_type,
        body.recurrence_interval,
        body.fixed_month,
        body.fixed_day,
        body.custom_due_date,
    )
    assignee = _get_member(session, body.assignee_id) if body.assignee_id is not None else None
    anchor, next_due = plan_task(
        recurrence_type=body.recurrence_type,
        interval=body.recurrence_interval,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        custom_due_date=body.custom_due_date,
        last_completed_on=body.last_completed_on,
    )
    now = utc_now_iso()
    task = MaintenanceTask(
        asset_id=asset.id,
        home_id=None,
        assignee_id=assignee.id if assignee is not None else None,
        name=body.name.strip(),
        priority=body.priority,
        recurrence_type=body.recurrence_type,
        recurrence_interval=body.recurrence_interval,
        recurrence_anchor=anchor,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        custom_due_date=body.custom_due_date,
        last_completed_on=body.last_completed_on,
        next_due_on=next_due,
        is_active=1,
        preparation_notes=(body.preparation_notes or "").strip() or None,
        description=(body.notes or "").strip() or None,
        replacement_parts=_replacement_part_rows(body.replacement_parts),
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.flush()
    if assignee is not None:
        notify_assignee(_home(session), task, assignee)
    statuses = task_status_map(session, [task.id])
    return _task_out(task, statuses.get(task.id), asset_name=asset.name)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, body: TaskPatch, session: Session = Depends(get_session)) -> TaskOut:
    task = session.get(MaintenanceTask, task_id)
    if task is None or task.asset_id is None:
        raise HTTPException(404, "Entretien introuvable")
    asset = _get_asset(session, task.asset_id)
    data = body.model_dump(exclude_unset=True)
    replace_parts = "replacement_parts" in data
    data.pop("replacement_parts", None)

    recurrence_fields = {
        "recurrence_type",
        "recurrence_interval",
        "fixed_month",
        "fixed_day",
        "custom_due_date",
        "last_completed_on",
    }
    if recurrence_fields & data.keys():
        rec_type = data.get("recurrence_type", task.recurrence_type)
        interval = data.get("recurrence_interval", task.recurrence_interval)
        fixed_month = data.get("fixed_month", task.fixed_month)
        fixed_day = data.get("fixed_day", task.fixed_day)
        custom_due_date = data.get("custom_due_date", task.custom_due_date)
        last_completed_on = data.get("last_completed_on", task.last_completed_on)
        _validate_recurrence(rec_type, interval, fixed_month, fixed_day, custom_due_date)
        anchor, next_due = plan_task(
            recurrence_type=rec_type,
            interval=interval,
            fixed_month=fixed_month,
            fixed_day=fixed_day,
            custom_due_date=custom_due_date,
            last_completed_on=last_completed_on,
        )
        task.recurrence_type = rec_type
        task.recurrence_interval = interval
        task.recurrence_anchor = anchor
        task.fixed_month = fixed_month
        task.fixed_day = fixed_day
        task.custom_due_date = custom_due_date
        task.last_completed_on = last_completed_on
        task.next_due_on = next_due
        for key in recurrence_fields:
            data.pop(key, None)

    new_assignee: Member | None = None
    assignee_changed = "assignee_id" in data
    if assignee_changed:
        assignee_id = data.pop("assignee_id")
        new_assignee = _get_member(session, assignee_id) if assignee_id is not None else None
        task.assignee_id = assignee_id

    if "name" in data and isinstance(data["name"], str):
        data["name"] = data["name"].strip()
    if "notes" in data:
        task.description = (data.pop("notes") or "").strip() or None
    for key, value in data.items():
        setattr(task, key, value)

    if replace_parts:
        task.replacement_parts = _replacement_part_rows(body.replacement_parts or [])

    task.updated_at = utc_now_iso()
    session.flush()

    if assignee_changed and new_assignee is not None:
        notify_assignee(_home(session), task, new_assignee)

    statuses = task_status_map(session, [task.id])
    return _task_out(
        task,
        statuses.get(task.id),
        asset_name=asset.name,
        loc_path=location_path(session, asset.location_id),
    )


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def mark_task_done(
    task_id: int, body: CompleteIn, session: Session = Depends(get_session)
) -> TaskOut:
    task = session.get(MaintenanceTask, task_id)
    if task is None or task.asset_id is None:
        raise HTTPException(404, "Entretien introuvable")
    asset = _get_asset(session, task.asset_id)
    performed_on = body.performed_on or utc_today().isoformat()
    intervention = complete_task(
        session,
        task,
        performed_on=performed_on,
        performed_by=body.performed_by,
        notes=body.notes,
    )
    if body.amount_cents is not None:
        home = _home(session)
        now = utc_now_iso()
        session.add(
            Cost(
                asset_id=asset.id,
                intervention_id=intervention.id,
                cost_type="maintenance",
                amount_cents=body.amount_cents,
                currency=home.currency,
                incurred_on=performed_on,
                created_at=now,
                updated_at=now,
            )
        )
    session.flush()
    statuses = task_status_map(session, [task.id])
    return _task_out(
        task,
        statuses.get(task.id),
        asset_name=asset.name,
        loc_path=location_path(session, asset.location_id),
        last_intervention_id=intervention.id,
    )


@router.get("/tasks/{task_id}/interventions", response_model=list[InterventionOut])
def list_task_interventions(
    task_id: int, session: Session = Depends(get_session)
) -> list[InterventionOut]:
    task = session.get(MaintenanceTask, task_id)
    if task is None or task.asset_id is None:
        raise HTTPException(404, "Entretien introuvable")
    _get_asset(session, task.asset_id)
    interventions = session.scalars(
        select(Intervention)
        .where(Intervention.task_id == task_id)
        .options(selectinload(Intervention.costs), selectinload(Intervention.documents))
        .order_by(Intervention.performed_on.desc(), Intervention.id.desc())
    ).all()
    return [
        InterventionOut(
            id=row.id,
            performed_on=row.performed_on,
            performed_by=row.performed_by,
            notes=row.notes,
            cost=_cost_out(row),
            documents=[_document_out(doc) for doc in row.documents],
        )
        for row in interventions
    ]


@router.get("/interventions", response_model=list[HistoryEntryOut])
def list_interventions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[HistoryEntryOut]:
    """Historique global, toutes les interventions de la maison confondues (page /entretiens)."""
    home = _home(session)
    rows = session.scalars(
        select(Intervention)
        .join(Asset, Intervention.asset_id == Asset.id)
        .where(Asset.home_id == home.id)
        .options(selectinload(Intervention.costs), selectinload(Intervention.documents))
        .order_by(Intervention.performed_on.desc(), Intervention.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    asset_ids = {row.asset_id for row in rows}
    assets = (
        {a.id: a for a in session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()}
        if asset_ids
        else {}
    )
    task_ids = {row.task_id for row in rows if row.task_id is not None}
    tasks = (
        {
            t.id: t
            for t in session.scalars(
                select(MaintenanceTask).where(MaintenanceTask.id.in_(task_ids))
            ).all()
        }
        if task_ids
        else {}
    )

    return [
        HistoryEntryOut(
            id=row.id,
            asset_id=row.asset_id,
            asset_name=assets[row.asset_id].name if row.asset_id in assets else "?",
            task_id=row.task_id,
            task_name=tasks[row.task_id].name if row.task_id in tasks else None,
            performed_on=row.performed_on,
            performed_by=row.performed_by,
            notes=row.notes,
            cost=_cost_out(row),
            documents=[_document_out(doc) for doc in row.documents],
        )
        for row in rows
    ]


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    task = session.get(MaintenanceTask, task_id)
    if task is None or task.asset_id is None:
        raise HTTPException(404, "Entretien introuvable")
    _get_asset(session, task.asset_id)
    session.delete(task)
    session.flush()
    return {"ok": True}


@router.delete("/interventions/{intervention_id}")
def delete_intervention(
    intervention_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, bool]:
    intervention = session.get(
        Intervention, intervention_id, options=(selectinload(Intervention.documents),)
    )
    if intervention is None:
        raise HTTPException(404, "Intervention introuvable")
    _get_asset(session, intervention.asset_id)
    for document in list(intervention.documents):
        _delete_document(session, settings, document)
    session.delete(intervention)
    session.flush()
    return {"ok": True}


_ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".doc",
    ".docx",
}
_MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def _document_out(row: Document) -> DocumentOut:
    return DocumentOut(
        id=row.id,
        name=row.name,
        doc_type=row.doc_type,
        file_size=row.file_size,
        mime_type=row.mime_type,
        created_at=row.created_at,
    )


def _cost_out(intervention: Intervention) -> CostOut | None:
    if not intervention.costs:
        return None
    cost = intervention.costs[0]
    return CostOut(
        id=cost.id,
        amount_cents=cost.amount_cents,
        currency=cost.currency,
        incurred_on=cost.incurred_on,
    )


async def _store_uploaded_file(
    asset_id: int, file: UploadFile, settings: Settings
) -> tuple[str, int, str | None, str]:
    original_name = file.filename or "document"
    extension = Path(original_name).suffix.lower()
    if extension not in _ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(415, "Type de fichier non accepte")
    content = await file.read()
    if len(content) > _MAX_DOCUMENT_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (10 Mo maximum)")

    asset_dir = settings.documents_dir / str(asset_id)
    asset_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    (asset_dir / stored_name).write_bytes(content)
    return f"{asset_id}/{stored_name}", len(content), file.content_type, original_name


def _delete_document(session: Session, settings: Settings, row: Document) -> None:
    if row.storage_mode == "local_file" and row.file_path:
        (settings.documents_dir / row.file_path).unlink(missing_ok=True)
    session.delete(row)


@router.post(
    "/interventions/{intervention_id}/documents", response_model=DocumentOut, status_code=201
)
async def upload_intervention_document(
    intervention_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentOut:
    intervention = session.get(Intervention, intervention_id)
    if intervention is None:
        raise HTTPException(404, "Intervention introuvable")
    _get_asset(session, intervention.asset_id)

    file_path, size, mime_type, original_name = await _store_uploaded_file(
        intervention.asset_id, file, settings
    )
    now = utc_now_iso()
    row = Document(
        intervention_id=intervention.id,
        name=original_name,
        doc_type="invoice",
        storage_mode="local_file",
        file_path=file_path,
        file_size=size,
        mime_type=mime_type,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _document_out(row)


@router.post("/assets/{asset_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_asset_document(
    asset_id: int,
    file: UploadFile = File(...),
    doc_type: Literal["manual", "invoice", "other", "photo"] = Form("manual"),
    name: str | None = Form(None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentOut:
    asset = _get_asset(session, asset_id)
    if doc_type == "photo":
        existing_photo = session.scalars(
            select(Document).where(Document.asset_id == asset.id, Document.doc_type == "photo")
        ).first()
        if existing_photo is not None:
            _delete_document(session, settings, existing_photo)
            session.flush()

    file_path, size, mime_type, original_name = await _store_uploaded_file(asset.id, file, settings)
    now = utc_now_iso()
    row = Document(
        asset_id=asset.id,
        name=(name or "").strip() or original_name,
        doc_type=doc_type,
        storage_mode="local_file",
        file_path=file_path,
        file_size=size,
        mime_type=mime_type,
        is_primary_photo=1 if doc_type == "photo" else 0,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _document_out(row)


@router.get("/assets/{asset_id}/documents", response_model=list[DocumentOut])
def list_asset_documents(
    asset_id: int, session: Session = Depends(get_session)
) -> list[DocumentOut]:
    asset = _get_asset(session, asset_id)
    rows = session.scalars(
        select(Document)
        .where(Document.asset_id == asset.id, Document.doc_type != "photo")
        .order_by(Document.created_at.desc())
    ).all()
    return [_document_out(row) for row in rows]


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, bool]:
    row = session.get(Document, document_id)
    if row is None or row.asset_id is None:
        raise HTTPException(404, "Document introuvable")
    _get_asset(session, row.asset_id)
    _delete_document(session, settings, row)
    session.flush()
    return {"ok": True}


@router.get("/documents/{document_id}/file")
def download_document(
    document_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> FileResponse:
    row = session.get(Document, document_id)
    if row is None or row.storage_mode != "local_file" or row.file_path is None:
        raise HTTPException(404, "Document introuvable")
    full_path = settings.documents_dir / row.file_path
    if not full_path.is_file():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(
        full_path, media_type=row.mime_type or "application/octet-stream", filename=row.name
    )


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskOut]:
    home = _home(session)
    tasks = session.scalars(
        select(MaintenanceTask)
        .join(Asset, MaintenanceTask.asset_id == Asset.id)
        .where(Asset.home_id == home.id, Asset.status != "removed", MaintenanceTask.is_active == 1)
        .options(
            selectinload(MaintenanceTask.replacement_parts),
            selectinload(MaintenanceTask.assignee),
        )
        .order_by(MaintenanceTask.next_due_on.is_(None), MaintenanceTask.next_due_on)
    ).all()
    statuses = task_status_map(session, [task.id for task in tasks])
    asset_ids = [task.asset_id for task in tasks if task.asset_id is not None]
    assets: dict[int, Asset] = {}
    if asset_ids:
        assets = {
            asset.id: asset
            for asset in session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()
        }
    result = [
        _task_out(
            task,
            statuses.get(task.id),
            asset_name=assets[task.asset_id].name if task.asset_id in assets else None,
            loc_path=location_path(session, assets[task.asset_id].location_id)
            if task.asset_id in assets
            else None,
        )
        for task in tasks
    ]
    # Priorite decroissante puis echeance croissante (spec ClickUp 869ezy08h).
    # Le statut 'overdue' force le badge 'urgente' cote affichage (voir frontend),
    # mais l'ordre par defaut reste base sur la priorite telle que stockee.
    priority_rank = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    result.sort(key=lambda item: (priority_rank.get(item.priority, 9), item.next_due_on or "9999"))
    return result


@router.get("/ha/devices", response_model=list[HaDeviceOut])
def ha_devices() -> list[HaDeviceOut]:
    try:
        return list_ha_devices()
    except HaUnavailableError as exc:
        raise HTTPException(503, f"Home Assistant injoignable : {exc}") from exc


@router.put("/assets/{asset_id}/ha-link", response_model=AssetOut)
def put_ha_link(asset_id: int, body: HaLinkIn, session: Session = Depends(get_session)) -> AssetOut:
    asset = _get_asset(session, asset_id)
    existing = session.scalars(
        select(HaLink).where(HaLink.ha_device_id == body.ha_device_id)
    ).first()
    if existing is not None and existing.asset_id != asset.id:
        raise HTTPException(409, "Cet appareil Home Assistant est deja lie a une autre fiche")
    now = utc_now_iso()
    link = primary_ha_link(asset)
    if link is None:
        link = HaLink(
            asset_id=asset.id,
            link_kind="device",
            ha_device_id=body.ha_device_id,
            name_at_link=body.name_at_link,
            entity_id_at_link=body.entity_id_at_link,
            domain_at_link=body.domain_at_link,
            role="primary",
            resolution_status="ok",
            last_resolved_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(link)
    else:
        link.ha_device_id = body.ha_device_id
        link.name_at_link = body.name_at_link
        link.entity_id_at_link = body.entity_id_at_link
        link.domain_at_link = body.domain_at_link
        link.resolution_status = "ok"
        link.last_resolved_at = now
        link.updated_at = now
    if body.area_name and asset.location_id is None:
        _assign_area_location(session, asset, body.area_name)
    session.flush()
    return _asset_out(session, _get_asset(session, asset.id))


@router.delete("/assets/{asset_id}/ha-link", response_model=AssetOut)
def delete_ha_link(asset_id: int, session: Session = Depends(get_session)) -> AssetOut:
    asset = _get_asset(session, asset_id)
    for link in list(asset.ha_links):
        session.delete(link)
    session.flush()
    return _asset_out(session, _get_asset(session, asset.id))


def _assign_area_location(session: Session, asset: Asset, area_name: str) -> None:
    home = _home(session)
    match = session.scalars(
        select(Location).where(Location.home_id == home.id, Location.name == area_name)
    ).first()
    if match is None:
        now = utc_now_iso()
        match = Location(
            home_id=home.id,
            name=area_name,
            location_type="room",
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add(match)
        session.flush()
    asset.location_id = match.id


def _validate_recurrence(
    rec_type: RecurrenceType,
    interval: int | None,
    fixed_month: int | None,
    fixed_day: int | None,
    custom_due_date: str | None,
) -> None:
    if rec_type in {"days", "months", "years"} and interval is None:
        raise HTTPException(422, "Indiquez l'intervalle (tous les X mois/ans/jours)")
    if rec_type == "annual_fixed" and (fixed_month is None or fixed_day is None):
        raise HTTPException(422, "Indiquez le jour et le mois pour un entretien annuel")
    if rec_type == "custom_date" and custom_due_date is None:
        raise HTTPException(422, "Indiquez la date de l'entretien ponctuel")
