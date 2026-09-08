"""Modeles Pydantic d'entree et de sortie."""

from typing import Literal

from pydantic import BaseModel, Field

LocationType = Literal["building", "floor", "room", "zone", "outdoor", "technical"]
RecurrenceType = Literal["none", "days", "months", "years", "annual_fixed", "custom_date"]
TaskStatus = Literal["ok", "due_soon", "overdue", "unscheduled"]
AssetStatus = Literal["planned", "active", "inactive", "removed"]


class HomeOut(BaseModel):
    id: int
    name: str
    address: str | None
    currency: str
    due_soon_threshold_days: int


class HomePatch(BaseModel):
    name: str | None = None
    address: str | None = None
    currency: str | None = None
    due_soon_threshold_days: int | None = Field(default=None, ge=0)


class LocationIn(BaseModel):
    name: str = Field(min_length=1)
    parent_id: int | None = None
    location_type: LocationType = "room"
    sort_order: int = 0
    notes: str | None = None


class LocationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    parent_id: int | None = None
    location_type: LocationType | None = None
    sort_order: int | None = None
    notes: str | None = None


class LocationOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    location_type: str
    sort_order: int
    notes: str | None
    path: str
    asset_count: int


class CategoryOut(BaseModel):
    id: int
    parent_id: int | None
    name: str
    slug: str
    icon: str | None
    is_builtin: bool
    sort_order: int


class WarrantyIn(BaseModel):
    start_date: str
    duration_months: int | None = Field(default=None, gt=0)
    provider: str | None = None
    terms_url: str | None = None
    notes: str | None = None


class WarrantyOut(BaseModel):
    start_date: str
    duration_months: int | None
    end_date: str | None
    provider: str | None
    terms_url: str | None
    notes: str | None


class HaLinkOut(BaseModel):
    ha_device_id: str | None
    name_at_link: str
    entity_id_at_link: str | None
    resolution_status: str


class HaLinkIn(BaseModel):
    ha_device_id: str
    name_at_link: str
    entity_id_at_link: str | None = None
    domain_at_link: str | None = None
    area_name: str | None = None


class TaskOut(BaseModel):
    id: int
    asset_id: int | None
    asset_name: str | None = None
    location_path: str | None = None
    name: str
    last_completed_on: str | None
    next_due_on: str | None
    status: TaskStatus
    days_until_due: int | None
    recurrence_type: str
    recurrence_interval: int | None
    fixed_month: int | None
    fixed_day: int | None


class TaskIn(BaseModel):
    name: str = Field(min_length=1)
    recurrence_type: RecurrenceType = "none"
    recurrence_interval: int | None = Field(default=None, ge=1)
    fixed_month: int | None = Field(default=None, ge=1, le=12)
    fixed_day: int | None = Field(default=None, ge=1, le=31)
    last_completed_on: str | None = None


class CompleteIn(BaseModel):
    performed_on: str | None = None
    performed_by: str | None = None
    notes: str | None = None


class AssetIn(BaseModel):
    name: str = Field(min_length=1)
    category_id: int | None = None
    location_id: int | None = None
    brand: str | None = None
    model: str | None = None
    reference: str | None = None
    serial_number: str | None = None
    purchase_date: str | None = None
    install_date: str | None = None
    notes: str | None = None
    warranty: WarrantyIn | None = None


class AssetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    category_id: int | None = None
    location_id: int | None = None
    status: AssetStatus | None = None
    brand: str | None = None
    model: str | None = None
    reference: str | None = None
    serial_number: str | None = None
    purchase_date: str | None = None
    install_date: str | None = None
    notes: str | None = None
    warranty: WarrantyIn | None = None


class AssetListItem(BaseModel):
    id: int
    name: str
    category_name: str | None
    location_path: str | None
    install_date: str | None
    status: str
    task_status: TaskStatus


class AssetOut(BaseModel):
    id: int
    name: str
    kind: str
    status: str
    category_id: int | None
    category_name: str | None
    location_id: int | None
    location_path: str | None
    brand: str | None
    model: str | None
    reference: str | None
    serial_number: str | None
    purchase_date: str | None
    install_date: str | None
    notes: str | None
    warranty: WarrantyOut | None
    ha_link: HaLinkOut | None
    tasks: list[TaskOut]


class HaDeviceOut(BaseModel):
    ha_device_id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    area_name: str | None = None
    entity_id: str | None = None
    domain: str | None = None
