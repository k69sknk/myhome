import { useRef, useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { Task } from '../api/types'
import { errorMessage, todayIso } from '../lib/format'
import Field from './Field'

export default function CompleteTask({
  task,
  onCompleted,
}: {
  task: Task
  onCompleted: () => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [performedOn, setPerformedOn] = useState(todayIso())
  const [performedBy, setPerformedBy] = useState('')
  const [notes, setNotes] = useState('')
  const inflight = useRef(false)

  async function markToday() {
    if (inflight.current) return
    inflight.current = true
    setBusy(true)
    setError(null)
    try {
      await api.completeTask(task.id, { performed_on: todayIso() })
      onCompleted()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      inflight.current = false
      setBusy(false)
    }
  }

  async function submitDetails(event: FormEvent) {
    event.preventDefault()
    if (inflight.current) return
    inflight.current = true
    setBusy(true)
    setError(null)
    try {
      await api.completeTask(task.id, {
        performed_on: performedOn,
        performed_by: performedBy.trim() || null,
        notes: notes.trim() || null,
      })
      setOpen(false)
      setPerformedBy('')
      setNotes('')
      onCompleted()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      inflight.current = false
      setBusy(false)
    }
  }

  return (
    <div className="complete">
      <div className="complete__actions">
        <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void markToday()}>
          Fait
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => setOpen((current) => !current)}
        >
          Preciser
        </button>
      </div>
      {error && <p className="status status--error">{error}</p>}
      {open && (
        <form className="complete__form" onSubmit={(event) => void submitDetails(event)}>
          <Field label="Date">
            <input
              type="date"
              required
              value={performedOn}
              onChange={(event) => setPerformedOn(event.target.value)}
            />
          </Field>
          <Field label="Qui (facultatif)">
            <input
              type="text"
              value={performedBy}
              onChange={(event) => setPerformedBy(event.target.value)}
              placeholder="Vous, un pro..."
            />
          </Field>
          <Field label="Note (facultatif)">
            <input
              type="text"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Enregistrer
          </button>
        </form>
      )}
    </div>
  )
}
