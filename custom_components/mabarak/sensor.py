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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MaBarakConfigEntry, MaBarakCoordinator
from .entity import MaBarakEntity


@dataclass(frozen=True, kw_only=True)
class MaBarakSensorDescription(SensorEntityDescription):
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


SENSORS: tuple[MaBarakSensorDescription, ...] = (
    MaBarakSensorDescription(
        key="tasks_overdue",
        translation_key="tasks_overdue",
        icon="mdi:alert-circle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("counts", {}).get("overdue", 0),
    ),
    MaBarakSensorDescription(
        key="tasks_due_soon",
        translation_key="tasks_due_soon",
        icon="mdi:clock-alert-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("counts", {}).get("due_soon", 0),
    ),
    MaBarakSensorDescription(
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
    entry: MaBarakConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(MaBarakSensor(coordinator, description) for description in SENSORS)
    _suivre_les_equipements(coordinator, async_add_entities)


def _suivre_les_equipements(
    coordinator: MaBarakCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Un capteur de statut par equipement, cree au fil des fiches.

    Les fiches naissent dans l'add-on, pas ici : la liste ne peut donc pas etre
    connue au demarrage. On ajoute les capteurs a mesure qu'ils apparaissent
    dans le resume. Une fiche supprimee laisse son entite derriere elle, marquee
    indisponible — c'est le comportement attendu d'une integration Home
    Assistant, qui n'efface pas une entite que des automatisations referencent
    peut-etre encore.
    """
    connus: set[int] = set()

    @callback
    def ajouter_les_nouveaux() -> None:
        nouveaux = [
            MaBarakStatutEquipement(coordinator, asset["id"], asset["name"])
            for asset in coordinator.data.get("assets", [])
            if asset.get("id") is not None and asset["id"] not in connus
        ]
        connus.update(capteur.asset_id for capteur in nouveaux)
        if nouveaux:
            async_add_entities(nouveaux)

    ajouter_les_nouveaux()
    coordinator.config_entry.async_on_unload(
        coordinator.async_add_listener(ajouter_les_nouveaux)
    )


class MaBarakSensor(MaBarakEntity, SensorEntity):
    entity_description: MaBarakSensorDescription

    def __init__(
        self,
        coordinator: MaBarakCoordinator,
        description: MaBarakSensorDescription,
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


class MaBarakStatutEquipement(MaBarakEntity, SensorEntity):
    """Le pire statut d'entretien d'un equipement : `ok`, `due_soon`, `overdue`.

    Ce capteur existe pour les automatisations ciblees — « previens-moi quand la
    chaudiere passe en retard » — que les compteurs globaux ne permettent pas.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "due_soon", "overdue", "unscheduled"]
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator: MaBarakCoordinator, asset_id: int, nom: str) -> None:
        super().__init__(coordinator, f"asset_{asset_id}")
        self.asset_id = asset_id
        self._attr_name = nom

    @property
    def _fiche(self) -> Mapping[str, Any] | None:
        for asset in self.coordinator.data.get("assets", []):
            if asset.get("id") == self.asset_id:
                return asset
        return None

    @property
    def available(self) -> bool:
        # La fiche a disparu de l'add-on (supprimee, ou mise au rebut) : l'etat
        # affiche serait celui d'avant, ce qui est pire qu'un etat absent.
        return super().available and self._fiche is not None

    @property
    def native_value(self) -> str | None:
        fiche = self._fiche
        return None if fiche is None else str(fiche.get("status"))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        fiche = self._fiche
        return None if fiche is None else {"asset_id": self.asset_id, "nom": fiche.get("name")}
