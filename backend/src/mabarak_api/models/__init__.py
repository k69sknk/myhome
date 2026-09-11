"""Tables SQLAlchemy alignees sur docs/schema.sql."""

from __future__ import annotations

from sqlalchemy import Computed, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Home(Base):
    __tablename__ = "home"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, default="EUR")
    due_soon_threshold_days: Mapped[int] = mapped_column(Integer, default=30)
    ha_calendar_entity_id: Mapped[str | None] = mapped_column(Text)
    ha_calendar_sync_enabled: Mapped[int] = mapped_column(Integer, default=0)
    task_notifications_enabled: Mapped[int] = mapped_column(Integer, default=0)
    reminder_hour: Mapped[int] = mapped_column(Integer, default=8)
    default_notify_service: Mapped[str | None] = mapped_column(Text)
    last_reminder_run_on: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    locations: Mapped[list[Location]] = relationship(back_populates="home")
    assets: Mapped[list[Asset]] = relationship(back_populates="home")


class LocationType(Base):
    __tablename__ = "location_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    is_builtin: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class Location(Base):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("home.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("location.id"))
    name: Mapped[str] = mapped_column(Text)
    location_type_id: Mapped[int] = mapped_column(ForeignKey("location_type.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    catalog_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    home: Mapped[Home] = relationship(back_populates="locations")
    parent: Mapped[Location | None] = relationship(remote_side=[id])
    location_type: Mapped[LocationType] = relationship()
    assets: Mapped[list[Asset]] = relationship(back_populates="location")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"))
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    icon: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[int] = mapped_column(Integer, default=0)
    is_hidden: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    parent: Mapped[Category | None] = relationship(remote_side=[id])


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("home.id"))
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("location.id"))
    status: Mapped[str] = mapped_column(Text, default="active")
    manufacturer_id: Mapped[int | None] = mapped_column(Integer)
    brand: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    serial_number: Mapped[str | None] = mapped_column(Text)
    purchase_date: Mapped[str | None] = mapped_column(Text)
    install_date: Mapped[str | None] = mapped_column(Text)
    manual_url: Mapped[str | None] = mapped_column(Text)
    support_url: Mapped[str | None] = mapped_column(Text)
    parts_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    catalog_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    home: Mapped[Home] = relationship(back_populates="assets")
    location: Mapped[Location | None] = relationship(back_populates="assets")
    category: Mapped[Category | None] = relationship()
    warranty: Mapped[Warranty | None] = relationship(back_populates="asset")
    tasks: Mapped[list[MaintenanceTask]] = relationship(back_populates="asset")
    ha_links: Mapped[list[HaLink]] = relationship(back_populates="asset")


class Warranty(Base):
    __tablename__ = "warranty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), unique=True)
    start_date: Mapped[str] = mapped_column(Text)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    end_date: Mapped[str | None] = mapped_column(
        Text,
        Computed(
            "CASE WHEN duration_months IS NULL THEN NULL "
            "ELSE date(start_date, '+' || duration_months || ' months') END"
        ),
    )
    provider: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="warranty")


class MaintenanceTask(Base):
    __tablename__ = "maintenance_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"))
    home_id: Mapped[int | None] = mapped_column(ForeignKey("home.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("member.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text, default="normal")
    preparation_notes: Mapped[str | None] = mapped_column(Text)
    recurrence_type: Mapped[str] = mapped_column(Text, default="none")
    recurrence_interval: Mapped[int | None] = mapped_column(Integer)
    recurrence_anchor: Mapped[str] = mapped_column(Text, default="from_completion")
    fixed_month: Mapped[int | None] = mapped_column(Integer)
    fixed_day: Mapped[int | None] = mapped_column(Integer)
    custom_due_date: Mapped[str | None] = mapped_column(Text)
    season_start_month: Mapped[int | None] = mapped_column(Integer)
    season_end_month: Mapped[int | None] = mapped_column(Integer)
    last_completed_on: Mapped[str | None] = mapped_column(Text)
    next_due_on: Mapped[str | None] = mapped_column(Text)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    last_reminded_on: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    catalog_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset | None] = relationship(back_populates="tasks")
    assignee: Mapped[Member | None] = relationship()
    replacement_parts: Mapped[list[ReplacementPart]] = relationship(
        back_populates="task",
        order_by="ReplacementPart.sort_order",
        cascade="all, delete-orphan",
    )


class Member(Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_id: Mapped[int | None] = mapped_column(ForeignKey("home.id"))
    name: Mapped[str] = mapped_column(Text)
    member_type: Mapped[str] = mapped_column(Text, default="household")
    contact: Mapped[str | None] = mapped_column(Text)
    ha_person_entity_id: Mapped[str | None] = mapped_column(Text)
    ha_notify_service: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class ReplacementPart(Base):
    __tablename__ = "replacement_part"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_task.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    task: Mapped[MaintenanceTask] = relationship(back_populates="replacement_parts")


class HaLink(Base):
    __tablename__ = "ha_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    link_kind: Mapped[str] = mapped_column(Text)
    ha_device_id: Mapped[str | None] = mapped_column(Text)
    ha_entity_registry_id: Mapped[str | None] = mapped_column(Text)
    entity_id_at_link: Mapped[str | None] = mapped_column(Text)
    name_at_link: Mapped[str] = mapped_column(Text)
    domain_at_link: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="primary")
    consumable_kind: Mapped[str | None] = mapped_column(Text)
    last_resolved_at: Mapped[str | None] = mapped_column(Text)
    resolution_status: Mapped[str] = mapped_column(Text, default="unresolved")
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="ha_links")


class Intervention(Base):
    __tablename__ = "intervention"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_task.id"))
    issue_id: Mapped[int | None] = mapped_column(Integer)
    intervention_type: Mapped[str] = mapped_column(Text, default="maintenance")
    performed_on: Mapped[str] = mapped_column(Text)
    # Le nom affiche, fige a la saisie ; le membre, quand il y en a un, permet de
    # regrouper les interventions d'un meme prestataire (voir schema.sql).
    performed_by: Mapped[str | None] = mapped_column(Text)
    performed_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("member.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    costs: Mapped[list[Cost]] = relationship(back_populates="intervention")
    documents: Mapped[list[Document]] = relationship(back_populates="intervention")


class Cost(Base):
    __tablename__ = "cost"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    intervention_id: Mapped[int | None] = mapped_column(ForeignKey("intervention.id"))
    cost_type: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(Text, default="EUR")
    incurred_on: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    intervention: Mapped[Intervention | None] = relationship(back_populates="costs")


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    home_id: Mapped[int | None] = mapped_column(ForeignKey("home.id"))
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"))
    maintenance_task_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_task.id"))
    intervention_id: Mapped[int | None] = mapped_column(ForeignKey("intervention.id"))
    issue_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(Text, default="other")
    storage_mode: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    reference_note: Mapped[str | None] = mapped_column(Text)
    is_primary_photo: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)

    intervention: Mapped[Intervention | None] = relationship(back_populates="documents")


class TaskStatusRow(Base):
    """Vue `v_task_status` : lecture seule."""

    __tablename__ = "v_task_status"
    __table_args__ = {"info": {"is_view": True}}

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(Integer)
    home_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text)
    next_due_on: Mapped[str | None] = mapped_column(Text)
    last_completed_on: Mapped[str | None] = mapped_column(Text)
    effective_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    days_until_due: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
