"""Catalogue de demarrage : pieces types, objets typiques et entretiens par defaut.

Le catalogue est du CONTENU LIVRE AVEC L'APPLICATION, pas des donnees utilisateur.
Il est lu depuis des fichiers YAML versionnes et n'est jamais ecrit en base : la
base ne recoit que les lieux, fiches et entretiens que l'utilisateur cree
reellement, a partir des modeles proposes ici. Voir adr/0008.

Consequence : enrichir le catalogue d'une version a l'autre ne demande aucune
migration et ne peut pas ecraser ce que l'utilisateur a personnalise.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, Field, model_validator

_CATALOG_DIR = Path(__file__).resolve().parent

# 'none' et 'custom_date' existent en base mais n'ont pas de sens pour un modele
# par defaut : un entretien propose est toujours recurrent.
RecurrenceType = Literal["days", "months", "years", "annual_fixed"]

AssetKind = Literal["equipment", "building_element"]


class CatalogRecurrence(BaseModel):
    """Recurrence d'un entretien type, calquee sur `maintenance_task`."""

    model_config = {"extra": "forbid"}

    type: RecurrenceType
    interval: int | None = Field(default=None, ge=1)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    # Fenetre de saison (adr/0010) : 'la tonte revient toutes les semaines, mais
    # de mars a octobre'. Les deux bornes ensemble ou aucune.
    season_start_month: int | None = Field(default=None, ge=1, le=12)
    season_end_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        # Memes regles que les CHECK de `maintenance_task` : un catalogue invalide
        # doit echouer ici, pas au moment de l'insertion chez l'utilisateur.
        if self.type == "annual_fixed":
            if self.month is None or self.day is None:
                raise ValueError("une recurrence 'annual_fixed' exige 'month' et 'day'")
            if self.interval is not None:
                raise ValueError("une recurrence 'annual_fixed' n'a pas d'intervalle")
            if self.season_start_month is not None or self.season_end_month is not None:
                # Une date fixe porte deja son mois : lui ajouter une saison, c'est
                # dire deux fois la meme chose, ou se contredire.
                raise ValueError("une recurrence 'annual_fixed' n'a pas de saison")
        else:
            if self.interval is None:
                raise ValueError(f"une recurrence '{self.type}' exige un 'interval'")
            if self.month is not None or self.day is not None:
                raise ValueError(f"une recurrence '{self.type}' n'a ni 'month' ni 'day'")
        if (self.season_start_month is None) != (self.season_end_month is None):
            raise ValueError("une saison exige 'season_start_month' ET 'season_end_month'")
        return self


class CatalogMaintenance(BaseModel):
    """Entretien propose par defaut, a la fin du didacticiel."""

    model_config = {"extra": "forbid"}

    key: str
    label: str
    description: str | None = None
    recurrence: CatalogRecurrence
    # Voir adr/0004 : 'from_due_date' pour tout ce qui est reglementaire ou
    # contractuel, qui ne doit pas deriver si l'utilisateur s'y prend en retard.
    anchor: Literal["from_completion", "from_due_date"] = "from_completion"
    preparation_notes: str | None = None


class CatalogItem(BaseModel):
    """Objet typique proposable dans une piece."""

    model_config = {"extra": "forbid"}

    key: str
    label: str
    kind: AssetKind
    # Slug d'une categorie pre-alimentee de schema.sql. Absent quand aucune
    # categorie existante ne convient : la fiche sera creee sans categorie
    # plutot que rangee de force au mauvais endroit.
    category: str | None = None
    deprecated: bool = False
    maintenances: list[CatalogMaintenance] = Field(default_factory=list)


class CatalogRoom(BaseModel):
    """Piece type proposee a l'etape 0 du didacticiel."""

    model_config = {"extra": "forbid"}

    key: str
    label: str
    # Slug d'un `location_type` pre-alimente de schema.sql.
    location_type: str
    deprecated: bool = False
    items: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    """Catalogue complet, tel que renvoye par l'API."""

    rooms: list[CatalogRoom]
    items: list[CatalogItem]
    # Entretiens rattaches a la maison et non a un objet : `maintenance_task`
    # accepte les deux (verifier les detecteurs de fumee, purger les radiateurs).
    home_maintenances: list[CatalogMaintenance]

    @model_validator(mode="after")
    def _references(self) -> Self:
        _reject_duplicates([room.key for room in self.rooms], "piece")
        _reject_duplicates([item.key for item in self.items], "objet")

        maintenance_keys = [m.key for m in self.home_maintenances]
        maintenance_keys += [m.key for item in self.items for m in item.maintenances]
        _reject_duplicates(maintenance_keys, "entretien")

        known = {item.key for item in self.items}
        for room in self.rooms:
            for item_key in room.items:
                if item_key not in known:
                    raise ValueError(
                        f"la piece '{room.key}' reference l'objet inconnu '{item_key}'"
                    )
        return self


def _reject_duplicates(keys: list[str], label: str) -> None:
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            raise ValueError(f"cle de {label} en double : '{key}'")
        seen.add(key)


def _read(name: str) -> object:
    return yaml.safe_load((_CATALOG_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    """Charge et valide le catalogue. Le resultat est immuable et mis en cache."""
    return Catalog(
        rooms=_read("rooms.yaml"),  # type: ignore[arg-type]
        items=_read("items.yaml"),  # type: ignore[arg-type]
        home_maintenances=_read("home_maintenances.yaml"),  # type: ignore[arg-type]
    )
