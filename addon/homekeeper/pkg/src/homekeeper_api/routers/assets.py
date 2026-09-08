"""Fiches d'equipements et taches d'entretien."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..clock import utc_now_iso, utc_today
from ..db import get_session
from ..ha_client import HaUnavailableError, list_ha_devices
from ..models import (
    Asset,
    Category,
    HaLink,
    Home,
    Location,
    MaintenanceTask,
    TaskStatusRow,
    Warranty,
)
from ..schemas import (
    AssetIn,
    AssetListItem,
    AssetOut,
    AssetPatch,
    CompleteIn,
    HaDeviceOut,
    HaLinkIn,
    HaLinkOut,
    TaskIn,
    TaskOut,
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
            selectinload(Asset.tasks),
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
        last_completed_on=task.last_completed_on,
        next_due_on=task.next_due_on,
        status=status,
        days_until_due=days,
        recurrence_type=task.recurrence_type,
        recurrence_interval=task.recurrence_interval,
        fixed_month=task.fixed_month,
        fixed_day=task.fixed_day,
    )


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
def list_assets(session: Session = Depends(get_session)) -> list[AssetListItem]:
    home = _home(session)
    rows = session.scalars(
        select(Asset)
        .where(Asset.home_id == home.id, Asset.kind == "equipment", Asset.status != "removed")
        .options(selectinload(Asset.category), selectinload(Asset.tasks))
        .order_by(Asset.name)
    ).all()
    all_ids = [task.id for asset in rows for task in asset.tasks]
    statuses = task_status_map(session, all_ids)
    items: list[AssetListItem] = []
    for asset in rows:
        task_statuses = [statuses[task.id].status for task in asset.tasks if task.id in statuses]
        items.append(
            AssetListItem(
                id=asset.id,
                name=asset.name,
                category_name=asset.category.name if asset.category is not None else None,
                location_path=location_path(session, asset.location_id),
                install_date=asset.install_date,
                status=asset.status,
                task_status=worst_status(task_statuses),  # type: ignore[arg-type]
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
        raise HTTPException(404, "Categorie introuvable")
    now = utc_now_iso()
    asset = Asset(
        home_id=home.id,
        kind="equipment",
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


@router.post("/assets/{asset_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(asset_id: int, body: TaskIn, session: Session = Depends(get_session)) -> TaskOut:
    asset = _get_asset(session, asset_id)
    _validate_recurrence(body)
    anchor, next_due = plan_task(
        recurrence_type=body.recurrence_type,
        interval=body.recurrence_interval,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        last_completed_on=body.last_completed_on,
    )
    now = utc_now_iso()
    task = MaintenanceTask(
        asset_id=asset.id,
        home_id=None,
        name=body.name.strip(),
        recurrence_type=body.recurrence_type,
        recurrence_interval=body.recurrence_interval,
        recurrence_anchor=anchor,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        last_completed_on=body.last_completed_on,
        next_due_on=next_due,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.flush()
    statuses = task_status_map(session, [task.id])
    return _task_out(task, statuses.get(task.id), asset_name=asset.name)


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def mark_task_done(
    task_id: int, body: CompleteIn, session: Session = Depends(get_session)
) -> TaskOut:
    task = session.get(MaintenanceTask, task_id)
    if task is None or task.asset_id is None:
        raise HTTPException(404, "Entretien introuvable")
    asset = _get_asset(session, task.asset_id)
    performed_on = body.performed_on or utc_today().isoformat()
    complete_task(
        session,
        task,
        performed_on=performed_on,
        performed_by=body.performed_by,
        notes=body.notes,
    )
    session.flush()
    statuses = task_status_map(session, [task.id])
    return _task_out(
        task,
        statuses.get(task.id),
        asset_name=asset.name,
        loc_path=location_path(session, asset.location_id),
    )


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskOut]:
    home = _home(session)
    tasks = session.scalars(
        select(MaintenanceTask)
        .join(Asset, MaintenanceTask.asset_id == Asset.id)
        .where(Asset.home_id == home.id, Asset.status != "removed", MaintenanceTask.is_active == 1)
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
    rank = {"overdue": 0, "due_soon": 1, "ok": 2, "unscheduled": 3}
    result.sort(key=lambda item: (rank.get(item.status, 9), item.next_due_on or "9999"))
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


def _validate_recurrence(body: TaskIn) -> None:
    rec_type: RecurrenceType = body.recurrence_type
    if rec_type in {"days", "months", "years"} and body.recurrence_interval is None:
        raise HTTPException(422, "Indiquez l'intervalle (tous les X mois/ans/jours)")
    if rec_type == "annual_fixed" and (body.fixed_month is None or body.fixed_day is None):
        raise HTTPException(422, "Indiquez le jour et le mois pour un entretien annuel")
