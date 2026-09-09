"""Calendrier en lecture seule des entretiens a venir."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaBarakConfigEntry, MaBarakCoordinator
from .entity import MaBarakEntity


def _event_from_task(task: dict) -> CalendarEvent:
    start = date.fromisoformat(task["due_date"])
    summary = f"{task['name']} — {task['asset_name']}" if task.get("asset_name") else task["name"]
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=summary,
        description=f"Statut : {task.get('status', 'inconnu')}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaBarakConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([MaBarakCalendarEntity(coordinator)])


class MaBarakCalendarEntity(MaBarakEntity, CalendarEntity):
    _attr_translation_key = "entretiens"

    def __init__(self, coordinator: MaBarakCoordinator) -> None:
        super().__init__(coordinator, "entretiens")

    @property
    def event(self) -> CalendarEvent | None:
        tasks = self.coordinator.data.get("upcoming_tasks", [])
        upcoming = [task for task in tasks if task.get("due_date")]
        if not upcoming:
            return None
        return _event_from_task(min(upcoming, key=lambda task: task["due_date"]))

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        tasks = self.coordinator.data.get("upcoming_tasks", [])
        window_start = start_date.date()
        window_end = end_date.date()
        return [
            _event_from_task(task)
            for task in tasks
            if task.get("due_date")
            and window_start <= date.fromisoformat(task["due_date"]) <= window_end
        ]
