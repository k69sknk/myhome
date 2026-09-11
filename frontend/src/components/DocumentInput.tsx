import { useEffect, useRef } from 'react'

import type { DocumentDraft } from '../api/types'

export const DOCUMENT_ACCEPT = '.pdf,.jpg,.jpeg,.png,.heic,.doc,.docx'

/** Les trois modes, dans l'ordre et avec le meme poids visuel.
 *
 *  L'adr/0002 le demande explicitement : si le fichier local est presente comme
 *  le choix par defaut et les deux autres comme des options secondaires, la
 *  decision de modeliser trois modes n'aura servi a rien sur le plan de la
 *  confidentialite. Trois boutons de meme taille, trois phrases d'explication de
 *  meme longueur : le choix est pose, pas suggere.
 */
const MODES: { mode: DocumentDraft['mode']; label: string }[] = [
  { mode: 'local_file', label: 'Un fichier' },
  { mode: 'external_link', label: 'Un lien' },
  { mode: 'reference_note', label: 'Une note' },
]

const HINTS: Record<DocumentDraft['mode'], string> = {
  local_file:
    "Le fichier est déposé dans l'application et reste chez vous. PDF, photo ou document Word, 10 Mo maximum.",
  external_link:
    "L'adresse du document sur votre Nextcloud, votre Drive ou votre NAS. L'application n'en garde que le lien.",
  reference_note:
    "Simplement où le trouver : « e-mail du 12/05/2024 », « classeur chauffage au garage ». Rien n'est stocké.",
}

function switchTo(mode: DocumentDraft['mode']): DocumentDraft {
  if (mode === 'local_file') return { mode, file: null }
  if (mode === 'external_link') return { mode, url: '' }
  return { mode, note: '' }
}

export default function DocumentInput({
  value,
  onChange,
  disabled = false,
}: {
  value: DocumentDraft
  onChange: (draft: DocumentDraft) => void
  disabled?: boolean
}) {
  const fileInput = useRef<HTMLInputElement>(null)

  // Le parent remet le brouillon a vide apres enregistrement ; l'input fichier,
  // lui, garderait le nom du fichier choisi.
  useEffect(() => {
    if (value.mode === 'local_file' && value.file === null && fileInput.current) {
      fileInput.current.value = ''
    }
  }, [value])

  return (
    <div className="doc-input">
      <div className="doc-input__modes" role="group" aria-label="Ou se trouve ce document">
        {MODES.map((entry) => (
          <button
            key={entry.mode}
            type="button"
            className={`btn${value.mode === entry.mode ? ' btn--active' : ''}`}
            aria-pressed={value.mode === entry.mode}
            disabled={disabled}
            onClick={() => onChange(switchTo(entry.mode))}
          >
            {entry.label}
          </button>
        ))}
      </div>
      {value.mode === 'local_file' && (
        <input
          ref={fileInput}
          type="file"
          accept={DOCUMENT_ACCEPT}
          disabled={disabled}
          onChange={(event) => onChange({ mode: 'local_file', file: event.target.files?.[0] ?? null })}
        />
      )}
      {value.mode === 'external_link' && (
        <input
          type="url"
          value={value.url}
          disabled={disabled}
          placeholder="https://nextcloud.exemple/factures/chaudiere.pdf"
          onChange={(event) => onChange({ mode: 'external_link', url: event.target.value })}
        />
      )}
      {value.mode === 'reference_note' && (
        <input
          type="text"
          value={value.note}
          disabled={disabled}
          placeholder="e-mail du 12/05/2024"
          onChange={(event) => onChange({ mode: 'reference_note', note: event.target.value })}
        />
      )}
      <p className="field__hint">{HINTS[value.mode]}</p>
    </div>
  )
}
