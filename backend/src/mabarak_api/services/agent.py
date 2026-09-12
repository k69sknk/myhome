"""Ce qui separe le vocabulaire d'un agent de celui de la base (adr/0013).

Deux traductions vivent ici, et nulle part ailleurs :

* **des noms vers des fiches** — via `resolve.py`, en refusant de trancher
  plutot qu'en devinant ;
* **de la frequence dite vers la recurrence stockee** — « tous les six mois »
  vers `recurrence_type='months', recurrence_interval=6`, et retour, parce que
  l'agent qui relit un entretien doit pouvoir le dire en francais.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from ..models import Asset, Location, MaintenanceTask, Member, Provider
from ..schemas.agent import Frequence
from ..services.catalog import location_path
from ..services.recurrence import RecurrenceType
from .resolve import Candidat, ResolutionError, resolve

# Marqueur de provenance ecrit dans `created_via` (migration 0014).
VIA_AGENT = "agent"

_MOIS = (
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
)


# --- Frequence ---------------------------------------------------------------


class FrequenceInvalideError(ValueError):
    pass


def recurrence_depuis_frequence(
    frequence: Frequence,
) -> tuple[RecurrenceType, int | None, int | None, int | None, str | None]:
    """(type, intervalle, mois_fixe, jour_fixe, date_unique) pour `plan_task`."""
    if frequence.tous_les is not None and frequence.unite is not None:
        unites: dict[str, RecurrenceType] = {
            "jours": "days",
            "mois": "months",
            "ans": "years",
        }
        return unites[frequence.unite], frequence.tous_les, None, None, None

    if frequence.chaque_annee_le is not None:
        jour_texte, mois_texte = frequence.chaque_annee_le.split("-")
        jour, mois = int(jour_texte), int(mois_texte)
        if not 1 <= mois <= 12 or not 1 <= jour <= 31:
            raise FrequenceInvalideError(
                f"« {frequence.chaque_annee_le} » n'est pas une date valide. "
                "Le format attendu est JJ-MM, par exemple 15-03 pour le 15 mars."
            )
        return "annual_fixed", None, mois, jour, None

    if frequence.le is not None:
        try:
            date.fromisoformat(frequence.le)
        except ValueError as err:
            raise FrequenceInvalideError(
                f"« {frequence.le} » n'est pas une date valide (format attendu : AAAA-MM-JJ)."
            ) from err
        return "custom_date", None, None, None, frequence.le

    return "none", None, None, None, None


def frequence_en_francais(task: MaintenanceTask) -> str:
    """La recurrence relue comme on la dirait, saison comprise."""
    base: str
    match task.recurrence_type:
        case "days" | "months" | "years":
            intervalle = task.recurrence_interval or 1
            # « tous les » commande le pluriel dans les deux cas : « tous les ans »
            # et non « tous les an ». Seul « mois » est invariable.
            pluriel = {"days": "jours", "months": "mois", "years": "ans"}[task.recurrence_type]
            base = f"tous les {pluriel}" if intervalle == 1 else f"tous les {intervalle} {pluriel}"
        case "annual_fixed":
            mois = _MOIS[(task.fixed_month or 1) - 1]
            base = f"chaque annee le {task.fixed_day or 1} {mois}"
        case "custom_date":
            base = f"une seule fois, le {task.custom_due_date}"
        case _:
            return "aucune frequence definie"

    if task.season_start_month is not None and task.season_end_month is not None:
        debut = _MOIS[task.season_start_month - 1]
        fin = _MOIS[task.season_end_month - 1]
        return f"{base}, de {debut} a {fin}"
    return base


# --- Resolution contre la base -----------------------------------------------


def _equipements(session: Session, home_id: int) -> list[Asset]:
    return list(
        session.scalars(
            select(Asset)
            .where(Asset.home_id == home_id, Asset.status != "removed")
            .options(selectinload(Asset.tasks), selectinload(Asset.warranty))
            .order_by(Asset.name)
        ).all()
    )


def resoudre_equipement(session: Session, home_id: int, nom: str) -> Asset:
    """L'equipement que designe `nom`, ou une `ResolutionError` explicite."""
    assets = _equipements(session, home_id)
    candidats = [
        Candidat(id=asset.id, nom=asset.name, precision=location_path(session, asset.location_id))
        for asset in assets
    ]
    choisi = resolve(nom, candidats, quoi="equipement", precision="la piece ou il se trouve")
    par_id = {asset.id: asset for asset in assets}
    return par_id[choisi.id]


def taches_de_la_maison(session: Session, home_id: int) -> list[MaintenanceTask]:
    """Tous les entretiens actifs, ceux d'une fiche comme ceux de la maison.

    La jointure est externe pour la meme raison que dans `/api/tasks` : un
    entretien peut etre rattache a la maison plutot qu'a un equipement
    (« tester les detecteurs de fumee »). Une jointure interne les ferait
    disparaitre de la recherche alors qu'ils figurent au planning.
    """
    return list(
        session.scalars(
            select(MaintenanceTask)
            .join(Asset, MaintenanceTask.asset_id == Asset.id, isouter=True)
            .where(
                MaintenanceTask.is_active == 1,
                or_(
                    and_(
                        MaintenanceTask.asset_id.is_not(None),
                        Asset.home_id == home_id,
                        Asset.status != "removed",
                    ),
                    MaintenanceTask.home_id == home_id,
                ),
            )
            .options(selectinload(MaintenanceTask.asset))
            .order_by(MaintenanceTask.name)
        ).all()
    )


def resoudre_entretien(
    session: Session, home_id: int, nom: str, equipement: str | None
) -> MaintenanceTask:
    """L'entretien que designe `nom`, restreint a un equipement s'il est donne.

    Sans equipement, la recherche porte sur toute la maison : c'est ce qui
    permet de dire « marque le ramonage comme fait » sans savoir a quelle fiche
    il est rattache. Le prix est une ambiguite plus frequente — « changer le
    filtre » existe sur trois appareils — que le message d'erreur invite alors
    a lever en nommant l'equipement.
    """
    if equipement is not None:
        asset = resoudre_equipement(session, home_id, equipement)
        taches = [task for task in asset.tasks if task.is_active]
        candidats = [Candidat(id=task.id, nom=task.name) for task in taches]
        choisi = resolve(nom, candidats, quoi=f"entretien de « {asset.name} »")
        return next(task for task in taches if task.id == choisi.id)

    taches = taches_de_la_maison(session, home_id)
    candidats = [
        Candidat(
            id=task.id,
            nom=task.name,
            precision=task.asset.name if task.asset is not None else "la maison",
        )
        for task in taches
    ]
    choisi = resolve(nom, candidats, quoi="entretien", precision="le nom de l'equipement")
    return next(task for task in taches if task.id == choisi.id)


def resoudre_lieu(session: Session, home_id: int, nom: str) -> Location:
    lieux = list(
        session.scalars(
            select(Location).where(Location.home_id == home_id).order_by(Location.name)
        ).all()
    )
    candidats = [
        Candidat(id=lieu.id, nom=lieu.name, precision=location_path(session, lieu.parent_id))
        for lieu in lieux
    ]
    choisi = resolve(nom, candidats, quoi="lieu")
    return next(lieu for lieu in lieux if lieu.id == choisi.id)


def resoudre_intervenant(
    session: Session, home_id: int, nom: str
) -> tuple[Member | None, Provider | None, str]:
    """Qui a fait l'entretien : un membre, un prestataire, ou du texte libre.

    Le texte libre est le cas normal et non un echec : « le voisin » n'a pas de
    fiche et n'en merite pas. On ne rattache a l'annuaire que si le nom y
    correspond sans ambiguite — c'est ce qui evite qu'une meme entreprise
    s'ecrive de trois facons dans l'historique, sans pour autant obliger a
    creer une fiche pour un coup de main.
    """
    membres = list(
        session.scalars(select(Member).where(Member.home_id == home_id).order_by(Member.name)).all()
    )
    prestataires = list(
        session.scalars(
            select(Provider).where(Provider.home_id == home_id).order_by(Provider.name)
        ).all()
    )
    # Membres et prestataires vivent dans deux tables (adr/0011) et leurs
    # identifiants se recouvrent : on resout sur la position dans la liste
    # concatenee, seule clef qui soit unique des deux cotes.
    fiches: list[Member | Provider] = [*membres, *prestataires]
    candidats = [Candidat(id=rang, nom=fiche.name) for rang, fiche in enumerate(fiches)]

    try:
        choisi = resolve(nom, candidats, quoi="intervenant")
    except ResolutionError:
        return None, None, nom.strip()

    fiche = fiches[choisi.id]
    if isinstance(fiche, Member):
        return fiche, None, fiche.name
    return None, fiche, fiche.name
