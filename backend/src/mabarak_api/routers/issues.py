"""Les problemes constates sur un equipement (table `issue`).

La table existe dans `schema.sql` depuis l'origine — avec ses index, son CHECK
sur `resolved_on` et sa place dans `v_asset_timeline` — mais rien ne l'ecrivait
ni ne la lisait. Elle n'etait citee que comme litteral dans `DocumentScope` : un
document pouvait donc se declarer rattache a un probleme qui ne pouvait pas
exister.

Un probleme n'est pas une intervention. L'intervention est une action datee,
ponctuelle ; le probleme dure — « la VMC fait du bruit » — et peut appeler
plusieurs interventions avant d'etre resolu. C'est ce qui justifie les deux
tables, et ce qui rend la chronologie d'une fiche lisible : on y voit quand
quelque chose a commence a aller mal, pas seulement quand on s'en est occupe.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import utc_now_iso, utc_today
from ..config import Settings
from ..db import get_app_settings, get_session
from ..models import Asset, Document, Home, Issue
from ..schemas import DocType, DocumentOut, IssueIn, IssueOut, IssuePatch, StorageMode
from ..services.documents import contenu_a_la_creation, document_out
from ..services.home import ensure_home

router = APIRouter(tags=["problemes"])


def _home(session: Session) -> Home:
    return ensure_home(session)


def _issue_out(row: Issue) -> IssueOut:
    return IssueOut(
        id=row.id,
        asset_id=row.asset_id,
        title=row.title,
        description=row.description,
        action_taken=row.action_taken,
        result=row.result,
        status=row.status,  # type: ignore[arg-type]
        severity=row.severity,  # type: ignore[arg-type]
        opened_on=row.opened_on,
        resolved_on=row.resolved_on,
    )


def _get_asset(session: Session, asset_id: int) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None or asset.home_id != _home(session).id:
        raise HTTPException(404, "Equipement introuvable")
    return asset


def _get_issue(session: Session, issue_id: int) -> Issue:
    row = session.get(Issue, issue_id)
    if row is None:
        raise HTTPException(404, "Probleme introuvable")
    _get_asset(session, row.asset_id)
    return row


@router.get("/assets/{asset_id}/issues", response_model=list[IssueOut])
def list_issues(asset_id: int, session: Session = Depends(get_session)) -> list[IssueOut]:
    """Les problemes de cet equipement, les ouverts d'abord.

    Un probleme resolu il y a trois ans n'a pas a passer devant une fuite en
    cours : l'ordre suit l'urgence, pas la seule chronologie.
    """
    _get_asset(session, asset_id)
    rows = session.scalars(
        select(Issue)
        .where(Issue.asset_id == asset_id)
        .order_by(Issue.opened_on.desc(), Issue.id.desc())
    ).all()
    ordre = {"open": 0, "in_progress": 0, "resolved": 1}
    return [_issue_out(row) for row in sorted(rows, key=lambda row: ordre.get(row.status, 0))]


@router.post("/assets/{asset_id}/issues", response_model=IssueOut, status_code=201)
def create_issue(asset_id: int, body: IssueIn, session: Session = Depends(get_session)) -> IssueOut:
    _get_asset(session, asset_id)
    maintenant = utc_now_iso()
    row = Issue(
        asset_id=asset_id,
        title=body.title.strip(),
        description=(body.description or "").strip() or None,
        severity=body.severity,
        status="open",
        opened_on=body.opened_on or utc_today().isoformat(),
        created_at=maintenant,
        updated_at=maintenant,
    )
    session.add(row)
    session.flush()
    return _issue_out(row)


@router.patch("/issues/{issue_id}", response_model=IssueOut)
def patch_issue(
    issue_id: int, body: IssuePatch, session: Session = Depends(get_session)
) -> IssueOut:
    row = _get_issue(session, issue_id)
    data = body.model_dump(exclude_unset=True)

    # `resolved_on` renseigne si et seulement si le statut est `resolved` : c'est
    # un CHECK de la base. Le tenir ici, et non dans l'interface, evite qu'un
    # appelant oublie la moitie de la regle et se prenne une IntegrityError.
    if "status" in data:
        statut = data["status"]
        if statut == "resolved":
            data["resolved_on"] = (
                data.get("resolved_on") or row.resolved_on or utc_today().isoformat()
            )
        else:
            data["resolved_on"] = None
    elif "resolved_on" in data and data["resolved_on"] is not None and row.status != "resolved":
        raise HTTPException(422, "Une date de resolution n'a de sens que sur un probleme resolu.")

    for champ in ("title", "description", "action_taken", "result"):
        if champ in data and isinstance(data[champ], str):
            data[champ] = data[champ].strip() or None
    if data.get("title") is None and "title" in data:
        raise HTTPException(422, "Un probleme a besoin d'un titre.")

    for clef, valeur in data.items():
        setattr(row, clef, valeur)
    row.updated_at = utc_now_iso()
    session.flush()
    return _issue_out(row)


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    row = _get_issue(session, issue_id)
    session.delete(row)
    session.flush()
    return {"ok": True}


@router.post("/issues/{issue_id}/documents", response_model=DocumentOut, status_code=201)
async def create_issue_document(
    issue_id: int,
    storage_mode: StorageMode = Form("local_file"),
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    reference_note: str | None = Form(None),
    doc_type: DocType = Form("other"),
    name: str | None = Form(None),
    notes: str | None = Form(None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentOut:
    """Le devis, la photo de la fuite, le rapport du plombier.

    `DocumentScope` annoncait « issue » depuis toujours, sans qu'aucune route ne
    permette d'y arriver : le rattachement etait declarable et jamais joignable.
    Le fichier suit l'equipement du probleme, comme celui d'une intervention.
    """
    row = _get_issue(session, issue_id)
    contenu, label = await contenu_a_la_creation(
        settings,
        scope=str(row.asset_id),
        storage_mode=storage_mode,
        file=file,
        url=url,
        reference_note=reference_note,
        name=name,
    )
    maintenant = utc_now_iso()
    document = Document(
        issue_id=row.id,
        name=label,
        doc_type=doc_type,
        notes=(notes or "").strip() or None,
        created_at=maintenant,
        updated_at=maintenant,
        **contenu,
    )
    session.add(document)
    session.flush()
    return document_out(document)


@router.get("/issues/{issue_id}/documents", response_model=list[DocumentOut])
def list_issue_documents(
    issue_id: int, session: Session = Depends(get_session)
) -> list[DocumentOut]:
    row = _get_issue(session, issue_id)
    return [
        document_out(document)
        for document in session.scalars(
            select(Document).where(Document.issue_id == row.id).order_by(Document.id)
        )
    ]
