"""Application des migrations Alembic.

Expose la commande `homekeeper-migrate`, appelee par le service s6
`init-homekeeper` avant tout demarrage de l'API. Les migrations sont jouees a
chaque demarrage de l'add-on : c'est ce qui rend sure une mise a jour, y compris
apres plusieurs versions sautees.
"""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import get_settings

_LOGGER = logging.getLogger(__name__)


def alembic_config() -> Config:
    """Construit la configuration Alembic depuis le paquet installe.

    Le repertoire de migrations est resolu par rapport a ce module, et non par
    rapport au repertoire courant : dans le conteneur, seul le paquet installe
    existe et il n'y a pas d'alembic.ini a la racine.
    """
    settings = get_settings()
    script_location = Path(__file__).parent / "alembic"

    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_to_head() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(), "head")


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
