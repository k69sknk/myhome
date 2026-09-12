"""Retrouver une fiche a partir du nom qu'un humain lui donne.

Un agent externe ne connait pas les identifiants : il dit « la chaudiere », pas
`asset_id=42`. Tout le pilotage de MaBarak depuis Home Assistant (adr/0013)
repose donc sur ce module.

Le parti pris tient en une phrase : **en cas de doute, ne pas choisir**. Une
correspondance approximative qui se trompe de fiche ecrit dans l'historique de
la maison, et personne ne s'en apercoit. Une ambiguite signalee, elle, se
rattrape immediatement — un agent sait quoi faire d'une liste de candidats,
il ne sait pas defaire une ecriture silencieuse.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

# Au-dela, la liste cesse d'aider a choisir et encombre la reponse.
MAX_CANDIDATS = 12


def fold(value: str) -> str:
    """Forme comparable : sans accent, sans casse, sans espaces superflus.

    « Chaudière » et « chaudiere » designent le meme appareil ; l'agent qui
    dicte n'a aucune raison de connaitre l'orthographe exacte de la fiche.
    """
    sans_accent = unicodedata.normalize("NFKD", value)
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    return " ".join(sans_accent.casefold().split())


def _mots(value: str) -> list[str]:
    # Les mots d'un seul caractere ne discriminent rien et font matcher trop
    # large : « l' » de « l'aspirateur » ne doit pas peser dans la recherche.
    return [mot for mot in fold(value).replace("'", " ").split() if len(mot) > 1]


@dataclass(frozen=True)
class Candidat:
    """Une fiche joignable par son nom, avec de quoi la distinguer d'une autre."""

    id: int
    nom: str
    # Ce qui permet a l'humain de trancher entre deux homonymes : le lieu pour
    # un equipement, l'equipement pour un entretien.
    precision: str | None = None

    def etiquette(self) -> str:
        return f"{self.nom} ({self.precision})" if self.precision else self.nom


class ResolutionError(Exception):
    """Echec de resolution, avec un message directement lisible par un agent."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IntrouvableError(ResolutionError):
    pass


class AmbiguiteError(ResolutionError):
    def __init__(self, message: str, candidats: Sequence[Candidat]) -> None:
        super().__init__(message)
        self.candidats = list(candidats)


def _liste(candidats: Sequence[Candidat]) -> str:
    noms = [candidat.etiquette() for candidat in candidats[:MAX_CANDIDATS]]
    reste = len(candidats) - len(noms)
    texte = ", ".join(noms)
    return f"{texte}, et {reste} autres" if reste > 0 else texte


def resolve(
    requete: str,
    candidats: Sequence[Candidat],
    *,
    quoi: str,
    precision: str | None = None,
) -> Candidat:
    """Le candidat unique que designe `requete`, ou une erreur explicite.

    `quoi` nomme ce qu'on cherche au singulier (« equipement », « entretien ») :
    il n'apparait que dans les messages d'erreur, qui sont la vraie sortie de
    cette fonction quand elle echoue.
    """
    requete = requete.strip()
    if not requete:
        raise IntrouvableError(f"Indiquez le nom de l'{quoi} a rechercher.")
    if not candidats:
        raise IntrouvableError(f"Aucun {quoi} n'est enregistre dans MaBarak pour l'instant.")

    cible = fold(requete)

    # 1. Le nom exact gagne toujours, meme s'il est aussi le prefixe d'un autre :
    #    avec « Chaudiere » et « Chaudiere d'appoint », demander « chaudiere »
    #    designe la premiere sans ambiguite.
    exacts = [c for c in candidats if fold(c.nom) == cible]
    if len(exacts) == 1:
        return exacts[0]
    if len(exacts) > 1:
        raise AmbiguiteError(
            f"Plusieurs {quoi}s portent exactement le nom « {requete} » : "
            f"{_liste(exacts)}. Precisez lequel.",
            exacts,
        )

    # 2. Sinon, tous les mots de la requete doivent se retrouver dans le nom.
    #    « filtre pac » trouve « Changer le filtre de la PAC ».
    mots = _mots(requete)
    partiels = [c for c in candidats if mots and all(mot in fold(c.nom) for mot in mots)]

    # 3. En dernier recours, l'inverse : la requete est plus bavarde que la
    #    fiche. « la chaudiere gaz de la cave » doit trouver « Chaudiere gaz ».
    if not partiels:
        partiels = [c for c in candidats if fold(c.nom) and fold(c.nom) in cible]

    if len(partiels) == 1:
        return partiels[0]

    if len(partiels) > 1:
        indice = (
            f" Precisez, par exemple avec {precision}."
            if precision
            else " Reprenez le nom complet de celui que vous visez."
        )
        raise AmbiguiteError(
            f"Plusieurs {quoi}s correspondent a « {requete} » : {_liste(partiels)}.{indice}",
            partiels,
        )

    raise IntrouvableError(
        f"Aucun {quoi} ne correspond a « {requete} ». "
        f"Voici ce que MaBarak connait : {_liste(candidats)}."
    )
