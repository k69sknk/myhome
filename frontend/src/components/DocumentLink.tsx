import { api } from '../api/client'
import type { DocumentMeta } from '../api/types'

/** Le nom d'un document, cliquable quand il y a quelque chose a ouvrir.
 *
 *  Le fichier depose se telecharge, le lien externe s'ouvre chez l'utilisateur,
 *  et la reference se lit sur place : elle ne mene nulle part, c'est son propos.
 */
export default function DocumentLink({
  document,
  className,
}: {
  document: DocumentMeta
  className?: string
}) {
  if (document.storage_mode === 'local_file') {
    return (
      <a
        href={api.documentFileUrl(document.id)}
        target="_blank"
        rel="noreferrer"
        className={className}
      >
        {document.name}
      </a>
    )
  }
  if (document.storage_mode === 'external_link' && document.url !== null) {
    return (
      <a href={document.url} target="_blank" rel="noreferrer" className={className}>
        {document.name}
      </a>
    )
  }
  return (
    <span className={className} title={document.reference_note ?? undefined}>
      {document.name}
    </span>
  )
}
