import { useState, type FormEvent } from 'react'

import type { Member, RecurrenceType, ReplacementPartIn, Task, TaskIn } from '../api/types'
import { emptyToNull, errorMessage, todayIso } from '../lib/format'
import Field from './Field'

type Frequency = Extract<RecurrenceType, 'months' | 'years' | 'annual_fixed'> | 'custom_date'

function defaultFixedDate(): string {
  const year = new Date().getFullYear()
  return `${year}-01-15`
}

function initialFrequency(task?: Task): Frequency {
  const type = task?.recurrence_type
  if (type === 'months' || type === 'years' || type === 'annual_fixed') return type
  if (type === 'custom_date' || type === 'none' || !type) return 'custom_date'
  return 'months'
}

interface PartRow {
  name: string
  source: string
}

export default function TaskForm({
  members,
  initial,
  onSubmit,
  onCancel,
}: {
  members: Member[]
  initial?: Task
  onSubmit: (body: TaskIn) => Promise<void>
  onCancel?: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [frequency, setFrequency] = useState<Frequency>(initialFrequency(initial))
  const [interval, setInterval] = useState(initial?.recurrence_interval ?? 3)
  const [fixedDate, setFixedDate] = useState(
    initial?.recurrence_type === 'annual_fixed' && initial.fixed_month && initial.fixed_day
      ? `${new Date().getFullYear()}-${String(initial.fixed_month).padStart(2, '0')}-${String(initial.fixed_day).padStart(2, '0')}`
      : defaultFixedDate(),
  )
  const [customDate, setCustomDate] = useState(initial?.custom_due_date ?? todayIso())
  const [lastCompleted, setLastCompleted] = useState(initial?.last_completed_on ?? '')
  const [parts, setParts] = useState<PartRow[]>(
    initial?.replacement_parts.map((part) => ({ name: part.name, source: part.source ?? '' })) ??
      [],
  )
  const [prepNotes, setPrepNotes] = useState(initial?.preparation_notes ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [assigneeId, setAssigneeId] = useState(
    initial?.assignee_id != null ? String(initial.assignee_id) : '',
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function addPart() {
    setParts((current) => [...current, { name: '', source: '' }])
  }

  function updatePart(index: number, field: 'name' | 'source', value: string) {
    setParts((current) =>
      current.map((part, i) => (i === index ? { ...part, [field]: value } : part)),
    )
  }

  function removePart(index: number) {
    setParts((current) => current.filter((_, i) => i !== index))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    const replacementParts: ReplacementPartIn[] = parts
      .filter((part) => part.name.trim())
      .map((part) => ({ name: part.name.trim(), source: emptyToNull(part.source) }))
    const body: TaskIn = {
      name: trimmed,
      recurrence_type: frequency === 'custom_date' ? 'custom_date' : frequency,
      last_completed_on: lastCompleted || null,
      replacement_parts: replacementParts,
      preparation_notes: emptyToNull(prepNotes),
      notes: emptyToNull(notes),
      assignee_id: assigneeId ? Number(assigneeId) : null,
    }
    if (frequency === 'months' || frequency === 'years') {
      body.recurrence_interval = interval
    }
    if (frequency === 'annual_fixed') {
      const [, monthPart, dayPart] = fixedDate.split('-')
      body.fixed_month = Number(monthPart)
      body.fixed_day = Number(dayPart)
    }
    if (frequency === 'custom_date') {
      body.custom_due_date = customDate
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(body)
      if (!initial) {
        setName('')
        setLastCompleted('')
        setParts([])
        setPrepNotes('')
        setNotes('')
        setAssigneeId('')
      }
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={(event) => void submit(event)}>
      <Field label="Nom de l'entretien">
        <input
          type="text"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Filtres, detartrage..."
        />
      </Field>
      <Field label="Frequence">
        <select
          value={frequency}
          onChange={(event) => setFrequency(event.target.value as Frequency)}
        >
          <option value="months">Tous les X mois</option>
          <option value="years">Tous les X ans</option>
          <option value="annual_fixed">Une fois par an, a date fixe</option>
          <option value="custom_date">Ponctuel</option>
        </select>
      </Field>
      {(frequency === 'months' || frequency === 'years') && (
        <Field label={frequency === 'months' ? 'Tous les combien de mois' : "Tous les combien d'ans"}>
          <input
            type="number"
            min={1}
            value={interval}
            onChange={(event) => setInterval(Number(event.target.value))}
          />
        </Field>
      )}
      {frequency === 'annual_fixed' && (
        <Field label="Date fixe" hint="Seuls le jour et le mois sont retenus, l'annee saisie n'a pas d'importance.">
          <input
            type="date"
            required
            value={fixedDate}
            onChange={(event) => setFixedDate(event.target.value)}
          />
        </Field>
      )}
      {frequency === 'custom_date' && (
        <Field label="Date de l'entretien" hint="Une seule echeance, sans recurrence.">
          <input
            type="date"
            required
            value={customDate}
            onChange={(event) => setCustomDate(event.target.value)}
          />
        </Field>
      )}
      <Field label="Dernier entretien (facultatif)">
        <input
          type="date"
          value={lastCompleted}
          onChange={(event) => setLastCompleted(event.target.value)}
        />
      </Field>
      <Field label="Assigne a (facultatif)">
        <select value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}>
          <option value="">Personne</option>
          {members.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Pieces a remplacer" hint="Facultatif, plusieurs pieces possibles.">
        <div className="complete__form-fields">
          {parts.map((part, index) => (
            <div key={index} className="task-form__part-row">
              <input
                type="text"
                value={part.name}
                onChange={(event) => updatePart(index, 'name', event.target.value)}
                placeholder="Filtre a eau 10 pouces..."
              />
              <input
                type="text"
                value={part.source}
                onChange={(event) => updatePart(index, 'source', event.target.value)}
                placeholder="Lien ou magasin d'achat"
              />
              <button
                type="button"
                className="btn btn--small btn--delete"
                onClick={() => removePart(index)}
                aria-label="Retirer cette piece"
              >
                ✕
              </button>
            </div>
          ))}
          <button type="button" className="btn btn--small" onClick={addPart}>
            + Ajouter une piece
          </button>
        </div>
      </Field>
      <Field label="A prevoir lors de l'entretien" hint="Outils specifiques, produits, autres">
        <textarea
          rows={2}
          value={prepNotes}
          onChange={(event) => setPrepNotes(event.target.value)}
        />
      </Field>
      <Field label="Notes">
        <textarea
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </Field>
      {error && <p className="status status--error">{error}</p>}
      <div className="complete__form-actions">
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {initial ? 'Enregistrer les modifications' : "Ajouter l'entretien"}
        </button>
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            Annuler
          </button>
        )}
      </div>
    </form>
  )
}
