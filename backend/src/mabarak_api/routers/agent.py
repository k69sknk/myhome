"""Surface de pilotage par un agent externe (adr/0013).

Pourquoi un routeur a part, alors que `/api/assets` sait deja tout faire : les
routes de l'interface parlent en identifiants, parce que l'interface vient de
les afficher. Un agent n'a que des noms. Chaque route ci-dessous fait donc en
un seul appel ce que l'interface fait en deux — retrouver la fiche, puis agir —
et repond par une phrase francaise plutot que par un objet a interpreter.

La regle qui gouverne tout le fichier : **en cas de doute, ne rien ecrire.** Une
erreur qui nomme les candidats se rattrape ; une ecriture dans la mauvaise fiche,
non.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..clock import utc_now_iso, utc_today
from ..db import get_session
from ..models import (
    Asset,
    Cost,
    Home,
    Intervention,
    Location,
    LocationType,
    MaintenanceTask,
    Warranty,
)
from ..schemas.agent import (
    TYPE_INTERVENTION_SQL,
    ActionOut,
    Apercu,
    Compteurs,
    ConsignerInterventionIn,
    CreerEntretienIn,
    CreerEquipementIn,
    EcheanceResume,
    EntretienResume,
    EquipementResume,
    GarantieResume,
    ValiderEntretienIn,
)
from ..services.agent import (
    VIA_AGENT,
    FrequenceInvalideError,
    frequence_en_francais,
    recurrence_depuis_frequence,
    resoudre_entretien,
    resoudre_equipement,
    resoudre_intervenant,
    resoudre_lieu,
    taches_de_la_maison,
)
from ..services.catalog import (
    complete_task,
    location_path,
    plan_task,
    task_status_map,
    worst_status,
)
from ..services.home import ensure_home
from ..services.recurrence import RecurrenceType
from ..services.resolve import IntrouvableError, fold

router = APIRouter(prefix="/agent", tags=["pilotage par agent"])

# Assez pour repondre « qu'est-ce qui arrive ? » sans noyer la reponse.
PROCHAINS_MAX = 10
GARANTIE_FENETRE_JOURS = 60


def _home(session: Session) -> Home:
    return ensure_home(session)


def _euros_en_centimes(montant: float | None) -> int | None:
    return None if montant is None else round(montant * 100)


def _date_ou_aujourdhui(valeur: str | None) -> str:
    if valeur is None:
        return utc_today().isoformat()
    try:
        return date.fromisoformat(valeur).isoformat()
    except ValueError as err:
        raise HTTPException(
            422, f"« {valeur} » n'est pas une date valide (format attendu : AAAA-MM-JJ)."
        ) from err


@router.get("/apercu", response_model=Apercu, summary="L'etat de la maison en un appel")
def apercu(session: Session = Depends(get_session)) -> Apercu:
    """Le point de depart de toute conversation : ce qui presse, et ce qui existe.

    La liste des lieux et le nombre d'equipements sont la pour une raison
    precise : ils donnent a l'agent le vocabulaire de la maison. Sans eux, il
    invente des noms de pieces et echoue a la resolution suivante.
    """
    home = _home(session)
    taches = taches_de_la_maison(session, home.id)
    statuts = task_status_map(session, [task.id for task in taches])

    compteurs = Compteurs()
    en_retard: list[EcheanceResume] = []
    prochains: list[EcheanceResume] = []

    for task in taches:
        ligne = statuts.get(task.id)
        statut = ligne.status if ligne is not None else "unscheduled"
        match statut:
            case "overdue":
                compteurs.en_retard += 1
            case "due_soon":
                compteurs.bientot += 1
            case "ok":
                compteurs.a_jour += 1
            case _:
                compteurs.sans_echeance += 1

        if ligne is None or ligne.next_due_on is None:
            continue
        resume = EcheanceResume(
            entretien=task.name,
            equipement=task.asset.name if task.asset is not None else None,
            echeance=ligne.next_due_on,
            jours_restants=ligne.days_until_due or 0,
        )
        (en_retard if statut == "overdue" else prochains).append(resume)

    en_retard.sort(key=lambda item: item.echeance)
    prochains.sort(key=lambda item: item.echeance)

    aujourdhui = utc_today()
    fin_fenetre = (aujourdhui + timedelta(days=GARANTIE_FENETRE_JOURS)).isoformat()
    garanties: list[GarantieResume] = []
    for warranty in session.scalars(select(Warranty).where(Warranty.end_date.is_not(None))).all():
        if warranty.end_date is None or not (
            aujourdhui.isoformat() <= warranty.end_date <= fin_fenetre
        ):
            continue
        asset = session.get(Asset, warranty.asset_id)
        if asset is not None and asset.status != "removed":
            garanties.append(GarantieResume(equipement=asset.name, fin=warranty.end_date))
    garanties.sort(key=lambda item: item.fin)

    lieux = session.scalars(
        select(Location).where(Location.home_id == home.id).order_by(Location.name)
    ).all()
    equipements = session.scalar(
        select(func.count())
        .select_from(Asset)
        .where(Asset.home_id == home.id, Asset.status != "removed")
    )

    return Apercu(
        maison=home.name,
        compteurs=compteurs,
        en_retard=en_retard,
        prochains=prochains[:PROCHAINS_MAX],
        garanties_qui_expirent=garanties,
        lieux=[location_path(session, lieu.id) or lieu.name for lieu in lieux],
        nombre_equipements=equipements or 0,
    )


@router.get(
    "/equipements",
    response_model=list[EquipementResume],
    summary="Les fiches, avec leurs entretiens",
)
def equipements(
    recherche: str | None = None, session: Session = Depends(get_session)
) -> list[EquipementResume]:
    """Les equipements et tout ce qui les concerne, filtres par `recherche`.

    Le filtre est volontairement large — il ne sert qu'a raccourcir la reponse,
    pas a designer une fiche. Designer, c'est le role de `services/resolve.py`,
    qui refuse de trancher ; ici, rendre trop de lignes est sans consequence.
    """
    home = _home(session)
    assets = session.scalars(
        select(Asset)
        .where(Asset.home_id == home.id, Asset.status != "removed")
        .options(
            selectinload(Asset.tasks),
            selectinload(Asset.warranty),
        )
        .order_by(Asset.name)
    ).all()

    if recherche:
        cible = fold(recherche)
        mots = [mot for mot in cible.split() if len(mot) > 1]
        assets = [
            asset
            for asset in assets
            if all(
                mot in fold(f"{asset.name} {asset.brand or ''} {asset.model or ''}") for mot in mots
            )
        ]

    statuts = task_status_map(session, [task.id for asset in assets for task in asset.tasks])

    resumes: list[EquipementResume] = []
    for asset in assets:
        entretiens: list[EntretienResume] = []
        for task in asset.tasks:
            if not task.is_active:
                continue
            ligne = statuts.get(task.id)
            entretiens.append(
                EntretienResume(
                    nom=task.name,
                    statut=ligne.status if ligne is not None else "unscheduled",  # type: ignore[arg-type]
                    echeance=ligne.next_due_on if ligne is not None else None,
                    jours_restants=ligne.days_until_due if ligne is not None else None,
                    derniere_fois=task.last_completed_on,
                    frequence=frequence_en_francais(task),
                )
            )
        resumes.append(
            EquipementResume(
                nom=asset.name,
                type="equipement" if asset.kind == "equipment" else "element de construction",
                lieu=location_path(session, asset.location_id),
                marque=asset.brand,
                modele=asset.model,
                numero_de_serie=asset.serial_number,
                date_installation=asset.install_date,
                garantie_jusqu_au=asset.warranty.end_date if asset.warranty is not None else None,
                statut_entretien=worst_status([e.statut for e in entretiens]),  # type: ignore[arg-type]
                entretiens=entretiens,
            )
        )
    return resumes


@router.post(
    "/entretiens/valider", response_model=ActionOut, summary="Marquer un entretien comme fait"
)
def valider_entretien(
    body: ValiderEntretienIn, session: Session = Depends(get_session)
) -> ActionOut:
    home = _home(session)
    task = resoudre_entretien(session, home.id, body.entretien, body.equipement)

    if task.asset_id is None:
        # Limitation connue et anterieure a cette surface : `intervention.asset_id`
        # est NOT NULL, un entretien rattache a la maison ne peut donc pas encore
        # etre valide — pas davantage depuis l'interface. Le dire franchement vaut
        # mieux que de laisser croire a un probleme de resolution du nom.
        raise HTTPException(
            409,
            f"« {task.name} » est un entretien de la maison, pas d'un equipement. "
            "MaBarak ne sait pas encore enregistrer sa realisation, ni ici ni dans "
            "l'interface.",
        )

    asset = session.get(Asset, task.asset_id)
    if asset is None:
        raise HTTPException(404, "Equipement introuvable")

    quand = _date_ou_aujourdhui(body.date)
    membre, prestataire, nom_affiche = (
        resoudre_intervenant(session, home.id, body.fait_par) if body.fait_par else (None, None, "")
    )

    intervention = complete_task(
        session,
        task,
        performed_on=quand,
        performed_by=nom_affiche or None,
        performed_by_member_id=membre.id if membre is not None else None,
        performed_by_provider_id=prestataire.id if prestataire is not None else None,
        notes=body.notes,
    )
    intervention.created_via = VIA_AGENT

    centimes = _euros_en_centimes(body.montant_euros)
    if centimes is not None:
        maintenant = utc_now_iso()
        session.add(
            Cost(
                asset_id=asset.id,
                intervention_id=intervention.id,
                cost_type="maintenance",
                amount_cents=centimes,
                currency=home.currency,
                incurred_on=quand,
                created_at=maintenant,
                updated_at=maintenant,
            )
        )
    session.flush()

    suite = (
        f" Prochaine echeance le {task.next_due_on}."
        if task.next_due_on
        else " Cet entretien n'a pas de frequence : aucune prochaine echeance n'a ete calculee."
    )
    return ActionOut(
        message=f"« {task.name} » sur « {asset.name} » est note comme fait le {quand}.{suite}",
        equipement=asset.name,
        entretien=task.name,
        prochaine_echeance=task.next_due_on,
    )


@router.post(
    "/entretiens", response_model=ActionOut, status_code=201, summary="Planifier un entretien"
)
def creer_entretien(body: CreerEntretienIn, session: Session = Depends(get_session)) -> ActionOut:
    home = _home(session)
    asset = resoudre_equipement(session, home.id, body.equipement)

    doublon = next(
        (
            task
            for task in asset.tasks
            if task.is_active and task.name.strip().casefold() == body.nom.strip().casefold()
        ),
        None,
    )
    if doublon is not None:
        raise HTTPException(
            409,
            f"« {asset.name} » a deja un entretien nomme « {doublon.name} » "
            f"({frequence_en_francais(doublon)}). Choisissez un autre nom, ou "
            "validez celui-ci plutot que d'en creer un second.",
        )

    try:
        rec_type, intervalle, mois, jour, date_unique = recurrence_depuis_frequence(body.frequence)
    except FrequenceInvalideError as err:
        raise HTTPException(422, str(err)) from err

    type_recurrence: RecurrenceType = rec_type
    ancre, prochaine = plan_task(
        recurrence_type=type_recurrence,
        interval=intervalle,
        fixed_month=mois,
        fixed_day=jour,
        custom_due_date=date_unique,
        last_completed_on=_date_ou_aujourdhui(body.derniere_fois) if body.derniere_fois else None,
        season_start_month=body.frequence.saison_du_mois,
        season_end_month=body.frequence.saison_au_mois,
    )

    membre, prestataire = (None, None)
    if body.responsable:
        membre, prestataire, _ = resoudre_intervenant(session, home.id, body.responsable)
        if membre is None and prestataire is None:
            raise IntrouvableError(
                f"Aucun membre ni prestataire ne correspond a « {body.responsable} ». "
                "Un responsable doit exister dans l'annuaire ; laissez le champ vide "
                "si l'entretien n'est assigne a personne."
            )

    maintenant = utc_now_iso()
    task = MaintenanceTask(
        asset_id=asset.id,
        home_id=None,
        assignee_id=membre.id if membre is not None else None,
        assignee_provider_id=prestataire.id if prestataire is not None else None,
        name=body.nom.strip(),
        priority=body.priorite,
        recurrence_type=type_recurrence,
        recurrence_interval=intervalle,
        recurrence_anchor=ancre,
        fixed_month=mois,
        fixed_day=jour,
        custom_due_date=date_unique,
        season_start_month=body.frequence.saison_du_mois,
        season_end_month=body.frequence.saison_au_mois,
        last_completed_on=body.derniere_fois,
        next_due_on=prochaine,
        is_active=1,
        description=(body.notes or "").strip() or None,
        created_via=VIA_AGENT,
        created_at=maintenant,
        updated_at=maintenant,
    )
    session.add(task)
    session.flush()

    suite = f" Premiere echeance le {prochaine}." if prochaine else ""
    return ActionOut(
        message=(
            f"Entretien « {task.name} » ajoute a « {asset.name} », "
            f"{frequence_en_francais(task)}.{suite}"
        ),
        equipement=asset.name,
        entretien=task.name,
        prochaine_echeance=prochaine,
    )


@router.post("/equipements", response_model=ActionOut, status_code=201, summary="Creer une fiche")
def creer_equipement(body: CreerEquipementIn, session: Session = Depends(get_session)) -> ActionOut:
    home = _home(session)

    existant = session.scalar(
        select(Asset).where(
            Asset.home_id == home.id,
            Asset.status != "removed",
            Asset.name == body.nom.strip(),
        )
    )
    if existant is not None:
        raise HTTPException(
            409,
            f"Une fiche « {existant.name} » existe deja"
            + (
                f" ({location_path(session, existant.location_id)})."
                if existant.location_id
                else "."
            ),
        )

    lieu: Location | None = None
    if body.lieu:
        try:
            lieu = resoudre_lieu(session, home.id, body.lieu)
        except IntrouvableError:
            if not body.creer_le_lieu:
                raise
            maintenant = utc_now_iso()
            type_lieu = session.scalar(select(LocationType).order_by(LocationType.sort_order))
            if type_lieu is None:
                raise HTTPException(500, "Aucun type de lieu configure") from None
            lieu = Location(
                home_id=home.id,
                name=body.lieu.strip(),
                location_type_id=type_lieu.id,
                created_at=maintenant,
                updated_at=maintenant,
            )
            session.add(lieu)
            session.flush()

    maintenant = utc_now_iso()
    asset = Asset(
        home_id=home.id,
        kind="equipment" if body.type == "equipement" else "building_element",
        name=body.nom.strip(),
        location_id=lieu.id if lieu is not None else None,
        status="active",
        brand=body.marque,
        model=body.modele,
        serial_number=body.numero_de_serie,
        purchase_date=body.date_achat,
        install_date=body.date_installation,
        notes=body.notes,
        created_via=VIA_AGENT,
        created_at=maintenant,
        updated_at=maintenant,
    )
    session.add(asset)
    session.flush()

    if body.garantie_mois is not None:
        debut = body.date_achat or body.date_installation or utc_today().isoformat()
        session.add(
            Warranty(
                asset_id=asset.id,
                start_date=debut,
                duration_months=body.garantie_mois,
                created_at=maintenant,
                updated_at=maintenant,
            )
        )
        session.flush()

    ou = f" dans « {location_path(session, asset.location_id)} »" if asset.location_id else ""
    return ActionOut(
        message=(
            f"Fiche « {asset.name} » creee{ou}. "
            "Elle n'a encore aucun entretien : ajoutez-en un pour qu'elle apparaisse "
            "dans les echeances."
        ),
        equipement=asset.name,
    )


@router.post(
    "/interventions",
    response_model=ActionOut,
    status_code=201,
    summary="Consigner une intervention ponctuelle",
)
def consigner_intervention(
    body: ConsignerInterventionIn, session: Session = Depends(get_session)
) -> ActionOut:
    home = _home(session)
    asset = resoudre_equipement(session, home.id, body.equipement)
    quand = _date_ou_aujourdhui(body.date)

    membre, prestataire, nom_affiche = (
        resoudre_intervenant(session, home.id, body.fait_par) if body.fait_par else (None, None, "")
    )

    maintenant = utc_now_iso()
    intervention = Intervention(
        asset_id=asset.id,
        task_id=None,
        intervention_type=TYPE_INTERVENTION_SQL[body.type],
        performed_on=quand,
        performed_by=nom_affiche or None,
        performed_by_member_id=membre.id if membre is not None else None,
        performed_by_provider_id=prestataire.id if prestataire is not None else None,
        notes=body.notes,
        created_via=VIA_AGENT,
        created_at=maintenant,
        updated_at=maintenant,
    )
    session.add(intervention)
    session.flush()

    centimes = _euros_en_centimes(body.montant_euros)
    if centimes is not None:
        session.add(
            Cost(
                asset_id=asset.id,
                intervention_id=intervention.id,
                cost_type="repair" if body.type == "reparation" else "maintenance",
                amount_cents=centimes,
                currency=home.currency,
                incurred_on=quand,
                created_at=maintenant,
                updated_at=maintenant,
            )
        )
        session.flush()

    par = f" par {nom_affiche}" if nom_affiche else ""
    return ActionOut(
        message=f"Intervention du {quand} consignee sur « {asset.name} »{par}.",
        equipement=asset.name,
    )
