"""Diagnostics telechargeables depuis l'interface de Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import HomeKeeperConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeKeeperConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    summary = coordinator.data or {}

    # Ni les noms d'equipements ni les noms de taches ne sont inclus : ce fichier
    # est destine a etre partage dans un rapport de bug, et le projet repose sur
    # le fait que rien de personnel ne sorte de la machine.
    return {
        "entry": {
            "host": entry.data.get("host"),
            "port": entry.data.get("port"),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "summary": {
            "api_schema_version": summary.get("api_schema_version"),
            "generated_at": summary.get("generated_at"),
            "counts": summary.get("counts"),
            "asset_count": len(summary.get("assets", [])),
            "has_next_task": summary.get("next_task") is not None,
            "expiring_warranty_count": len(summary.get("warranties_expiring", [])),
        },
    }
