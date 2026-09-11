import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import type { HistoryEntry } from '../api/types'
import { errorMessage, formatAmount, formatDate } from '../lib/format'
import DocumentLink from './DocumentLink'
import { TrashIcon } from './icons'

const PAGE_SIZE = 20

export default function InterventionHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set())
  const inflight = useRef(false)

  async function loadMore() {
    if (inflight.current) return
    inflight.current = true
    setLoading(true)
    setError(null)
    try {
      const page = await api.interventions({ limit: PAGE_SIZE, offset })
      setEntries((current) => [...current, ...page])
      setOffset((current) => current + page.length)
      setHasMore(page.length === PAGE_SIZE)
      setLoaded(true)
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      inflight.current = false
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadMore()
  }, [])

  async function removeEntry(id: number) {
    if (deletingIds.has(id)) return
    setError(null)
    setDeletingIds((current) => new Set(current).add(id))
    try {
      await api.deleteIntervention(id)
      setEntries((current) => current.filter((entry) => entry.id !== id))
    } catch (caught: unknown) {
      if (caught instanceof ApiError && caught.status === 404) {
        // Deja supprimee (double-tap, ou liste pas encore rafraichie) : on
        // aligne l'affichage plutot que d'afficher une erreur trompeuse.
        setEntries((current) => current.filter((entry) => entry.id !== id))
      } else {
        setError(errorMessage(caught))
      }
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current)
        next.delete(id)
        return next
      })
    }
  }

  return (
    <div>
      {error && <p className="status status--error">{error}</p>}
      {!loaded && loading && <p className="muted">Chargement...</p>}
      {loaded && entries.length === 0 && (
        <p className="muted">Aucun entretien realise pour l'instant.</p>
      )}
      {entries.length > 0 && (
        <ul className="complete__history-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <div className="complete__history-row">
                <div>
                  <strong>{formatDate(entry.performed_on)}</strong>
                  {' · '}
                  <Link to={`/equipements/${entry.asset_id}`}>{entry.asset_name}</Link>
                  {entry.task_name && <span> · {entry.task_name}</span>}
                  {entry.performed_by && <span> · {entry.performed_by}</span>}
                  {entry.cost && (
                    <span> · {formatAmount(entry.cost.amount_cents, entry.cost.currency)}</span>
                  )}
                  {entry.notes && <p className="muted">{entry.notes}</p>}
                  {entry.documents.length > 0 && (
                    <p>
                      {entry.documents.map((document) => (
                        <DocumentLink
                          key={document.id}
                          document={document}
                          className="complete__history-doc"
                        />
                      ))}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn--small btn--delete"
                  disabled={deletingIds.has(entry.id)}
                  onClick={() => void removeEntry(entry.id)}
                >
                  <TrashIcon /> Supprimer
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {hasMore && loaded && (
        <button type="button" className="btn btn--small" disabled={loading} onClick={() => void loadMore()}>
          {loading ? 'Chargement...' : 'Voir plus'}
        </button>
      )}
    </div>
  )
}
