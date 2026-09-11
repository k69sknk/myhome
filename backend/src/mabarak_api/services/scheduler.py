"""Le planificateur : une tache asyncio dans le cycle de vie de l'API (adr/0009).

Elle se reveille toutes les `TICK_SECONDS`, demande a `reminders.is_pass_due` si
un passage est attendu, et le lance le cas echeant. Le battement est court et la
decision porte sur la date et l'heure voulues, pas sur le rythme des reveils :
c'est ce qui permet a un add-on redemarre en cours de journee de rattraper le
passage manque au lieu de le sauter.

Tout le travail (SQLite, appels HTTP a Home Assistant) est synchrone et bloquant :
il est deporte dans un thread pour ne pas figer la boucle d'evenements qui sert
l'interface pendant ce temps.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from ..clock import local_now
from .home import ensure_home
from .reminders import ReminderConfigurationError, is_pass_due, run_reminders

_LOGGER = logging.getLogger(__name__)

# Assez fin pour tomber dans l'heure demandee, assez rare pour etre invisible sur
# un Raspberry Pi : 96 reveils par jour, dont un seul fait quelque chose.
TICK_SECONDS = 900

# Le premier passage attend que le demarrage soit fini : migrations appliquees,
# premieres requetes servies. Une minute ne change rien a un rappel quotidien, et
# evite au planificateur d'ouvrir la base pendant que l'add-on s'installe.
STARTUP_DELAY_SECONDS = 60

SessionFactory = Callable[[], Session]


def run_pass_if_due(session_factory: SessionFactory) -> bool:
    """Un passage de rappel, si l'heure est venue. Retourne vrai s'il a eu lieu.

    La date du passage est notee meme quand rien n'est parti (notifications
    coupees, aucun entretien du jour, Home Assistant injoignable) : sans cela, un
    add-on sans notifications relancerait la tentative a chaque battement.
    """
    session = session_factory()
    try:
        home = ensure_home(session)
        now = local_now()
        if not is_pass_due(home, now):
            session.rollback()
            return False

        home.last_reminder_run_on = now.date().isoformat()
        try:
            result = run_reminders(session, today=now.date())
        except ReminderConfigurationError:
            session.commit()
            return True

        if result.errors:
            _LOGGER.warning("Rappels : %s", " ".join(result.errors))
        _LOGGER.info(
            "Rappels : %d message(s) pour %d entretien(s), %d sans destinataire",
            result.sent,
            result.tasks,
            result.without_recipient,
        )
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def reminder_scheduler(session_factory: SessionFactory) -> None:
    """Boucle de fond, annulee a l'arret de l'application."""
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(run_pass_if_due, session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Une base verrouillee ou un lot de donnees inattendu ne doit pas tuer
            # le planificateur pour le reste de la vie du conteneur.
            _LOGGER.exception("Echec du passage de rappel, reprise au prochain reveil")
        await asyncio.sleep(TICK_SECONDS)
