import { useState, type FormEvent } from 'react'

import type { RecurrenceType, TaskIn } from '../api/types'
import { errorMessage } from '../lib/format'
import Field from './Field'

type Frequency = Extract<RecurrenceType, 'none' | 'months' | 'years' | 'annual_fixed'>

function defaultFixedDate(): string {
  const year = new Date().getFullYear()
  return `${year}-01-15`
}

export default function TaskForm({
  onCreate,
}: {
  onCreate: (body: TaskIn) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [frequency, setFrequency] = useState<Frequency>('months')
  const [interval, setInterval] = useState(3)
  const [fixedDate, setFixedDate] = useState(defaultFixedDate())
  const [lastCompleted, setLastCompleted] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    const body: TaskIn = {
      name: trimmed,
      recurrence_type: frequency,
      last_completed_on: lastCompleted || null,
    }
    if (frequency === 'months' || frequency === 'years') {
      body.recurrence_interval = interval
    }
    if (frequency === 'annual_fixed') {
      const [, monthPart, dayPart] = fixedDate.split('-')
      body.fixed_month = Number(monthPart)
      body.fixed_day = Number(dayPart)
    }
    setBusy(true)
    setError(null)
    try {
      await onCreate(body)
      setName('')
      setLastCompleted('')
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
          <option value="none">Ponctuel</option>
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
      <Field label="Dernier entretien (facultatif)">
        <input
          type="date"
          value={lastCompleted}
          onChange={(event) => setLastCompleted(event.target.value)}
        />
      </Field>
      {error && <p className="status status--error">{error}</p>}
      <button type="submit" className="btn btn--primary" disabled={busy}>
        Ajouter l'entretien
      </button>
    </form>
  )
}
