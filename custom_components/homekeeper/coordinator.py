"""Coordinator : une seule requete alimente toutes les entites."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HomeKeeperClient, HomeKeeperConnectionError
from .const import LOGGER, SUPPORTED_API_SCHEMA_VERSION, UPDATE_INTERVAL

type HomeKeeperConfigEntry = ConfigEntry[HomeKeeperCoordinator]


class HomeKeeperCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Interroge `/api/ha/summary` et diffuse le resultat a toutes les entites.

    Un coordinator unique, plutot qu'un `async_update` par entite : le backend
    calcule deja tous les compteurs et statuts en une fois, et c'est la source
    unique qui garantit que les capteurs Home Assistant et le tableau de bord de
    l'add-on affichent les memes valeurs.
    """

    config_entry: HomeKeeperConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomeKeeperConfigEntry,
        client: HomeKeeperClient,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="HomeKeeper",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            summary = await self.client.summary()
        except HomeKeeperConnectionError as err:
            raise UpdateFailed(f"Add-on HomeKeeper injoignable : {err}") from err

        version = summary.get("api_schema_version")
        if version != SUPPORTED_API_SCHEMA_VERSION:
            # L'add-on et l'integration se mettent a jour separement (ADR-0005).
            # Un message explicite evite a l'utilisateur de chercher une panne
            # la ou il n'y a qu'un decalage de versions.
            raise ConfigEntryError(
                f"Version de l'add-on HomeKeeper incompatible : contrat v{version} recu, "
                f"v{SUPPORTED_API_SCHEMA_VERSION} attendu. Mettez a jour l'add-on et "
                "l'integration ensemble."
            )

        return summary
