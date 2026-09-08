"""Configuration par l'interface, sans YAML (ADR-0010 de Home Assistant)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import HomeKeeperClient, HomeKeeperConnectionError
from .const import (
    CONF_HOST,
    CONF_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
    NAME,
    SUPPORTED_API_SCHEMA_VERSION,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class HomeKeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Deux chemins : la decouverte par le Supervisor, et la saisie manuelle.

    La decouverte couvre le cas normal, ou l'add-on tourne sur la meme machine.
    La saisie manuelle reste indispensable : la decouverte echoue sur les
    installations ou l'add-on a ete renomme, et la retirer laisserait
    l'utilisateur sans recours.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}

    async def _async_validate(self, host: str, port: int) -> str | None:
        """Retourne une cle d'erreur, ou None si l'add-on repond correctement."""
        client = HomeKeeperClient(host, port, async_get_clientsession(self.hass))
        try:
            health = await client.health()
        except HomeKeeperConnectionError as err:
            LOGGER.debug("Add-on injoignable sur %s:%s : %s", host, port, err)
            return "cannot_connect"

        if health.get("api_schema_version") != SUPPORTED_API_SCHEMA_VERSION:
            return "unsupported_version"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate(user_input[CONF_HOST], user_input[CONF_PORT])
            if error is None:
                return self.async_create_entry(title=NAME, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """L'add-on s'est annonce aupres du Supervisor."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        self._discovered = {
            CONF_HOST: discovery_info.config.get("host", DEFAULT_HOST),
            CONF_PORT: discovery_info.config.get("port", DEFAULT_PORT),
        }
        self.context["title_placeholders"] = {"name": NAME}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await self._async_validate(
                self._discovered[CONF_HOST], self._discovered[CONF_PORT]
            )
            if error is None:
                return self.async_create_entry(title=NAME, data=self._discovered)
            errors["base"] = error

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"name": NAME},
            errors=errors,
        )
