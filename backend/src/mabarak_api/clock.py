"""Horodatages UTC, convention du schema (TEXT ISO 8601)."""

from datetime import UTC, date, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> date:
    return datetime.now(UTC).date()


def local_now() -> datetime:
    """Heure locale du conteneur, naive.

    Les dates stockees restent en UTC (convention du schema) ; cette fonction ne
    sert qu'aux rappels, ou c'est l'heure vue par l'habitant qui compte : recevoir
    « les entretiens de la semaine » a 8h du matin n'a de sens que dans SON fuseau.
    Le Supervisor propage le fuseau de Home Assistant au conteneur de l'add-on ;
    en developpement local, c'est celui de la machine.
    """
    return datetime.now()
