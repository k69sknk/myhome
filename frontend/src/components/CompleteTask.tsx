import { useEffect, useRef, useState, type FormEvent } from 'react'

import { ApiError, api } from '../api/client'
import type { Intervention, Member, Task } from '../api/types'
import { errorMessage, formatAmount, formatDate, todayIso } from '../lib/format'
import Field from './Field'
import TaskForm from './TaskForm'
import { EditIcon, TrashIcon } from './icons'

export default function CompleteTask({
  task,
  members,
  onCompleted,
  onEdited,
  onDeleted,
}: {
  task: Task
  members: Member[]
  onCompleted: () => void
  onEdited: () => void
  onDeleted: () => void
}) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [performedOn, setPerformedOn] = useState(todayIso())
  const [performedBy, setPerformedBy] = useState('')
  const [notes, setNotes] = useState('')
  const [isPro, setIsPro] = useState(false)
  const [amount, setAmount] = useState('')
  const inflight = useRef(false)
  const dateInputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [historyOpen, setHistoryOpen] = useState(false)
  const [history, setHistory] = useState<Intervention[] | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (open) dateInputRef.current?.focus()
  }, [open])

  async function refreshHistory() {
    setHistoryError(null)
    try {
      setHistory(await api.taskInterventions(task.id))
    } catch (caught: unknown) {
      setHistoryError(errorMessage(caught))
    }
  }

  /** Invalide le cache d'historique ; le rafraichit tout de suite s'il est
   * affiche, sinon laisse le prochain "Historique" le refaire. */
  async function invalidateHistory() {
    if (historyOpen) {
      await refreshHistory()
    } else {
      setHistory(null)
    }
  }

  async function submitDetails(event: FormEvent) {
    event.preventDefault()
    if (inflight.current) return
    inflight.current = true
    setBusy(true)
    setError(null)
    try {
      const amountCents = isPro && amount.trim() ? Math.round(Number(amount) * 100) : null
      const completed = await api.completeTask(task.id, {
        performed_on: performedOn,
        performed_by: performedBy.trim() || null,
        notes: notes.trim() || null,
        amount_cents: amountCents,
      })
      const file = fileInputRef.current?.files?.[0]
      if (isPro && file && completed.last_intervention_id) {
        try {
          await api.uploadInterventionDocument(completed.last_intervention_id, file)
        } catch (caught: unknown) {
          setError(`Entretien enregistre, mais l'envoi du document a echoue : ${errorMessage(caught)}`)
        }
      }
      setOpen(false)
      setPerformedBy('')
      setNotes('')
      setIsPro(false)
      setAmount('')
      if (fileInputRef.current) fileInputRef.current.value = ''
      await invalidateHistory()
      onCompleted()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      inflight.current = false
      setBusy(false)
    }
  }

  async function toggleHistory() {
    const next = !historyOpen
    setHistoryOpen(next)
    if (next && history === null) {
      await refreshHistory()
    }
  }

  async function removeTask() {
    if (inflight.current) return
    inflight.current = true
    setBusy(true)
    setError(null)
    try {
      await api.deleteTask(task.id)
      onDeleted()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      inflight.current = false
      setBusy(false)
    }
  }

  async function removeIntervention(interventionId: number) {
    if (deletingIds.has(interventionId)) return
    setHistoryError(null)
    setDeletingIds((current) => new Set(current).add(interventionId))
    try {
      await api.deleteIntervention(interventionId)
      await refreshHistory()
    } catch (caught: unknown) {
      if (caught instanceof ApiError && caught.status === 404) {
        // Deja supprimee (double-tap, ou liste pas encore rafraichie) : on
        // resynchronise l'affichage plutot que d'afficher une erreur trompeuse.
        await refreshHistory()
      } else {
        setHistoryError(errorMessage(caught))
      }
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current)
        next.delete(interventionId)
        return next
      })
    }
  }

  return (
    <div className="complete">
      <div className="complete__actions">
        <button
          type="button"
          className={open ? 'btn btn--active' : 'btn btn--primary'}
          disabled={busy}
          aria-expanded={open}
          onClick={() => {
            setEditing(false)
            setOpen((current) => !current)
          }}
        >
          {open ? 'Annuler' : 'Marquer comme fait'}
        </button>
        <button
          type="button"
          className={editing ? 'btn btn--small btn--active' : 'btn btn--small btn--edit'}
          disabled={busy}
          aria-expanded={editing}
          onClick={() => {
            setOpen(false)
            setEditing((current) => !current)
          }}
        >
          <EditIcon /> {editing ? 'Annuler' : 'Modifier'}
        </button>
        {(task.last_completed_on || historyOpen) && (
          <button
            type="button"
            className={historyOpen ? 'btn btn--small btn--active' : 'btn btn--small'}
            onClick={() => void toggleHistory()}
          >
            {historyOpen ? 'Masquer l\'historique' : 'Historique'}
          </button>
        )}
        <button type="button" className="btn btn--small btn--delete" disabled={busy} onClick={() => void removeTask()}>
          <TrashIcon /> Supprimer
        </button>
      </div>
      {error && <p className="status status--error">{error}</p>}
      {editing && (
        <TaskForm
          members={members}
          initial={task}
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await api.patchTask(task.id, body)
            setEditing(false)
            onEdited()
          }}
        />
      )}
      {open && (
        <form className="complete__form" onSubmit={(event) => void submitDetails(event)}>
          <p className="complete__form-hint">Qui l'a fait, quand, et une note si besoin.</p>
          <div className="complete__form-fields">
            <Field label="Date">
              <input
                ref={dateInputRef}
                type="date"
                required
                value={performedOn}
                onChange={(event) => setPerformedOn(event.target.value)}
              />
            </Field>
            <Field label={isPro ? 'Entreprise' : 'Qui (facultatif)'}>
              <input
                type="text"
                value={performedBy}
                onChange={(event) => setPerformedBy(event.target.value)}
                placeholder={isPro ? 'Dupont Chauffage...' : 'Vous, un pro...'}
              />
            </Field>
            <Field label="Note (facultatif)">
              <input
                type="text"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </Field>
          </div>
          <label className="complete__checkbox">
            <input
              type="checkbox"
              checked={isPro}
              onChange={(event) => setIsPro(event.target.checked)}
            />
            Entretien realise par un pro
          </label>
          {isPro && (
            <div className="complete__form-fields">
              <Field label="Montant (facultatif)">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  placeholder="0,00"
                />
              </Field>
              <Field label="Facture / document (facultatif)">
                <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.heic,.doc,.docx" />
              </Field>
            </div>
          )}
          <div className="complete__form-actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              Enregistrer
            </button>
          </div>
        </form>
      )}
      {historyOpen && (
        <div className="complete__history">
          {historyError && <p className="status status--error">{historyError}</p>}
          {history === null && !historyError && <p className="muted">Chargement...</p>}
          {history !== null && history.length === 0 && (
            <p className="muted">Aucun entretien enregistre pour l'instant.</p>
          )}
          {history !== null && history.length > 0 && (
            <ul className="complete__history-list">
              {history.map((entry) => (
                <li key={entry.id}>
                  <div className="complete__history-row">
                    <div>
                      <strong>{formatDate(entry.performed_on)}</strong>
                      {entry.performed_by && <span> · {entry.performed_by}</span>}
                      {entry.cost && (
                        <span> · {formatAmount(entry.cost.amount_cents, entry.cost.currency)}</span>
                      )}
                      {entry.notes && <p className="muted">{entry.notes}</p>}
                      {entry.documents.length > 0 && (
                        <p>
                          {entry.documents.map((document) => (
                            <a
                              key={document.id}
                              href={api.documentFileUrl(document.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="complete__history-doc"
                            >
                              {document.name}
                            </a>
                          ))}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      className="btn btn--small btn--delete"
                      disabled={deletingIds.has(entry.id)}
                      onClick={() => void removeIntervention(entry.id)}
                    >
                      <TrashIcon /> Supprimer
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
