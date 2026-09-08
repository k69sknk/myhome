"""Client HTTP de l'add-on HomeKeeper."""

from __future__ import annotations

from typing import Any

import aiohttp
from yarl import URL


class HomeKeeperError(Exception):
    """Erreur generique de communication avec l'add-on."""


class HomeKeeperConnectionError(HomeKeeperError):
    """L'add-on est injoignable."""


class HomeKeeperIncompatibleError(HomeKeeperError):
    """La version de contrat de l'add-on n'est pas supportee."""


class HomeKeeperClient:
    """Acces en lecture a l'API de l'add-on.

    L'add-on n'expose aucune authentification : il n'est joignable que depuis le
    reseau interne de Home Assistant, et son propre filtrage d'adresse IP le
    protege (docs/ARCHITECTURE.md section 4).
    """

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        self._base = URL.build(scheme="http", host=host, port=port) / "api"
        self._session = session

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._base / path,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeKeeperConnectionError(str(err)) from err
        return data

    async def health(self) -> dict[str, Any]:
        return await self._get("health")

    async def summary(self) -> dict[str, Any]:
        return await self._get("ha/summary")
