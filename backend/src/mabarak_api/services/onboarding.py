"""Application du didacticiel de demarrage : du catalogue vers la base.

Le catalogue ne fournit que des MODELES. Ce module les transforme en lignes qui
appartiennent ensuite entierement a l'utilisateur : `catalog_key` garde trace de
l'origine, mais rien ici ne relit jamais le catalogue pour mettre a jour une
ligne existante (adr/0008).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import CatalogMaintenance, load_catalog
from ..clock import utc_now_iso, utc_today
from ..models import (
    Asset,
    Category,
    Home,
    Location,
    LocationType,
    MaintenanceTask,
    ReplacementPart,
)
from ..schemas import TaskIn
from .catalog import location_path
from .recurrence import Recurrence, hidden_anchor, initial_next_due


class UnknownCatalogKeyError(LookupError):
    """Cle absente du catalogue livre : la requete est invalide."""


@dataclass(frozen=True)
class Proposal:
    """Entretien type restant a proposer, avec la fiche qu'il concerne."""

    maintenance: CatalogMaintenance
    asset_id: int | None
    asset_name: str | None
    # Un meme objet existe souvent dans plusieurs zones (volets, fenetres, siphon) :
    # sans le lieu, l'ecran de recapitulatif empile des propositions identiques.
    location_path: str | None


@dataclass(frozen=True)
class RoomState:
    """Ce qui existe deja pour une zone du catalogue, vu du didacticiel."""

    room_key: str
    location_id: int | None
    location_name: str | None
    present_items: list[str]


def house_state(session: Session, home: Home) -> list[RoomState]:
    """Pour chaque zone du catalogue, ce qui est deja enregistre.

    Applique exactement la meme regle de reconnaissance que `apply_room` — cle de
    catalogue d'abord, nom en repli — pour que ce qui s'affiche corresponde a ce
    qui se passerait reellement si l'utilisateur cochait.
    """
    catalog = load_catalog()
    locations = session.scalars(select(Location).where(Location.home_id == home.id)).all()
    by_catalog_key = {row.catalog_key: row for row in locations if row.catalog_key}
    by_name = {row.name: row for row in locations}

    states: list[RoomState] = []
    for room in catalog.rooms:
        location = by_catalog_key.get(room.key) or by_name.get(room.label)
        if location is None:
            states.append(RoomState(room.key, None, None, []))
            continue

        present: set[str] = set()
        for key, name in session.execute(
            select(Asset.catalog_key, Asset.name).where(Asset.location_id == location.id)
        ):
            if key is not None:
                present.add(key)
            present.add(name)

        by_key = {item.key: item for item in catalog.items}
        found = [
            item_key
            for item_key in room.items
            if item_key in present or by_key[item_key].label in present
        ]
        states.append(RoomState(room.key, location.id, location.name, found))

    return states


def apply_room(
    session: Session, home: Home, room_key: str, item_keys: list[str]
) -> tuple[Location, list[Asset]]:
    """Cree la zone et les fiches cochees, en sautant ce qui existe deja.

    Reprendre le didacticiel ou revenir sur une zone ne cree pas de doublon.
    """
    catalog = load_catalog()
    room = next((r for r in catalog.rooms if r.key == room_key), None)
    if room is None:
        raise UnknownCatalogKeyError(f"zone inconnue : '{room_key}'")

    unknown = set(item_keys) - {item.key for item in catalog.items}
    if unknown:
        raise UnknownCatalogKeyError(f"objets inconnus : {', '.join(sorted(unknown))}")

    now = utc_now_iso()
    location = session.scalars(
        select(Location).where(Location.home_id == home.id, Location.catalog_key == room_key)
    ).first()
    if location is None:
        # Maison deja remplie a la main : ses lieux n'ont aucune cle de catalogue.
        # On adopte celui qui porte deja ce nom plutot que d'en creer un double —
        # la contrainte UNIQUE ne protege pas, `parent_id` valant NULL au premier
        # niveau et deux NULL etant distincts sous SQLite.
        location = session.scalars(
            select(Location).where(Location.home_id == home.id, Location.name == room.label)
        ).first()
        if location is not None:
            location.catalog_key = room.key
            location.updated_at = now

    if location is None:
        location_type = session.scalars(
            select(LocationType).where(LocationType.slug == room.location_type)
        ).one()
        location = Location(
            home_id=home.id,
            name=room.label,
            location_type_id=location_type.id,
            catalog_key=room.key,
            created_at=now,
            updated_at=now,
        )
        session.add(location)
        session.flush()

    return location, add_items(session, home, location, item_keys)


def apply_items_to_location(
    session: Session, home: Home, location_id: int, item_keys: list[str]
) -> tuple[Location, list[Asset]]:
    """Meme chose, dans un lieu quelconque : les zones que l'utilisateur a creees
    lui-meme n'ont pas de cle de catalogue mais accueillent les memes objets."""
    location = session.get(Location, location_id)
    if location is None or location.home_id != home.id:
        raise UnknownCatalogKeyError(f"lieu introuvable : {location_id}")

    unknown = set(item_keys) - {item.key for item in load_catalog().items}
    if unknown:
        raise UnknownCatalogKeyError(f"objets inconnus : {', '.join(sorted(unknown))}")

    return location, add_items(session, home, location, item_keys)


def add_items(
    session: Session, home: Home, location: Location, item_keys: list[str]
) -> list[Asset]:
    """Cree les fiches cochees dans un lieu, en sautant ou adoptant ce qui existe."""
    catalog = load_catalog()
    now = utc_now_iso()
    existing = session.scalars(
        select(Asset).where(Asset.home_id == home.id, Asset.location_id == location.id)
    ).all()
    by_catalog_key = {asset.catalog_key: asset for asset in existing if asset.catalog_key}
    by_name = {asset.name: asset for asset in existing}

    by_key = {item.key: item for item in catalog.items}
    created: list[Asset] = []
    for item_key in item_keys:
        item = by_key[item_key]
        if item_key in by_catalog_key:
            continue

        adoptee = by_name.get(item.label)
        if adoptee is not None:
            # Fiche saisie a la main, donc sans cle. On l'adopte au lieu de
            # simplement l'ignorer : sans cela, ses entretiens types ne seraient
            # jamais proposes et relancer le tour n'apporterait rien a une maison
            # deja remplie.
            adoptee.catalog_key = item.key
            adoptee.updated_at = now
            continue

        asset = Asset(
            home_id=home.id,
            kind=item.kind,
            name=item.label,
            category_id=_category_id(session, item.category),
            location_id=location.id,
            status="active",
            catalog_key=item.key,
            created_at=now,
            updated_at=now,
        )
        session.add(asset)
        created.append(asset)

    session.flush()
    return created


def pending_proposals(session: Session, home: Home) -> list[Proposal]:
    """Entretiens types pas encore crees, pour l'ecran de recapitulatif."""
    catalog = load_catalog()
    by_item = {item.key: item for item in catalog.items}

    # Deduplication sur (entretien, fiche) et non sur la seule cle d'entretien :
    # un meme objet peut exister dans plusieurs zones (une bouche d'extraction
    # dans la salle de bain et aux WC), chacune avec son propre entretien.
    done = {
        (key, asset_id)
        for key, asset_id in session.execute(
            select(MaintenanceTask.catalog_key, MaintenanceTask.asset_id).where(
                MaintenanceTask.catalog_key.is_not(None)
            )
        )
    }

    proposals: list[Proposal] = []
    assets = session.scalars(
        select(Asset).where(Asset.home_id == home.id, Asset.catalog_key.is_not(None))
    ).all()
    for asset in assets:
        item = by_item.get(asset.catalog_key or "")
        if item is None:
            continue  # objet retire du catalogue depuis la creation de la fiche
        for maintenance in item.maintenances:
            if (maintenance.key, asset.id) in done:
                continue
            proposals.append(
                Proposal(
                    maintenance,
                    asset.id,
                    asset.name,
                    location_path(session, asset.location_id),
                )
            )

    for maintenance in catalog.home_maintenances:
        if (maintenance.key, None) not in done:
            proposals.append(Proposal(maintenance, None, None, None))

    return proposals


def draft_from_catalog(key: str) -> TaskIn:
    """Le modele du catalogue, sous la forme d'une fiche d'entretien editable.

    C'est ce que l'ecran de recapitulatif presente : une fiche pre-remplie que
    l'utilisateur peut modifier entierement avant de la valider.
    """
    maintenance = _find_maintenance(key)
    recurrence = maintenance.recurrence
    return TaskIn(
        name=maintenance.label,
        recurrence_type=recurrence.type,
        recurrence_interval=recurrence.interval,
        fixed_month=recurrence.month,
        fixed_day=recurrence.day,
        season_start_month=recurrence.season_start_month,
        season_end_month=recurrence.season_end_month,
        notes=maintenance.description,
        preparation_notes=maintenance.preparation_notes,
    )


def apply_maintenance(
    session: Session,
    home: Home,
    *,
    body: TaskIn,
    asset_id: int | None,
    key: str | None = None,
) -> MaintenanceTask:
    """Cree l'entretien tel que l'utilisateur l'a valide.

    `key` ne sert plus qu'a la provenance et a l'ancrage : le contenu vient
    entierement de `body`, que l'ecran de recapitulatif a pu faire modifier.
    """
    maintenance = _find_maintenance(key) if key is not None else None

    # L'ancrage vient du catalogue et non de `hidden_anchor`, qui le deduit du
    # seul type de recurrence : lui seul sait qu'un entretien annuel de chaudiere
    # est contractuel et ne doit pas deriver d'annee en annee (adr/0004).
    anchor = maintenance.anchor if maintenance is not None else hidden_anchor(body.recurrence_type)
    recurrence = Recurrence(
        recurrence_type=body.recurrence_type,
        interval=body.recurrence_interval,
        anchor=anchor,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        custom_due_date=date.fromisoformat(body.custom_due_date) if body.custom_due_date else None,
        season_start_month=body.season_start_month,
        season_end_month=body.season_end_month,
    )
    last = date.fromisoformat(body.last_completed_on) if body.last_completed_on else None
    next_due = initial_next_due(last_completed_on=last, today=utc_today(), recurrence=recurrence)

    now = utc_now_iso()
    task = MaintenanceTask(
        asset_id=asset_id,
        home_id=None if asset_id is not None else home.id,
        assignee_id=body.assignee_id,
        name=body.name.strip(),
        description=(body.notes or "").strip() or None,
        preparation_notes=(body.preparation_notes or "").strip() or None,
        priority=body.priority,
        recurrence_type=body.recurrence_type,
        recurrence_interval=body.recurrence_interval,
        recurrence_anchor=anchor,
        fixed_month=body.fixed_month,
        fixed_day=body.fixed_day,
        custom_due_date=body.custom_due_date,
        season_start_month=body.season_start_month,
        season_end_month=body.season_end_month,
        last_completed_on=body.last_completed_on,
        next_due_on=next_due.isoformat() if next_due else None,
        is_active=1,
        replacement_parts=[
            ReplacementPart(
                name=part.name.strip(),
                source=(part.source or "").strip() or None,
                sort_order=index,
            )
            for index, part in enumerate(body.replacement_parts)
        ],
        catalog_key=key,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.flush()
    return task


def _find_maintenance(key: str) -> CatalogMaintenance:
    catalog = load_catalog()
    for maintenance in catalog.home_maintenances:
        if maintenance.key == key:
            return maintenance
    for item in catalog.items:
        for maintenance in item.maintenances:
            if maintenance.key == key:
                return maintenance
    raise UnknownCatalogKeyError(f"entretien inconnu : '{key}'")


def _category_id(session: Session, slug: str | None) -> int | None:
    if slug is None:
        return None
    return session.scalars(select(Category.id).where(Category.slug == slug)).first()
