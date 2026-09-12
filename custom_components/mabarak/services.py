"""Services `mabarak.*` (adr/0013).

Cette surface sert les automatisations, les scripts, et tout agent qui parle a
Home Assistant par son API REST avec un jeton. Les agents branches en MCP, eux,
passent par `intents.py` : le serveur MCP n'expose pas les services.

Les deux se contentent d'habiller `actions.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .actions import ACTIONS, Action, executer
from .api import MaBarakConnectionError, MaBarakRefusError
from .const import DOMAIN
from .coordinator import MaBarakCoordinator


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Enregistre un service par action. Idempotent : appele a chaque entree."""
    for action in ACTIONS:
        if hass.services.has_service(DOMAIN, action.nom):
            continue
        hass.services.async_register(
            DOMAIN,
            action.nom,
            _handler(action),
            schema=vol.Schema(action.schema),
            supports_response=(
                SupportsResponse.ONLY if action.lecture_seule else SupportsResponse.OPTIONAL
            ),
        )


@callback
def async_remove_services(hass: HomeAssistant) -> None:
    for action in ACTIONS:
        hass.services.async_remove(DOMAIN, action.nom)


def _handler(action: Action) -> Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]:
    async def handler(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(call.hass)
        try:
            donnees = await executer(coordinator.client, action, call.data)
        except MaBarakRefusError as err:
            # Le refus vient du backend et nomme les candidats possibles :
            # `ServiceValidationError` l'affiche tel quel a l'utilisateur, sans
            # trace d'exception, parce que ce n'est pas un bug.
            raise ServiceValidationError(str(err)) from err
        except MaBarakConnectionError as err:
            raise HomeAssistantError(f"L'add-on MaBarak est injoignable : {err}") from err

        if not action.lecture_seule:
            # Les compteurs et le calendrier viennent de changer : les rafraichir
            # tout de suite evite qu'une automatisation enchainee lise l'etat
            # d'avant pendant les cinq minutes du cycle de sondage.
            await coordinator.async_request_refresh()

        return _reponse(action, donnees)

    return handler


def _reponse(action: Action, donnees: Any) -> ServiceResponse:
    reponse: dict[str, Any] = {"message": action.phrase(donnees)}
    if isinstance(donnees, list):
        reponse["resultats"] = donnees
    elif isinstance(donnees, dict):
        reponse |= {cle: valeur for cle, valeur in donnees.items() if cle != "message"}
    return reponse


def _coordinator(hass: HomeAssistant) -> MaBarakCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            "L'integration MaBarak n'est pas configuree, ou l'add-on n'a pas encore demarre."
        )
    coordinator: MaBarakCoordinator = entries[0].runtime_data
    return coordinator
