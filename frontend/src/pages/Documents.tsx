import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { DocType, DocumentDraft, DocumentListItem, StorageMode } from '../api/types'
import { draftIsEmpty, emptyDraft } from '../api/types'
import DocumentEdit, { DOC_TYPES } from '../components/DocumentEdit'
import DocumentInput from '../components/DocumentInput'
import DocumentLink from '../components/DocumentLink'
import Field from '../components/Field'
import { EditIcon, TrashIcon } from '../components/icons'
import { useToast } from '../components/Toast'
import {
  docTypeLabel,
  documentWhere,
  errorMessage,
  formatDate,
  storageModeLabel,
} from '../lib/format'
import { matches } from '../lib/search'

const MODES: StorageMode[] = ['local_file', 'external_link', 'reference_note']

/** Types proposes pour un papier de la maison : l'acte, l'assurance, le DPE. Ce
 *  ne sont pas les memes que pour un appareil, ou l'on cherche d'abord la notice. */
const HOME_DOC_TYPES: DocType[] = [
  'certificate',
  'service_contract',
  'invoice',
  'warranty',
  'other',
]

/** Ce a quoi le document est rattache, et par ou le retrouver.
 *
 *  Un document appartient a une seule entite (adr/0002). La facture d'un
 *  entretien remonte a l'equipement par jointure : c'est la fiche qu'on veut
 *  ouvrir, pas l'intervention. */
function Attachment({ document }: { document: DocumentListItem }) {
  if (document.scope === 'home') return <span className="muted">La maison</span>
  if (document.asset_id === null || document.asset_name === null) {
    return <span className="muted">Incident</span>
  }
  const base = document.asset_kind === 'building_element' ? '/elements' : '/equipements'
  return (
    <span className="muted">
      <Link to={`${base}/${document.asset_id}`}>{document.asset_name}</Link>
      {document.scope === 'intervention' && document.performed_on !== null && (
        <> · entretien du {formatDate(document.performed_on)}</>
      )}
      {document.scope === 'maintenance_task' && document.task_name !== null && (
        <> · {document.task_name}</>
      )}
    </span>
  )
}

export default function Documents() {
  const [documents, setDocuments] = useState<DocumentListItem[] | null>(null)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<DocType | ''>('')
  const [modeFilter, setModeFilter] = useState<StorageMode | ''>('')
  const [editing, setEditing] = useState<DocumentListItem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<DocumentDraft>(emptyDraft())
  const [name, setName] = useState('')
  const [docType, setDocType] = useState<DocType>('certificate')
  const { showToast } = useToast()

  async function reload() {
    setDocuments(await api.documents())
  }

  useEffect(() => {
    void reload().catch((caught: unknown) => setError(errorMessage(caught)))
  }, [])

  async function add(event: FormEvent) {
    event.preventDefault()
    if (draftIsEmpty(draft)) {
      setError("Ce document a besoin d'un contenu : un fichier, un lien ou une note.")
      return
    }
    if (draft.mode !== 'local_file' && name.trim() === '') {
      setError("Ce document a besoin d'un nom : sans fichier, il n'y en a pas à reprendre.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.createHomeDocument(draft, { doc_type: docType, name: name.trim() })
      setName('')
      setDraft(emptyDraft())
      showToast('Document ajouté')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove(documentId: number) {
    setBusy(true)
    setError(null)
    try {
      await api.deleteDocument(documentId)
      showToast('Document supprimé')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const all = documents ?? []
  // Un filtre a une seule reponse possible n'est pas un filtre : il n'apparait
  // qu'a partir de deux valeurs differentes dans la liste (comme le metier des
  // prestataires en 0.26).
  const presentTypes = DOC_TYPES.filter((value) => all.some((row) => row.doc_type === value))
  const presentModes = MODES.filter((value) => all.some((row) => row.storage_mode === value))
  const visible = all.filter(
    (row) =>
      (typeFilter === '' || row.doc_type === typeFilter) &&
      (modeFilter === '' || row.storage_mode === modeFilter) &&
      // Le nom, le contenu, mais aussi l'equipement : « facture chaudiere » est
      // une recherche qui traverse deux champs.
      matches(
        [row.name, row.asset_name, row.task_name, row.reference_note, row.url, row.notes],
        query,
      ),
  )

  return (
    <section className="page">
      <div className="page__header">
        <div>
          <h1 className="page__title">Documents</h1>
          <p className="page__lead">
            Tous les papiers de la maison : ceux de la maison elle-même, et ceux rattachés à un
            équipement ou à un entretien.
          </p>
        </div>
      </div>

      {error && <p className="status status--error">{error}</p>}

      <div className="card">
        {documents === null ? (
          <p className="muted">Chargement...</p>
        ) : (
          <>
            {all.length > 0 && (
              <div className="filters">
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Chercher un document, un équipement..."
                />
                {presentTypes.length > 1 && (
                  <select
                    value={typeFilter}
                    onChange={(event) => setTypeFilter(event.target.value as DocType | '')}
                  >
                    <option value="">Tous les types</option>
                    {presentTypes.map((value) => (
                      <option key={value} value={value}>
                        {docTypeLabel(value)}
                      </option>
                    ))}
                  </select>
                )}
                {presentModes.length > 1 && (
                  <select
                    value={modeFilter}
                    onChange={(event) => setModeFilter(event.target.value as StorageMode | '')}
                  >
                    <option value="">Tous les rangements</option>
                    {presentModes.map((value) => (
                      <option key={value} value={value}>
                        {storageModeLabel(value)}
                      </option>
                    ))}
                  </select>
                )}
                <span className="muted">
                  {visible.length} sur {all.length}
                </span>
              </div>
            )}
            {all.length === 0 && (
              <p className="muted">
                Aucun document pour l'instant. Les notices et les factures d'un appareil
                s'ajoutent depuis sa fiche, onglet Documents ; les papiers de la maison
                ci-dessous.
              </p>
            )}
            {all.length > 0 && visible.length === 0 && (
              <p className="muted">Aucun document ne correspond à cette recherche.</p>
            )}
            {visible.length > 0 && (
              <ul className="task-list">
                {visible.map((document) => (
                  <li key={document.id} className="task">
                    <div className="task__main">
                      <DocumentLink document={document} />
                      <p className="muted">
                        {docTypeLabel(document.doc_type)} · {storageModeLabel(document.storage_mode)}
                        {documentWhere(document) && ' · '}
                        {documentWhere(document) && (
                          <span className="doc-where">{documentWhere(document)}</span>
                        )}
                      </p>
                      <p>
                        <Attachment document={document} />
                      </p>
                    </div>
                    <div className="doc-actions">
                      <button
                        type="button"
                        className="btn btn--small btn--edit"
                        disabled={busy}
                        onClick={() => {
                          setError(null)
                          setEditing(document)
                        }}
                      >
                        <EditIcon /> Modifier
                      </button>
                      <button
                        type="button"
                        className="btn btn--small btn--delete"
                        disabled={busy}
                        onClick={() => void remove(document.id)}
                      >
                        <TrashIcon /> Supprimer
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <div className="card">
        <h2 className="card__title">Ajouter un papier de la maison</h2>
        <p className="muted">
          L'acte de propriété, l'assurance habitation, le DPE, un diagnostic : ce qui concerne la
          maison et non un appareil. La notice ou la facture d'un équipement s'ajoute depuis sa
          fiche, onglet Documents.
        </p>
        <form className="form" onSubmit={(event) => void add(event)}>
          <div className="doc-form__row">
            <Field label="Type">
              <select
                value={docType}
                onChange={(event) => setDocType(event.target.value as DocType)}
              >
                {HOME_DOC_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {docTypeLabel(value)}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={draft.mode === 'local_file' ? 'Nom (facultatif)' : 'Nom'}
              hint={draft.mode === 'local_file' ? 'Par défaut, le nom du fichier.' : undefined}
            >
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Acte de propriété"
              />
            </Field>
          </div>
          <div className="field">
            <span className="field__label">Où se trouve ce document</span>
            <DocumentInput value={draft} onChange={setDraft} disabled={busy} />
          </div>
          <div className="form__actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              Ajouter
            </button>
          </div>
        </form>
      </div>

      {editing !== null && (
        <DocumentEdit
          document={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            void reload().catch((caught: unknown) => setError(errorMessage(caught)))
          }}
          onError={setError}
        />
      )}
    </section>
  )
}
