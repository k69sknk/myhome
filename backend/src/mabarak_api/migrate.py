"""Application des migrations Alembic."""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import Settings, get_settings

_LOGGER = logging.getLogger(__name__)


def alembic_config(settings: Settings | None = None) -> Config:
    settings = settings or get_settings()
    script_location = Path(__file__).parent / "alembic"

    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_to_head(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(settings), "head")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        upgrade_to_head()
    except Exception:
        _LOGGER.exception("Echec de l'application des migrations")
        return 1
    _LOGGER.info("Base de donnees a jour")
    return 0


if __name__ == "__main__":
    sys.exit(main())
