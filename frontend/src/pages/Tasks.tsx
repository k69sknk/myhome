import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { Task } from '../api/types'
import CompleteTask from '../components/CompleteTask'
import StatusBadge from '../components/StatusBadge'
import { errorMessage, formatDate, formatRecurrence } from '../lib/format'

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    setTasks(await api.tasks())
  }

  useEffect(() => {
    let cancelled = false
    reload().catch((caught: unknown) => {
      if (!cancelled) setError(errorMessage(caught))
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="page">
      <h1 className="page__title">Entretiens</h1>
      <p className="page__lead">Toutes les taches, tous appareils confondus.</p>

      {error && <p className="status status--error">{error}</p>}
      {tasks === null && !error && <p className="muted">Chargement...</p>}
      {tasks && tasks.length === 0 && (
        <p className="muted">
          Aucun entretien. Ajoutez-en depuis la{' '}
          <Link to="/equipements">fiche d'un equipement</Link>.
        </p>
      )}
      {tasks && tasks.length > 0 && (
        <ul className="task-list task-list--page">
          {tasks.map((task) => (
            <li key={task.id} className="task card">
              <div className="task__main">
                <strong>{task.name}</strong>
                <StatusBadge status={task.status} />
                <p className="muted">
                  {task.asset_id ? (
                    <Link to={`/equipements/${task.asset_id}`}>{task.asset_name}</Link>
                  ) : (
                    task.asset_name
                  )}
                  {task.location_path ? ` · ${task.location_path}` : ''}
                  {' · '}
                  {formatRecurrence(task)}
                  {' · dernier '}
                  {formatDate(task.last_completed_on)}
                  {' · prochain '}
                  {formatDate(task.next_due_on)}
                </p>
              </div>
              <CompleteTask
                task={task}
                onCompleted={() => void reload().catch((caught) => setError(errorMessage(caught)))}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
