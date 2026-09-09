"""Base commune aux entites MaBarak."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import MaBarakCoordinator


class MaBarakEntity(CoordinatorEntity[MaBarakCoordinator]):
    """Toutes les entites sont regroupees sous un appareil unique.

    `DeviceEntryType.SERVICE` plutot qu'un appareil physique : MaBarak est un
    service local, pas un materiel.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: MaBarakCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )
