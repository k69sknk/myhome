import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { DocType, DocumentDraft, DocumentMeta, DocumentPatchIn } from '../api/types'
import { draftIsEmpty } from '../api/types'
import { docTypeLabel, errorMessage } from '../lib/format'
import DocumentInput from './DocumentInput'
import Field from './Field'
import Modal from './Modal'
import { useToast } from './Toast'

/** Types proposes a la saisie. `photo` n'en est pas : la photo de la fiche a son
 *  propre emplacement, en haut de la page. */
export const DOC_TYPES: DocType[] = [
  'manual',
  'user_guide',
  'invoice',
  'warranty',
  'certificate',
  'service_contract',
  'other',
]

/** Modification d'un document, changement de mode compris.
 *
 *  C'est le geste que l'adr/0002 voulait rendre possible : l'utilisateur qui
 *  sort ses factures de l'application, ou celui qui retrouve enfin le PDF qu'il
 *  avait seulement note. Le document garde son identite dans les deux sens.
 */
export default function DocumentEdit({
  document,
  onClose,
  onSaved,
  onError,
}: {
  document: DocumentMeta
  onClose: () => void
  onSaved: () => void
  onError: (message: string | null) => void
}) {
  const [name, setName] = useState(document.name)
  const [docType, setDocType] = useState<DocType>(document.doc_type)
  const [draft, setDraft] = useState<DocumentDraft>(() => {
    if (document.storage_mode === 'external_link') {
      return { mode: 'external_link', url: document.url ?? '' }
    }
    if (document.storage_mode === 'reference_note') {
      return { mode: 'reference_note', note: document.reference_note ?? '' }
    }
    return { mode: 'local_file', file: null }
  })
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()

  async function save(event: FormEvent) {
    event.preventDefault()
    if (name.trim() === '') {
      onError("Ce document a besoin d'un nom.")
      return
    }
    if (draft.mode !== 'local_file' && draftIsEmpty(draft)) {
      onError(
        draft.mode === 'external_link'
          ? "Un lien externe a besoin de son adresse."
          : 'Une référence a besoin de son texte.',
      )
      return
    }
    if (draft.mode === 'local_file' && document.storage_mode !== 'local_file' && draft.file === null) {
      onError('Choisissez le fichier à déposer, ou gardez le mode actuel.')
      return
    }
    setBusy(true)
    onError(null)
    try {
      const patch: DocumentPatchIn = {}
      if (name.trim() !== document.name) patch.name = name.trim()
      if (docType !== document.doc_type) patch.doc_type = docType
      // Le mode et son contenu ne partent que s'ils ont bougé : reenvoyer la
      // meme note ne changerait rien, mais annoncerait une modification.
      const modeChanged = draft.mode !== document.storage_mode
      if (draft.mode === 'external_link' && (modeChanged || draft.url.trim() !== document.url)) {
        patch.storage_mode = 'external_link'
        patch.url = draft.url.trim()
      } else if (
        draft.mode === 'reference_note' &&
        (modeChanged || draft.note.trim() !== document.reference_note)
      ) {
        patch.storage_mode = 'reference_note'
        patch.reference_note = draft.note.trim()
      }
      // Le changement de mode vers un lien ou une reference peut partir avec le
      // renommage : c'est un seul UPDATE.
      const patched = Object.keys(patch).length > 0
      if (patched) await api.patchDocument(document.id, patch)
      // Le retour au fichier local demande un envoi multipart, donc un appel a part.
      const file = draft.mode === 'local_file' ? draft.file : null
      if (file !== null) await api.attachDocumentFile(document.id, file)
      if (patched || file !== null) showToast('Document modifié')
      onSaved()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Modifier le document" onClose={onClose}>
      <form className="form" onSubmit={(event) => void save(event)}>
        <div className="doc-form__row">
          <Field label="Type">
            <select value={docType} onChange={(event) => setDocType(event.target.value as DocType)}>
              {DOC_TYPES.map((value) => (
                <option key={value} value={value}>
                  {docTypeLabel(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Nom">
            <input type="text" value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
        </div>
        <div className="field">
          <span className="field__label">Où se trouve ce document</span>
          <DocumentInput value={draft} onChange={setDraft} disabled={busy} />
          {document.storage_mode === 'local_file' && (
            <span className="field__hint">
              Passer à un lien ou à une note efface le fichier déposé dans l'application.
            </span>
          )}
        </div>
        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Enregistrer
          </button>
        </div>
      </form>
    </Modal>
  )
}

