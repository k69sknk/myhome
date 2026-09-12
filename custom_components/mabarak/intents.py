"""Intentions MaBarak, la surface que voient les agents en MCP (adr/0013).

Le serveur MCP de Home Assistant expose l'API « Assist », qui construit un outil
par intention enregistree — et **aucun** service. Sans ce fichier, un agent
branche en MCP ne verrait rien de MaBarak, quel que soit le nombre de services
declares a cote.

Deux details en decoulent, et ils sont fragiles :

* `platforms` doit rester a `None`. L'API Assist ne garde que les intentions
  dont `platforms` recoupe les domaines d'entites exposees a l'assistant ;
  « mabarak » n'est pas un domaine d'entites, une valeur non nulle ferait donc
  disparaitre ces outils.
* `description` et les descriptions de chaque champ du schema sont la seule
  documentation que l'agent recevra. Elles vivent dans `actions.py`.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent

from .actions import ACTIONS, Action, executer
from .api import MaBarakConnectionError, MaBarakRefusError
from .const import DOMAIN
from .coordinator import MaBarakCoordinator

# Prefixe des `intent_type`. La convention Home Assistant est le CamelCase
# (`HassTurnOn`) ; le nom devient tel quel celui de l'outil expose en MCP.
PREFIXE = "MaBarak"

# Clef du drapeau d'enregistrement dans `hass.data`.
INTENTIONS_ENREGISTREES = f"{DOMAIN}_intentions"


def _type_intention(nom: str) -> str:
    return PREFIXE + "".join(morceau.capitalize() for morceau in nom.split("_"))


class MaBarakIntentHandler(intent.IntentHandler):
    """Une action de `actions.py`, exposee comme intention."""

    # Voir l'en-tete du module : toute autre valeur rendrait l'outil invisible.
    platforms = None

    def __init__(self, action: Action) -> None:
        self._action = action
        self.intent_type = _type_intention(action.nom)
        self.description = action.description

    @property
    def slot_schema(self) -> dict[Any, Any] | None:
        return self._action.schema or None

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        reponse = intent_obj.create_response()
        coordinator = _coordinator(intent_obj.hass)

        donnees = _valider(self, intent_obj)
        try:
            resultat = await executer(coordinator.client, self._action, donnees)
        except MaBarakRefusError as err:
            # Le message nomme les candidats : c'est precisement ce dont l'agent
            # a besoin pour reformuler, il doit donc lui parvenir intact.
            raise intent.IntentHandleError(str(err)) from err
        except MaBarakConnectionError as err:
            raise intent.IntentHandleError(
                f"L'add-on MaBarak est injoignable : {err}"
            ) from err

        if not self._action.lecture_seule:
            await coordinator.async_request_refresh()

        reponse.async_set_speech(self._action.phrase(resultat))
        # Le detail structure accompagne la phrase : l'agent peut y puiser une
        # date ou un nom exact sans avoir a analyser du francais.
        reponse.async_set_speech_slots({"mabarak": resultat})
        return reponse


def _valider(handler: intent.IntentHandler, intent_obj: intent.Intent) -> dict[str, Any]:
    """Valide les champs recus et rend ceux qui sont renseignes.

    Sans cette validation explicite, `IntentHandler` ne verifie rien : la base
    laisse chaque gestionnaire appeler `async_validate_slots` lui-meme.

    Surtout, elle traduit l'echec. Une `vol.Invalid` qui remonte telle quelle
    est reemballee par Home Assistant en « Received invalid slot info for
    MaBarakValiderEntretien » — le detail ne va qu'au journal, et l'agent ne
    saura jamais quel champ il a manque. Une `IntentHandleError`, elle, remonte
    intacte (`async_handle` laisse passer les `IntentError`).
    """
    try:
        handler.async_validate_slots(intent_obj.slots)
    except vol.Invalid as err:
        champ = ".".join(str(morceau) for morceau in err.path if morceau != "value")
        if "required key not provided" in str(err.msg):
            raise intent.IntentHandleError(
                f"Le champ « {champ} » est obligatoire et n'a pas ete fourni."
            ) from err
        raise intent.IntentHandleError(
            f"Le champ « {champ} » est invalide : {err.msg}" if champ else str(err.msg)
        ) from err

    return {cle: valeur["value"] for cle, valeur in intent_obj.slots.items()}


@callback
def async_register_intents(hass: HomeAssistant) -> None:
    """Enregistre une intention par action.

    Les intentions sont globales et non liees a une entree de configuration :
    les reenregistrer a chaque rechargement ne ferait qu'emplir le journal
    d'avertissements « intent is being overwritten ». Un drapeau suffit, car
    elles n'ont rien a desenregistrer — elles vont chercher le coordinator au
    moment de l'appel, et disent elles-memes s'il n'y en a pas.
    """
    if hass.data.get(INTENTIONS_ENREGISTREES):
        return
    for action in ACTIONS:
        intent.async_register(hass, MaBarakIntentHandler(action))
    hass.data[INTENTIONS_ENREGISTREES] = True


def _coordinator(hass: HomeAssistant) -> MaBarakCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise intent.IntentHandleError(
            "L'integration MaBarak n'est pas configuree, ou l'add-on n'a pas encore demarre."
        )
    coordinator: MaBarakCoordinator = entries[0].runtime_data
    return coordinator
