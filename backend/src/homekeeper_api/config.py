"""Configuration de l'application, lue depuis l'environnement."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Nom du produit. Point de renommage unique cote backend
# (cf. docs/ARCHITECTURE.md, section « Renommage du produit »).
APP_NAME = "HomeKeeper"

# Version du contrat expose a l'integration Home Assistant sur /api/ha/summary.
#
# L'add-on et l'integration se mettent a jour independamment chez l'utilisateur
# (ADR-0005). Le coordinator lit cette valeur au premier appel et signale une
# incompatibilite explicite plutot que d'echouer de facon obscure.
# A incrementer uniquement pour un changement incompatible, jamais pour un ajout
# de champ.
API_SCHEMA_VERSION = 1

LogLevel = Literal["trace", "debug", "info", "notice", "warning", "error", "fatal"]


class Settings(BaseSettings):
    """Reglages runtime, surchargeables par variables d'environnement `HOMEKEEPER_*`."""

    model_config = SettingsConfigDict(
        env_prefix="HOMEKEEPER_",
        env_file=".env",
        extra="ignore",
    )

    # Seul repertoire persistant de l'add-on, et seul inclus dans les sauvegardes
    # Home Assistant. En developpement local, pointe vers un dossier temporaire.
    data_dir: Path = Field(default=Path("/data"))

    # Build Vite du frontend. Absent en developpement : l'application est alors
    # servie par le serveur de developpement Vite.
    frontend_dir: Path = Field(default=Path("/usr/share/homekeeper/www"))

    log_level: LogLevel = "info"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "homekeeper.db"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    """Instance unique, mise en cache. Surchargee dans les tests."""
    return Settings()
