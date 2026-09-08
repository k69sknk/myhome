"""Capteurs exposant l'etat d'entretien de la maison."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomeKeeperConfigEntry, HomeKeeperCoordinator
from .entity import HomeKeeperEntity


@dataclass(frozen=True, kw_only=True)
class HomeKeeperSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Mapping[str, Any]], int | date | None]
    attributes_fn: Callable[[Mapping[str, Any]], Mapping[str, Any] | None] | None = None


def _next_task_date(data: Mapping[str, Any]) -> date | None:
    next_task = data.get("next_task")
    if not next_task or not next_task.get("due_date"):
        return None
    return date.fromisoformat(next_task["due_date"])


def _next_task_attributes(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    next_task = data.get("next_task")
    if not next_task:
        return None
    return {
        "task": next_task.get("name"),
        "asset": next_task.get("asset_name"),
        "days_until": next_task.get("days_until"),
    }


SENSORS: tuple[HomeKeeperSensorDescription, ...] = (
    HomeKeeperSensorDescription(
        key="tasks_overdue",
        translation_key="tasks_overdue",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("counts", {}).get("overdue", 0),
    ),
    HomeKeeperSensorDescription(
        key="tasks_due_soon",
        translation_key="tasks_due_soon",
        icon="mdi:clock-alert-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("counts", {}).get("due_soon", 0),
    ),
    HomeKeeperSensorDescription(
        key="next_maintenance",
        translation_key="next_maintenance",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.DATE,
        value_fn=_next_task_date,
        attributes_fn=_next_task_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeKeeperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(HomeKeeperSensor(coordinator, description) for description in SENSORS)


class HomeKeeperSensor(HomeKeeperEntity, SensorEntity):
    entity_description: HomeKeeperSensorDescription

    def __init__(
        self,
        coordinator: HomeKeeperCoordinator,
        description: HomeKeeperSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | date | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
