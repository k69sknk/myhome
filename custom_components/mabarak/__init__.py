"""Integration MaBarak pour Home Assistant.

Elle ne stocke rien : toutes les donnees vivent dans l'add-on. Son role est de
projeter l'etat de la maison en entites, pour rendre les entretiens exploitables
dans les automatisations et les notifications.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MaBarakClient
from .const import CONF_HOST, CONF_PORT
from .coordinator import MaBarakConfigEntry, MaBarakCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: MaBarakConfigEntry) -> bool:
    client = MaBarakClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=async_get_clientsession(hass),
    )
    coordinator = MaBarakCoordinator(hass, entry, client)

    # Leve ConfigEntryNotReady si l'add-on n'est pas encore demarre, ce qui
    # declenche les nouvelles tentatives avec backoff de Home Assistant.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MaBarakConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
