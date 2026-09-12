"""Les actions de pilotage, definies une seule fois (adr/0013).

Elles sont exposees sous **deux formes**, pour une raison de plomberie qui
merite d'etre ecrite ici plutot que redecouverte plus tard :

* en **services** `mabarak.*`, appelables depuis une automatisation, un script,
  ou l'API REST de Home Assistant ;
* en **intentions**, parce que le serveur MCP de Home Assistant n'expose que
  l'API « Assist » — c'est-a-dire les intentions enregistrees — et jamais les
  services. Un agent branche en MCP ne verrait donc aucun service `mabarak.*`.

Les deux surfaces appellent ce module ; ni `services.py` ni `intents.py` ne
contiennent de logique propre. Ajouter une action ailleurs qu'ici, c'est la
rendre invisible a la moitie des agents.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol

from .api import MaBarakClient

# Les champs de frequence sont a plat dans les services et les intentions — un
# agent remplit mal un objet imbrique — et regroupes pour le backend.
_CHAMPS_FREQUENCE = (
    "tous_les",
    "unite",
    "chaque_annee_le",
    "le",
    "saison_du_mois",
    "saison_au_mois",
)


def _corps(donnees: Mapping[str, Any]) -> dict[str, Any]:
    """Les champs renseignes, tels quels.

    Les absents sont retires plutot qu'envoyes a `None` : le backend distingue
    « non precise » de « explicitement vide », notamment sur la date.
    """
    return {cle: valeur for cle, valeur in donnees.items() if valeur is not None}


def _corps_avec_frequence(donnees: Mapping[str, Any]) -> dict[str, Any]:
    corps = _corps({k: v for k, v in donnees.items() if k not in _CHAMPS_FREQUENCE})
    corps["frequence"] = _corps({k: donnees.get(k) for k in _CHAMPS_FREQUENCE})
    return corps


def _phrase_apercu(donnees: Mapping[str, Any]) -> str:
    """L'apercu resume en une phrase, avant le detail structure.

    Un agent lit d'abord cette phrase : elle doit suffire a repondre « est-ce
    que quelque chose presse ? » sans deplier les listes.
    """
    compteurs = donnees.get("compteurs", {})
    retard = compteurs.get("en_retard", 0)
    bientot = compteurs.get("bientot", 0)
    maison = donnees.get("maison", "La maison")

    if retard == 0 and bientot == 0:
        return f"{maison} : aucun entretien en retard ni a echeance proche."

    morceaux = []
    if retard:
        morceaux.append(f"{retard} entretien{'s' if retard > 1 else ''} en retard")
    if bientot:
        morceaux.append(f"{bientot} a echeance proche")
    phrase = f"{maison} : " + ", ".join(morceaux) + "."

    if donnees.get("en_retard"):
        premier = donnees["en_retard"][0]
        ou = f" sur « {premier['equipement']} »" if premier.get("equipement") else ""
        phrase += f" Le plus ancien est « {premier['entretien']} »{ou}, du {premier['echeance']}."
    return phrase


def _phrase_equipements(donnees: Any) -> str:
    if not isinstance(donnees, list) or not donnees:
        return "Aucun equipement ne correspond."
    if len(donnees) == 1:
        fiche = donnees[0]
        ou = f", {fiche['lieu']}" if fiche.get("lieu") else ""
        nombre = len(fiche.get("entretiens", []))
        if nombre > 1:
            entretiens = f" {nombre} entretiens y sont rattaches."
        elif nombre == 1:
            entretiens = " Un entretien y est rattache."
        else:
            entretiens = " Aucun entretien ne lui est rattache."
        return f"« {fiche['nom']} »{ou}.{entretiens}"
    noms = ", ".join(fiche["nom"] for fiche in donnees[:10])
    reste = len(donnees) - 10
    return f"{len(donnees)} equipements : {noms}" + (f", et {reste} autres." if reste > 0 else ".")


# Le serveur MCP de Home Assistant construit `inputSchema` avec `type` et
# `properties`, et **jette la liste `required`** (voir `mcp_server/server.py`,
# `_format_tool`). Un agent branche en MCP ne peut donc pas savoir qu'un champ
# est obligatoire — sauf si la description le dit. Elle, elle est transmise.
MENTION_OBLIGATOIRE = "Obligatoire. "


def _obligations_dans_les_descriptions(schema: dict[Any, Any]) -> dict[Any, Any]:
    """Prefixe la description de chaque champ requis par « Obligatoire. ».

    Applique a la definition et non a la main : un champ passe plus tard de
    `Optional` a `Required` verrait sinon sa mention rester fausse.
    """
    documente: dict[Any, Any] = {}
    for marqueur, validateur in schema.items():
        if isinstance(marqueur, vol.Required) and not (marqueur.description or "").startswith(
            MENTION_OBLIGATOIRE
        ):
            marqueur = vol.Required(
                marqueur.schema,
                description=f"{MENTION_OBLIGATOIRE}{marqueur.description or ''}".strip(),
            )
        documente[marqueur] = validateur
    return documente


@dataclass(frozen=True)
class Action:
    """Une action de pilotage, avec tout ce que les deux surfaces demandent.

    `schema` est partage : c'est lui qui devient la validation du service, et
    la description des parametres de l'outil MCP cote intention. Les
    descriptions portees par `vol.Optional(..., description=...)` ne sont donc
    pas decoratives — elles sont la seule documentation que l'agent recevra.
    """

    nom: str
    description: str
    schema: dict[Any, Any]
    appel: Callable[[MaBarakClient, dict[str, Any]], Awaitable[Any]]
    # Une action qui ne fait que lire : le service se declare en lecture seule,
    # et Home Assistant l'autorise sans confirmation.
    lecture_seule: bool = False
    construire: Callable[[Mapping[str, Any]], dict[str, Any]] = field(default=_corps)
    # Ce que l'agent entendra. La reponse structuree suit, mais c'est cette
    # phrase qui sera relue a l'utilisateur.
    phrase: Callable[[Any], str] = field(default=lambda donnees: str(donnees.get("message", "")))

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema", _obligations_dans_les_descriptions(self.schema))


_DATE = vol.Match(
    r"^\d{4}-\d{2}-\d{2}$",
    msg="La date doit s'ecrire AAAA-MM-JJ, par exemple 2026-03-15.",
)

ACTIONS: tuple[Action, ...] = (
    Action(
        nom="apercu",
        description=(
            "Donne l'etat d'entretien de la maison enregistre dans MaBarak : entretiens en "
            "retard, echeances a venir, garanties qui expirent, liste des pieces et nombre "
            "d'equipements. A appeler en premier pour savoir de quoi la maison est faite."
        ),
        schema={},
        appel=lambda client, _: client.apercu(),
        lecture_seule=True,
        phrase=_phrase_apercu,
    ),
    Action(
        nom="chercher_equipement",
        description=(
            "Cherche des equipements dans MaBarak et rend leur fiche complete : lieu, marque, "
            "modele, numero de serie, garantie, et la liste de leurs entretiens avec frequence "
            "et prochaine echeance. Sans terme de recherche, rend tous les equipements."
        ),
        schema={
            vol.Optional(
                "recherche",
                description="Terme a chercher dans le nom, la marque ou le modele.",
            ): vol.All(str, vol.Length(min=1)),
        },
        appel=lambda client, corps: client.equipements(corps.get("recherche")),
        lecture_seule=True,
        phrase=_phrase_equipements,
    ),
    Action(
        nom="valider_entretien",
        description=(
            "Enregistre dans MaBarak qu'un entretien recurrent a ete realise, et calcule sa "
            "prochaine echeance. L'entretien est designe par son nom ; si plusieurs "
            "equipements ont un entretien du meme nom, precisez l'equipement."
        ),
        schema={
            vol.Required(
                "entretien",
                description="Nom de l'entretien realise, par exemple « ramonage ».",
            ): vol.All(str, vol.Length(min=1)),
            vol.Optional(
                "equipement",
                description=(
                    "Nom de l'equipement concerne. A preciser seulement si le nom de "
                    "l'entretien est ambigu."
                ),
            ): str,
            vol.Optional(
                "date", description="Date de realisation (AAAA-MM-JJ). Par defaut, aujourd'hui."
            ): _DATE,
            vol.Optional(
                "fait_par",
                description=(
                    "Qui l'a fait. Rattache automatiquement au membre du foyer ou au "
                    "prestataire de l'annuaire si le nom y correspond."
                ),
            ): str,
            vol.Optional("notes", description="Ce qui a ete constate ou fait."): str,
            vol.Optional("montant_euros", description="Cout en euros, si l'entretien a coute."): (
                vol.Coerce(float)
            ),
        },
        appel=lambda client, corps: client.valider_entretien(corps),
    ),
    Action(
        nom="creer_entretien",
        description=(
            "Ajoute un entretien recurrent a un equipement existant de MaBarak. La frequence "
            "s'exprime d'UNE seule facon : soit tous_les + unite, soit chaque_annee_le, soit "
            "une date unique. Sans frequence, l'entretien existe mais n'a pas d'echeance."
        ),
        schema={
            vol.Required(
                "equipement", description="Nom de l'equipement auquel rattacher l'entretien."
            ): vol.All(str, vol.Length(min=1)),
            vol.Required(
                "nom", description="Nom de l'entretien, par exemple « changer le filtre »."
            ): vol.All(str, vol.Length(min=1)),
            vol.Optional(
                "tous_les", description="Nombre d'unites entre deux passages. Exige « unite »."
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                "unite", description="Unite de la frequence. Exige « tous_les »."
            ): vol.In(["jours", "mois", "ans"]),
            vol.Optional(
                "chaque_annee_le",
                description="Jour et mois fixes au format JJ-MM, par exemple 15-09.",
            ): vol.Match(r"^\d{2}-\d{2}$", msg="Le format attendu est JJ-MM, par exemple 15-09."),
            vol.Optional(
                "le", description="Date unique (AAAA-MM-JJ) pour un entretien ponctuel."
            ): _DATE,
            vol.Optional(
                "saison_du_mois",
                description=(
                    "Mois de debut de saison (1-12). La tonte revient toutes les semaines, "
                    "mais de mars a octobre : hors saison, aucune echeance n'est calculee."
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
            vol.Optional("saison_au_mois", description="Mois de fin de saison (1-12)."): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=12)
            ),
            vol.Optional("priorite", description="Priorite de l'entretien."): vol.In(
                ["low", "normal", "high", "critical"]
            ),
            vol.Optional(
                "derniere_fois",
                description=(
                    "Date du dernier passage (AAAA-MM-JJ), si connue. Sert a calculer la "
                    "premiere echeance."
                ),
            ): _DATE,
            vol.Optional("notes", description="Precisions sur l'entretien."): str,
            vol.Optional(
                "responsable",
                description=(
                    "Membre du foyer ou prestataire en charge. Doit exister dans l'annuaire."
                ),
            ): str,
        },
        appel=lambda client, corps: client.creer_entretien(corps),
        construire=_corps_avec_frequence,
    ),
    Action(
        nom="creer_equipement",
        description=(
            "Cree une fiche d'equipement dans MaBarak. Le lieu doit deja exister ; pour le "
            "creer au passage, mettez creer_le_lieu a vrai — sinon un nom de piece mal "
            "orthographie produirait un doublon."
        ),
        schema={
            vol.Required(
                "nom", description="Nom de l'equipement, par exemple « lave-linge »."
            ): vol.All(str, vol.Length(min=1)),
            vol.Optional(
                "type",
                description=(
                    "« equipement » pour un appareil, « element de construction » pour une "
                    "toiture, une facade, une fenetre."
                ),
            ): vol.In(["equipement", "element de construction"]),
            vol.Optional("lieu", description="Piece ou se trouve l'equipement."): str,
            vol.Optional(
                "creer_le_lieu",
                description="Creer la piece si elle n'existe pas. Faux par defaut.",
            ): vol.Coerce(bool),
            vol.Optional("marque", description="Marque."): str,
            vol.Optional("modele", description="Modele."): str,
            vol.Optional("numero_de_serie", description="Numero de serie."): str,
            vol.Optional("date_achat", description="Date d'achat (AAAA-MM-JJ)."): _DATE,
            vol.Optional(
                "date_installation", description="Date d'installation (AAAA-MM-JJ)."
            ): _DATE,
            vol.Optional("notes", description="Precisions libres."): str,
            vol.Optional(
                "garantie_mois",
                description="Duree de garantie en mois. La date de fin est calculee.",
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        },
        appel=lambda client, corps: client.creer_equipement(corps),
    ),
    Action(
        nom="consigner_intervention",
        description=(
            "Consigne dans l'historique MaBarak une intervention ponctuelle sur un equipement "
            "— une panne, une reparation, un controle — qui ne correspond a aucun entretien "
            "recurrent planifie. Pour un entretien planifie, utilisez plutot valider_entretien."
        ),
        schema={
            vol.Required("equipement", description="Nom de l'equipement concerne."): vol.All(
                str, vol.Length(min=1)
            ),
            vol.Optional("type", description="Nature de l'intervention."): vol.In(
                ["entretien", "reparation", "installation", "controle", "remplacement"]
            ),
            vol.Optional(
                "date", description="Date de l'intervention (AAAA-MM-JJ). Par defaut, aujourd'hui."
            ): _DATE,
            vol.Optional("fait_par", description="Qui est intervenu."): str,
            vol.Optional("notes", description="Ce qui a ete fait ou constate."): str,
            vol.Optional("montant_euros", description="Cout en euros."): vol.Coerce(float),
        },
        appel=lambda client, corps: client.consigner_intervention(corps),
    ),
    Action(
        nom="joindre_document",
        description=(
            "Rattache un document a la fiche d'un equipement dans MaBarak : facture, notice, "
            "garantie, contrat. Trois facons de le garder, et il en faut exactement une : "
            "« fichier_a_telecharger » pour que MaBarak en fasse une copie (l'adresse doit etre "
            "sur le reseau local), « lien » pour ne garder que l'adresse d'un document qui vit "
            "ailleurs, « note » pour dire simplement ou se trouve le papier."
        ),
        schema={
            vol.Required("equipement", description="Nom de l'equipement concerne."): vol.All(
                str, vol.Length(min=1)
            ),
            vol.Required(
                "nom", description="Nom du document, par exemple « Facture revision 2026 »."
            ): vol.All(str, vol.Length(min=1)),
            vol.Optional("type", description="Nature du document."): vol.In(
                [
                    "facture",
                    "notice",
                    "mode d'emploi",
                    "garantie",
                    "contrat",
                    "certificat",
                    "photo",
                    "autre",
                ]
            ),
            vol.Optional(
                "fichier_a_telecharger",
                description=(
                    "Adresse a laquelle MaBarak ira chercher le fichier pour en garder une "
                    "copie. Doit etre sur le reseau local : MaBarak ne telecharge rien depuis "
                    "Internet. Formats acceptes : pdf, jpg, png, heic, doc, docx ; 10 Mo au plus."
                ),
            ): str,
            vol.Optional(
                "lien",
                description=(
                    "Adresse du document, gardee telle quelle, sans copie. C'est le bon choix "
                    "pour un document qui vit deja ailleurs."
                ),
            ): str,
            vol.Optional(
                "note",
                description=(
                    "Ou se trouve le document, en clair — « classeur bleu, intercalaire 3 ». "
                    "Pour un papier qui n'existe qu'en papier."
                ),
            ): str,
            vol.Optional("commentaire", description="Precision libre sur ce document."): str,
        },
        appel=lambda client, corps: client.joindre_document(corps),
    ),
)


async def executer(client: MaBarakClient, action: Action, donnees: Mapping[str, Any]) -> Any:
    """Joue une action et rend la reponse brute de l'add-on."""
    return await action.appel(client, action.construire(donnees))
