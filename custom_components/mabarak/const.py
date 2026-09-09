"""Constantes de l'integration MaBarak."""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

# Point de renommage unique cote integration. Attention : `DOMAIN` ne peut plus
# changer apres la premiere publication sans casser les installations existantes
# (cf. docs/ARCHITECTURE.md, section « Renommage du produit »).
DOMAIN: Final = "mabarak"
NAME: Final = "MaBarak"

# Nom du service de l'add-on tel que le Supervisor le resout.
DEFAULT_HOST: Final = "a0d7b954-mabarak"
DEFAULT_PORT: Final = 8099

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"

# Les donnees ne changent qu'a l'action de l'utilisateur ou au passage d'une
# echeance : interroger plus souvent n'apporterait rien.
UPDATE_INTERVAL: Final = timedelta(minutes=5)

# Version du contrat `/api/ha/summary` attendue par cette integration.
# L'add-on et l'integration se mettent a jour separement chez l'utilisateur
# (ADR-0005) : une version d'add-on plus ancienne doit etre signalee clairement
# plutot que de produire une erreur incomprehensible.
SUPPORTED_API_SCHEMA_VERSION: Final = 1
