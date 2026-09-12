"""Integration MaBarak pour Home Assistant.

Elle ne stocke rien : toutes les donnees vivent dans l'add-on. Son role est
double : projeter l'etat de la maison en entites, pour rendre les entretiens
exploitables dans les automatisations et les notifications ; et ouvrir le seul
chemin d'ecriture depuis Home Assistant, en services et en intentions, pour que
l'application soit pilotable par un agent (adr/0013).
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MaBarakClient
from .const import CONF_HOST, CONF_PORT
from .coordinator import MaBarakConfigEntry, MaBarakCoordinator
from .intents import async_register_intents
from .services import async_register_services, async_remove_services

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

    # Les deux surfaces de pilotage (adr/0013). Les services servent les
    # automatisations ; les intentions sont le seul chemin par lequel un agent
    # branche sur le serveur MCP de Home Assistant peut voir MaBarak.
    async_register_services(hass)
    async_register_intents(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MaBarakConfigEntry) -> bool:
    decharge = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if decharge:
        async_remove_services(hass)
    return decharge
