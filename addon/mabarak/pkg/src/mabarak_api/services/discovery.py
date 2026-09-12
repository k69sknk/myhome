"""L'add-on s'annonce aupres du Supervisor (adr/0014).

`config.yaml` declare `discovery: [mabarak]` et `hassio_api: true` depuis
l'origine, et `config_flow.py` sait recevoir l'annonce — mais personne ne
l'emettait. L'integration retombait donc toujours sur la saisie manuelle, avec
une valeur d'hote par defaut qui ne pouvait pas etre juste : le Supervisor
resout un add-on a `<slug>` dont le prefixe est un hash du **depot** d'origine,
inconnu a l'avance.

L'add-on, lui, connait son propre nom d'hote : le Supervisor le lui donne sur
`/addons/self/info`. C'est donc a lui de l'annoncer.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)

# Le service declare dans `addon/mabarak/config.yaml`, cle `discovery`.
SERVICE = "mabarak"


# L'API du Supervisor, distincte de celle du Core (`/core/api`, ha_client.py).
def _supervisor_url() -> str:
    return os.environ.get("MABARAK_SUPERVISOR_URL", "http://supervisor")


def _headers() -> dict[str, str] | None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _self_info(client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
    reponse = client.get(f"{_supervisor_url()}/addons/self/info", headers=headers, timeout=10)
    reponse.raise_for_status()
    donnees: dict[str, Any] = reponse.json().get("data") or {}
    return donnees


def annoncer_au_superviseur(port: int) -> str | None:
    """Publie le message de decouverte. Rend le nom d'hote annonce, ou None.

    Volontairement silencieuse en cas d'echec : hors d'un add-on — en
    developpement, ou dans les tests — il n'y a pas de Supervisor, et ce n'est
    pas une panne. L'integration garde de toute facon sa saisie manuelle.
    """
    headers = _headers()
    if headers is None:
        _LOGGER.debug("Pas de SUPERVISOR_TOKEN : annonce ignoree (hors add-on)")
        return None

    try:
        with httpx.Client() as client:
            info = _self_info(client, headers)
            hote = info.get("hostname")
            if not hote:
                _LOGGER.warning("Le Supervisor n'a pas donne de nom d'hote : annonce ignoree")
                return None

            reponse = client.post(
                f"{_supervisor_url()}/discovery",
                headers=headers,
                json={"service": SERVICE, "config": {"host": hote, "port": port}},
                timeout=10,
            )
            reponse.raise_for_status()
    except httpx.HTTPError as exc:
        # Un echec ici ne doit pas empecher l'add-on de demarrer : l'interface
        # fonctionne sans integration, et l'integration s'ajoute a la main.
        _LOGGER.warning("Annonce au Supervisor impossible (%s) ; ajout manuel possible", exc)
        return None

    _LOGGER.info("Annonce au Supervisor : l'integration trouvera l'add-on sur %s:%s", hote, port)
    return str(hote)
