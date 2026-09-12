"""Modeles de la surface de pilotage par agent externe (adr/0013).

Ces modeles sont volontairement distincts de ceux de l'interface. L'interface
envoie des identifiants parce qu'elle vient de les afficher ; un agent, lui,
n'a que des noms et des tournures de langue. Reutiliser `AssetIn` ou `TaskIn`
aurait impose a l'agent de connaitre `recurrence_type`, `fixed_month` et
`recurrence_anchor` : trois notions internes qu'il n'a aucun moyen de deviner.

Les noms de champs sont en francais, comme le reste du produit : ils sont lus
par un modele de langue, qui n'a pas de documentation a cote.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

UniteFrequence = Literal["jours", "mois", "ans"]
TypeIntervention = Literal["entretien", "reparation", "installation", "controle", "remplacement"]

# La table stocke l'anglais (schema.sql) ; l'agent parle la langue du produit.
TYPE_INTERVENTION_SQL: dict[str, str] = {
    "entretien": "maintenance",
    "reparation": "repair",
    "installation": "installation",
    "controle": "inspection",
    "remplacement": "replacement",
}


class EntretienResume(BaseModel):
    nom: str
    statut: Literal["ok", "due_soon", "overdue", "unscheduled"]
    echeance: str | None = None
    jours_restants: int | None = None
    derniere_fois: str | None = None
    frequence: str


class EquipementResume(BaseModel):
    nom: str
    type: Literal["equipement", "element de construction"]
    lieu: str | None = None
    marque: str | None = None
    modele: str | None = None
    numero_de_serie: str | None = None
    date_installation: str | None = None
    garantie_jusqu_au: str | None = None
    statut_entretien: Literal["ok", "due_soon", "overdue", "unscheduled"]
    entretiens: list[EntretienResume] = Field(default_factory=list)


class EcheanceResume(BaseModel):
    entretien: str
    equipement: str | None = None
    echeance: str
    jours_restants: int


class Compteurs(BaseModel):
    en_retard: int = 0
    bientot: int = 0
    a_jour: int = 0
    sans_echeance: int = 0


class GarantieResume(BaseModel):
    equipement: str
    fin: str


class Apercu(BaseModel):
    """Tout ce qu'un agent doit savoir pour repondre « ou en est la maison ? »."""

    maison: str
    compteurs: Compteurs
    en_retard: list[EcheanceResume] = Field(default_factory=list)
    prochains: list[EcheanceResume] = Field(default_factory=list)
    garanties_qui_expirent: list[GarantieResume] = Field(default_factory=list)
    lieux: list[str] = Field(default_factory=list)
    nombre_equipements: int = 0


class ValiderEntretienIn(BaseModel):
    entretien: str = Field(min_length=1)
    # Facultatif, mais c'est lui qui leve l'ambiguite quand deux equipements
    # ont un entretien du meme nom — « changer le filtre », par exemple.
    equipement: str | None = None
    date: str | None = None
    fait_par: str | None = None
    notes: str | None = None
    montant_euros: float | None = Field(default=None, gt=0)


class Frequence(BaseModel):
    """La recurrence telle qu'un humain l'enonce, pas telle que la base la range.

    Une seule des trois formes a la fois. Aucune n'est obligatoire : un entretien
    sans frequence existe et se valide, il n'a simplement pas d'echeance.
    """

    tous_les: int | None = Field(default=None, ge=1)
    unite: UniteFrequence | None = None
    chaque_annee_le: str | None = Field(default=None, pattern=r"^\d{2}-\d{2}$")
    le: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Saison (adr/0010) : la tonte revient toutes les semaines, mais de mars a
    # octobre. Sans ces bornes elle s'afficherait en retard tout l'hiver.
    saison_du_mois: int | None = Field(default=None, ge=1, le=12)
    saison_au_mois: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def _une_seule_forme(self) -> Self:
        formes = [
            self.tous_les is not None or self.unite is not None,
            self.chaque_annee_le is not None,
            self.le is not None,
        ]
        if sum(formes) > 1:
            raise ValueError(
                "Une seule facon de dire la frequence a la fois : soit « tous les X mois », "
                "soit « chaque annee le JJ-MM », soit une date unique."
            )
        if (self.tous_les is None) != (self.unite is None):
            raise ValueError(
                "Indiquez les deux : le nombre et l'unite, par exemple tous_les=6 et unite=mois."
            )
        if (self.saison_du_mois is None) != (self.saison_au_mois is None):
            raise ValueError(
                "Une saison a deux bornes : indiquez le mois de debut ET celui de fin."
            )
        if self.saison_du_mois is not None and self.tous_les is None:
            raise ValueError(
                "Une saison ne s'applique qu'a un entretien qui revient tous les X jours/mois/ans."
            )
        return self


class CreerEntretienIn(BaseModel):
    equipement: str = Field(min_length=1)
    nom: str = Field(min_length=1)
    frequence: Frequence = Field(default_factory=Frequence)
    priorite: Literal["low", "normal", "high", "critical"] = "normal"
    derniere_fois: str | None = None
    notes: str | None = None
    # Un membre du foyer ou un prestataire, resolu par son nom dans l'annuaire.
    responsable: str | None = None


class CreerEquipementIn(BaseModel):
    nom: str = Field(min_length=1)
    type: Literal["equipement", "element de construction"] = "equipement"
    lieu: str | None = None
    # Garde-fou volontaire : un agent qui se trompe de nom de piece creerait un
    # doublon silencieux dans l'arbre des lieux. Creer un lieu doit etre voulu.
    creer_le_lieu: bool = False
    marque: str | None = None
    modele: str | None = None
    numero_de_serie: str | None = None
    date_achat: str | None = None
    date_installation: str | None = None
    notes: str | None = None
    garantie_mois: int | None = Field(default=None, gt=0)


class ConsignerInterventionIn(BaseModel):
    """Une intervention hors entretien planifie : une panne, une reparation.

    Distincte de `ValiderEntretienIn`, qui suppose un entretien recurrent a
    replanifier. Ici il n'y a rien a replanifier, seulement a consigner.
    """

    equipement: str = Field(min_length=1)
    type: TypeIntervention = "reparation"
    date: str | None = None
    fait_par: str | None = None
    notes: str | None = None
    montant_euros: float | None = Field(default=None, gt=0)


class ActionOut(BaseModel):
    """Reponse d'une ecriture.

    `message` est une phrase francaise complete, et non un statut : c'est elle
    que l'agent relira a l'utilisateur, et elle doit tenir seule.
    """

    message: str
    equipement: str | None = None
    entretien: str | None = None
    prochaine_echeance: str | None = None
