"""Contrat consomme par l'integration Home Assistant."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..clock import utc_today
from ..config import API_SCHEMA_VERSION
from ..db import get_session
from ..ha_client import HaUnavailableError, list_ha_calendars
from ..models import Asset, TaskStatusRow, Warranty
from ..schemas import CalendarSyncResult, HaCalendarOut
from ..services.calendar_sync import CalendarSyncConfigurationError, run_calendar_sync
from ..services.catalog import worst_status
from ..services.home import ensure_home

router = APIRouter(prefix="/ha", tags=["home assistant"])

TaskStatus = str

# Fenetre du calendrier expose a Home Assistant : tout le retard, plus les
# echeances a venir sur les 6 prochains mois. Au-dela, l'entretien n'a pas
# encore sa place dans un calendrier (et alourdirait le contrat pour rien).
UPCOMING_WINDOW_DAYS = 180
UPCOMING_MAX_ENTRIES = 200


class SummaryCounts(BaseModel):
    overdue: int = 0
    due_soon: int = 0
    ok: int = 0
    unscheduled: int = 0


class NextTask(BaseModel):
    id: int
    name: str
    asset_name: str | None = None
    asset_id: int | None = None
    due_date: str
    days_until: int


class AssetStatus(BaseModel):
    id: int
    name: str
    status: str


class ExpiringWarranty(BaseModel):
    asset_id: int
    asset_name: str
    end_date: str


class TaskCalendarEntry(BaseModel):
    id: int
    name: str
    asset_id: int | None = None
    asset_name: str | None = None
    due_date: str
    status: str


class HaSummary(BaseModel):
    api_schema_version: int = Field(default=API_SCHEMA_VERSION)
    generated_at: datetime
    counts: SummaryCounts
    next_task: NextTask | None = None
    assets: list[AssetStatus] = Field(default_factory=list)
    warranties_expiring: list[ExpiringWarranty] = Field(default_factory=list)
    upcoming_tasks: list[TaskCalendarEntry] = Field(default_factory=list)


@router.get("/summary", response_model=HaSummary, summary="Synthese pour Home Assistant")
def summary(session: Session = Depends(get_session)) -> HaSummary:
    ensure_home(session)
    rows = session.scalars(select(TaskStatusRow)).all()
    counts = SummaryCounts()
    for row in rows:
        if row.status == "overdue":
            counts.overdue += 1
        elif row.status == "due_soon":
            counts.due_soon += 1
        elif row.status == "ok":
            counts.ok += 1
        else:
            counts.unscheduled += 1

    scheduled = [row for row in rows if row.next_due_on is not None]
    scheduled.sort(key=lambda row: (0 if row.status == "overdue" else 1, row.next_due_on or ""))
    next_task: NextTask | None = None
    if scheduled:
        row = scheduled[0]
        asset_name = None
        if row.asset_id is not None:
            asset = session.get(Asset, row.asset_id)
            asset_name = None if asset is None else asset.name
        next_task = NextTask(
            id=row.task_id,
            name=row.name,
            asset_name=asset_name,
            asset_id=row.asset_id,
            due_date=row.next_due_on or "",
            days_until=row.days_until_due or 0,
        )

    assets = session.scalars(
        select(Asset)
        .where(Asset.kind == "equipment", Asset.status != "removed")
        .options(selectinload(Asset.tasks))
        .order_by(Asset.name)
    ).all()
    status_by_task = {row.task_id: row.status for row in rows}
    asset_statuses = [
        AssetStatus(
            id=asset.id,
            name=asset.name,
            status=worst_status(
                [status_by_task[task.id] for task in asset.tasks if task.id in status_by_task]
            ),
        )
        for asset in assets
    ]

    today = utc_today()
    asset_name_by_id = {asset.id: asset.name for asset in assets}
    upcoming_limit = (today + timedelta(days=UPCOMING_WINDOW_DAYS)).isoformat()
    upcoming = [
        row
        for row in rows
        if row.next_due_on is not None and row.next_due_on <= upcoming_limit
    ]
    upcoming.sort(key=lambda row: row.next_due_on or "")
    upcoming_tasks = [
        TaskCalendarEntry(
            id=row.task_id,
            name=row.name,
            asset_id=row.asset_id,
            asset_name=asset_name_by_id.get(row.asset_id) if row.asset_id else None,
            due_date=row.next_due_on or "",
            status=row.status,
        )
        for row in upcoming[:UPCOMING_MAX_ENTRIES]
    ]

    limit = (today + timedelta(days=30)).isoformat()
    warranties: list[ExpiringWarranty] = []
    for warranty in session.scalars(select(Warranty).where(Warranty.end_date.is_not(None))).all():
        if warranty.end_date is None:
            continue
        if today.isoformat() <= warranty.end_date <= limit:
            asset = session.get(Asset, warranty.asset_id)
            if asset is None:
                continue
            warranties.append(
                ExpiringWarranty(
                    asset_id=asset.id, asset_name=asset.name, end_date=warranty.end_date
                )
            )

    return HaSummary(
        generated_at=datetime.now(UTC),
        counts=counts,
        next_task=next_task,
        assets=asset_statuses,
        warranties_expiring=warranties,
        upcoming_tasks=upcoming_tasks,
    )


@router.get("/calendars", response_model=list[HaCalendarOut])
def calendars() -> list[HaCalendarOut]:
    try:
        return list_ha_calendars()
    except HaUnavailableError as exc:
        raise HTTPException(503, f"Home Assistant injoignable : {exc}") from exc


@router.post("/calendar-sync/run", response_model=CalendarSyncResult)
def calendar_sync_run(session: Session = Depends(get_session)) -> CalendarSyncResult:
    try:
        return run_calendar_sync(session)
    except CalendarSyncConfigurationError as exc:
        raise HTTPException(409, str(exc)) from exc
    except HaUnavailableError as exc:
        raise HTTPException(503, f"Home Assistant injoignable : {exc}") from exc
