import { useState, type FormEvent } from 'react'

import type { Member, RecurrenceType, ReplacementPartIn, TaskIn, TaskPriority } from '../api/types'
import { emptyToNull, errorMessage, monthName, priorityLabel, todayIso } from '../lib/format'
import Field from './Field'
import { useToast } from './Toast'

type Frequency =
  | Extract<RecurrenceType, 'days' | 'months' | 'years' | 'annual_fixed'>
  | 'custom_date'

/** Les frequences a intervalle sont les seules qui acceptent une saison (ADR-0010). */
const INTERVAL_FREQUENCIES: Frequency[] = ['days', 'months', 'years']

const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

const PRIORITIES: TaskPriority[] = ['low', 'normal', 'high', 'critical']

function defaultFixedDate(): string {
  const year = new Date().getFullYear()
  return `${year}-01-15`
}

/** Ce dont le formulaire a besoin pour se pre-remplir : un entretien existant
 *  comme un brouillon du didacticiel, qui n'a pas encore d'identifiant. */
export interface TaskFormInitial {
  name?: string
  priority?: TaskPriority
  recurrence_type?: RecurrenceType | string
  recurrence_interval?: number | null
  fixed_month?: number | null
  fixed_day?: number | null
  custom_due_date?: string | null
  season_start_month?: number | null
  season_end_month?: number | null
  last_completed_on?: string | null
  replacement_parts?: { name: string; source?: string | null }[]
  preparation_notes?: string | null
  notes?: string | null
  assignee_id?: number | null
}

function initialFrequency(task?: TaskFormInitial): Frequency {
  const type = task?.recurrence_type
  if (type === 'days' || type === 'months' || type === 'years' || type === 'annual_fixed') {
    return type
  }
  return 'custom_date'
}

function intervalUnit(frequency: Frequency): string {
  if (frequency === 'days') return 'de jours'
  if (frequency === 'years') return "d'ans"
  return 'de mois'
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
  initial?: TaskFormInitial
  onSubmit: (body: TaskIn) => Promise<void>
  onCancel?: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [priority, setPriority] = useState<TaskPriority>(initial?.priority ?? 'normal')
  const [frequency, setFrequency] = useState<Frequency>(initialFrequency(initial))
  const [interval, setInterval] = useState(initial?.recurrence_interval ?? 3)
  const [seasonal, setSeasonal] = useState(initial?.season_start_month != null)
  const [seasonStart, setSeasonStart] = useState(initial?.season_start_month ?? 3)
  const [seasonEnd, setSeasonEnd] = useState(initial?.season_end_month ?? 10)
  const [fixedDate, setFixedDate] = useState(
    initial?.recurrence_type === 'annual_fixed' && initial.fixed_month && initial.fixed_day
      ? `${new Date().getFullYear()}-${String(initial.fixed_month).padStart(2, '0')}-${String(initial.fixed_day).padStart(2, '0')}`
      : defaultFixedDate(),
  )
  const [customDate, setCustomDate] = useState(initial?.custom_due_date ?? todayIso())
  const [lastCompleted, setLastCompleted] = useState(initial?.last_completed_on ?? '')
  const [parts, setParts] = useState<PartRow[]>(
    initial?.replacement_parts?.map((part) => ({ name: part.name, source: part.source ?? '' })) ??
      [],
  )
  const [prepNotes, setPrepNotes] = useState(initial?.preparation_notes ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [assigneeId, setAssigneeId] = useState(
    initial?.assignee_id != null ? String(initial.assignee_id) : '',
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { showToast } = useToast()

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
      priority,
      recurrence_type: frequency === 'custom_date' ? 'custom_date' : frequency,
      last_completed_on: lastCompleted || null,
      replacement_parts: replacementParts,
      preparation_notes: emptyToNull(prepNotes),
      notes: emptyToNull(notes),
      assignee_id: assigneeId ? Number(assigneeId) : null,
    }
    if (INTERVAL_FREQUENCIES.includes(frequency)) {
      body.recurrence_interval = interval
      if (seasonal) {
        body.season_start_month = seasonStart
        body.season_end_month = seasonEnd
      }
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
      showToast(initial ? 'Entretien modifié' : 'Entretien ajouté')
      if (!initial) {
        setName('')
        setPriority('normal')
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
      <Field label="Priorite">
        <select
          value={priority}
          onChange={(event) => setPriority(event.target.value as TaskPriority)}
        >
          {PRIORITIES.map((value) => (
            <option key={value} value={value}>
              {priorityLabel(value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Frequence">
        <select
          value={frequency}
          onChange={(event) => setFrequency(event.target.value as Frequency)}
        >
          <option value="days">Tous les X jours</option>
          <option value="months">Tous les X mois</option>
          <option value="years">Tous les X ans</option>
          <option value="annual_fixed">Une fois par an, a date fixe</option>
          <option value="custom_date">Ponctuel</option>
        </select>
      </Field>
      {INTERVAL_FREQUENCIES.includes(frequency) && (
        <>
          <Field label={`Tous les combien ${intervalUnit(frequency)}`}>
            <input
              type="number"
              min={1}
              value={interval}
              onChange={(event) => setInterval(Number(event.target.value))}
            />
          </Field>
          <Field
            label="Seulement a la belle saison"
            hint="Pour ce qui ne vaut qu'une partie de l'annee : tonte, piscine. Hors saison, l'echeance se suspend au lieu d'afficher une tache en retard tout l'hiver."
          >
            <input
              type="checkbox"
              checked={seasonal}
              onChange={(event) => setSeasonal(event.target.checked)}
            />
          </Field>
          {seasonal && (
            <Field label="De ... a ..." hint="Mois inclus. La saison peut passer l'hiver (novembre a fevrier).">
              <div className="task-form__part-row">
                <select
                  value={seasonStart}
                  onChange={(event) => setSeasonStart(Number(event.target.value))}
                >
                  {MONTHS.map((month) => (
                    <option key={month} value={month}>
                      {monthName(month)}
                    </option>
                  ))}
                </select>
                <select
                  value={seasonEnd}
                  onChange={(event) => setSeasonEnd(Number(event.target.value))}
                >
                  {MONTHS.map((month) => (
                    <option key={month} value={month}>
                      {monthName(month)}
                    </option>
                  ))}
                </select>
              </div>
            </Field>
          )}
        </>
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
