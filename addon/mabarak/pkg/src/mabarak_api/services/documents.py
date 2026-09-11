"""Contenu d'un document, et transitions entre ses trois modes de stockage.

Un document est **une meme entite quel que soit son mode de stockage** : fichier
depose dans l'application, lien vers un Nextcloud ou un NAS, ou simple note
« facture dans l'e-mail du 12/05/2024 ». L'endroit ou se trouve son contenu est
un attribut, pas une nature (adr/0002). Changer de mode est donc un `UPDATE`, et
le document garde son `id`, donc ses rattachements.

Ce module existe pour une raison precise, annoncee dans les consequences de
l'ADR : la transition entre modes ne se reduit pas a ecrire trois colonnes.
Quitter `local_file` doit **effacer le fichier physique**. Un PDF de facture
oublie sous `/data/documents/` ne serait pas une fuite — il n'est plus servi par
l'API — mais resterait dans les sauvegardes Home Assistant d'un utilisateur qui
a justement demande a ce que ses factures n'y soient plus. `apply_*` est donc le
seul chemin par lequel un document change de contenu.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..clock import utc_now_iso
from ..config import Settings
from ..models import Document

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".doc",
    ".docx",
}
MAX_SIZE = 10 * 1024 * 1024

# Documents sans equipement de rattachement (maison, entretien, incident) : un
# sous-repertoire plutot que la racine de /data/documents/, pour que le contenu
# du repertoire reste lisible a l'oeil nu.
UNSCOPED_DIR = "divers"


@dataclass(frozen=True)
class StoredFile:
    """Fichier ecrit sur le disque, pas encore rattache a un document."""

    file_path: str
    file_size: int
    mime_type: str | None
    original_name: str


async def store_upload(file: UploadFile, settings: Settings, *, scope: str) -> StoredFile:
    original_name = file.filename or "document"
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Type de fichier non accepte")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "Fichier trop volumineux (10 Mo maximum)")

    target_dir = settings.documents_dir / scope
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    (target_dir / stored_name).write_bytes(content)
    return StoredFile(
        file_path=f"{scope}/{stored_name}",
        file_size=len(content),
        mime_type=file.content_type,
        original_name=original_name,
    )


def discard_file(settings: Settings, row: Document) -> None:
    """Efface le fichier physique d'un document, s'il en avait un."""
    if row.storage_mode == "local_file" and row.file_path:
        (settings.documents_dir / row.file_path).unlink(missing_ok=True)


def apply_local_file(settings: Settings, row: Document, stored: StoredFile) -> None:
    """Passe le document en fichier local, en ecartant son contenu precedent."""
    discard_file(settings, row)
    row.storage_mode = "local_file"
    row.file_path = stored.file_path
    row.file_size = stored.file_size
    row.mime_type = stored.mime_type
    row.url = None
    row.reference_note = None
    row.updated_at = utc_now_iso()


def apply_external_link(settings: Settings, row: Document, url: str) -> None:
    discard_file(settings, row)
    row.storage_mode = "external_link"
    row.url = url
    row.file_path = None
    row.file_size = None
    row.mime_type = None
    row.reference_note = None
    row.updated_at = utc_now_iso()


def apply_reference_note(settings: Settings, row: Document, note: str) -> None:
    discard_file(settings, row)
    row.storage_mode = "reference_note"
    row.reference_note = note
    row.file_path = None
    row.file_size = None
    row.mime_type = None
    row.url = None
    row.updated_at = utc_now_iso()


def delete_document(session: Session, settings: Settings, row: Document) -> None:
    discard_file(settings, row)
    session.delete(row)
