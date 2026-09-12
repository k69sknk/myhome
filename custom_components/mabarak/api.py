"""Client HTTP de l'add-on MaBarak."""

from __future__ import annotations

from typing import Any

import aiohttp
from yarl import URL


class MaBarakError(Exception):
    """Erreur generique de communication avec l'add-on."""


class MaBarakConnectionError(MaBarakError):
    """L'add-on est injoignable."""


class MaBarakIncompatibleError(MaBarakError):
    """La version de contrat de l'add-on n'est pas supportee."""


class MaBarakRefusError(MaBarakError):
    """L'add-on a refuse l'action, et explique pourquoi.

    C'est le cas normal du pilotage par agent (adr/0013), pas une panne : un nom
    d'equipement ambigu, un entretien introuvable, un doublon. Le message vient
    du backend, qui seul connait les fiches existantes, et il est destine a etre
    relu tel quel a l'utilisateur.
    """


class MaBarakClient:
    """Acces a l'API de l'add-on, en lecture comme en ecriture.

    L'add-on n'expose aucune authentification : il n'est joignable que depuis le
    reseau interne de Home Assistant, et son propre filtrage d'adresse IP le
    protege (docs/ARCHITECTURE.md section 4). C'est pourquoi l'ecriture passe
    par cette integration et non par une API ouverte a l'exterieur : Home
    Assistant reste le seul point d'authentification, et chaque appel figure
    dans son journal (adr/0013).
    """

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        self._base = URL.build(scheme="http", host=host, port=port) / "api"
        self._session = session

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                self._base / path,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                # 4xx porte une explication redigee par le backend ; la perdre
                # pour un « Bad Request » generique priverait l'agent appelant
                # de la seule chose qui lui permet de se corriger.
                if 400 <= response.status < 500:
                    raise MaBarakRefusError(await _detail(response))
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MaBarakConnectionError(str(err)) from err

    async def _get(self, path: str, **params: str) -> Any:
        return await self._request("GET", path, params=params or None)

    async def health(self) -> dict[str, Any]:
        data: dict[str, Any] = await self._get("health")
        return data

    async def summary(self) -> dict[str, Any]:
        data: dict[str, Any] = await self._get("ha/summary")
        return data

    # --- Pilotage (adr/0013) -------------------------------------------------

    async def apercu(self) -> dict[str, Any]:
        data: dict[str, Any] = await self._get("agent/apercu")
        return data

    async def equipements(self, recherche: str | None = None) -> list[dict[str, Any]]:
        params = {"recherche": recherche} if recherche else {}
        data: list[dict[str, Any]] = await self._get("agent/equipements", **params)
        return data

    async def valider_entretien(self, body: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("POST", "agent/entretiens/valider", json=body)
        return data

    async def creer_entretien(self, body: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("POST", "agent/entretiens", json=body)
        return data

    async def creer_equipement(self, body: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("POST", "agent/equipements", json=body)
        return data

    async def consigner_intervention(self, body: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("POST", "agent/interventions", json=body)
        return data


async def _detail(response: aiohttp.ClientResponse) -> str:
    """Le message du backend, ou a defaut quelque chose d'exploitable.

    FastAPI renvoie `{"detail": "..."}` pour nos refus, mais `detail` devient
    une liste d'objets quand c'est la validation Pydantic qui a parle : les deux
    formes doivent ressortir en une phrase.
    """
    try:
        corps = await response.json()
    except (aiohttp.ClientError, ValueError):
        return f"L'add-on MaBarak a refuse la demande (code {response.status})."

    detail = corps.get("detail") if isinstance(corps, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        # Pydantic prefixe ses messages de « Value error, » : un agent n'a que
        # faire de savoir quelle couche a parle, seule la phrase l'interesse.
        # En revanche le nom du champ, lui, vit dans `loc` : sans lui, « Field
        # required » ne dit pas lequel, et l'agent ne peut pas se corriger.
        raisons = [
            _raison(item) for item in detail if isinstance(item, dict) and item.get("msg")
        ]
        if raisons:
            return " ".join(raisons)
    return f"L'add-on MaBarak a refuse la demande (code {response.status})."


def _raison(item: dict[str, Any]) -> str:
    """Un message de validation Pydantic, rendu au champ qu'il concerne."""
    message = str(item["msg"]).removeprefix("Value error, ")
    # `loc` vaut ("body", "champ") ; « body » ne veut rien dire pour un agent.
    champ = ".".join(
        str(morceau) for morceau in item.get("loc") or () if morceau not in ("body", "query")
    )
    return f"Champ « {champ} » : {message}" if champ else message
