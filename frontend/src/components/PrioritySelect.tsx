import { useState } from 'react'

import { api } from '../api/client'
import type { Task, TaskPriority } from '../api/types'
import { errorMessage, priorityLabel } from '../lib/format'

const PRIORITIES: TaskPriority[] = ['low', 'normal', 'high', 'critical']

/**
 * Edition rapide de la priorite d'un entretien, directement depuis la liste
 * ou la fiche equipement. Si l'entretien est en retard, la couleur affichee
 * reste "urgente" quelle que soit la valeur stockee (cf. spec ClickUp 869ezy08h) ;
 * la valeur selectionnee, elle, reste la priorite reellement enregistree.
 */
export default function PrioritySelect({
  task,
  onChanged,
}: {
  task: Task
  onChanged: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const forcedUrgent = task.status === 'overdue' && task.priority !== 'critical'

  async function changePriority(priority: TaskPriority) {
    if (priority === task.priority || busy) return
    setBusy(true)
    setError(null)
    try {
      await api.patchTask(task.id, { priority })
      onChanged()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="priority-select">
      {forcedUrgent && (
        <span
          className="badge badge--priority-critical"
          title="Entretien en retard : affiche comme urgent quelle que soit la priorite enregistree."
        >
          {priorityLabel('critical')}
        </span>
      )}
      <select
        className={`badge badge--priority-${task.priority}`}
        value={task.priority}
        disabled={busy}
        aria-label="Priorite de l'entretien"
        onChange={(event) => void changePriority(event.target.value as TaskPriority)}
      >
        {PRIORITIES.map((value) => (
          <option key={value} value={value}>
            {priorityLabel(value)}
          </option>
        ))}
      </select>
      {error && <span className="status status--error priority-select__error">{error}</span>}
    </span>
  )
}
