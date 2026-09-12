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

# Repli de saisie manuelle. Le chemin normal est la decouverte : l'add-on
# s'annonce au Supervisor avec son vrai nom d'hote au demarrage (adr/0014), et
# `async_step_hassio` le recoit sans que personne ait a le taper.
#
# Le Supervisor resout un add-on a son slug, tirets a la place des soulignes
# (`hassio.hostname_from_addon_slug`), et ce slug porte en prefixe un hash du
# **depot** d'origine. `b34ff0a4` est celui de github.com/k69sknk/myhome : il
# vaut donc pour toute installation faite depuis ce depot, et changerait si le
# depot demenageait. La valeur precedente, `a0d7b954`, etait celle du depot
# Community Add-ons — fausse pour tout le monde, tout le temps.
DEFAULT_HOST: Final = "b34ff0a4-mabarak"
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
