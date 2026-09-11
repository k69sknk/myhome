import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { AssetListItem, Category, Member, Task, TaskStatus } from '../api/types'
import AssetSelect from '../components/AssetSelect'
import CompleteTask from '../components/CompleteTask'
import Field from '../components/Field'
import InterventionHistory from '../components/InterventionHistory'
import PrioritySelect from '../components/PrioritySelect'
import StatusBadge from '../components/StatusBadge'
import TaskForm from '../components/TaskForm'
import TaskPrepInfo from '../components/TaskPrepInfo'
import { errorMessage, formatDate, formatRecurrence, statusLabel } from '../lib/format'

const STATUS_GROUPS: TaskStatus[] = ['overdue', 'due_soon', 'ok', 'unscheduled']

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [assets, setAssets] = useState<AssetListItem[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [selectedAssetId, setSelectedAssetId] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    setTasks(await api.tasks())
  }

  useEffect(() => {
    let cancelled = false
    Promise.all([api.tasks(), api.assets(), api.categories(), api.members()])
      .then(([taskList, assetList, categoryList, memberList]) => {
        if (cancelled) return
        setTasks(taskList)
        setAssets(assetList)
        setCategories(categoryList)
        setMembers(memberList)
      })
      .catch((caught: unknown) => {
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

      <div className="card">
        <h2 className="card__title">Ajouter un entretien</h2>
        <Field label="Equipement" hint="Tapez pour chercher ; si l'equipement n'existe pas encore, proposez de le creer.">
          <AssetSelect
            assets={assets}
            categories={categories}
            value={selectedAssetId}
            onChange={setSelectedAssetId}
            onCreated={(asset) => setAssets((current) => [...current, asset])}
          />
        </Field>
        {selectedAssetId && (
          <TaskForm
            members={members}
            onMemberCreated={(member) => setMembers((current) => [...current, member])}
            onSubmit={async (body) => {
              await api.createTask(Number(selectedAssetId), body)
              await reload()
            }}
          />
        )}
      </div>

      <div className="card">
        <h2 className="card__title">A faire</h2>
        {tasks === null && !error && <p className="muted">Chargement...</p>}
        {tasks && tasks.length === 0 && (
          <p className="muted">Aucun entretien. Ajoutez-en ci-dessus.</p>
        )}
        {tasks &&
          STATUS_GROUPS.map((status) => {
            const group = tasks.filter((task) => task.status === status)
            if (group.length === 0) return null
            return (
              <div key={status}>
                <h3 className="card__subtitle">
                  {statusLabel(status)} ({group.length})
                </h3>
                <ul className="task-list task-list--page">
                  {group.map((task) => (
                    <li key={task.id} className="task card">
                      <div className="task__main">
                        <strong>{task.name}</strong>
                        <StatusBadge status={task.status} />
                        <PrioritySelect
                          task={task}
                          onChanged={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                        />
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
                        <TaskPrepInfo task={task} />
                      </div>
                      <CompleteTask
                        task={task}
                        members={members}
                        onMemberCreated={(member) => setMembers((current) => [...current, member])}
                        onCompleted={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                        onEdited={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                        onDeleted={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
      </div>

      <div className="card">
        <h2 className="card__title">Historique</h2>
        <InterventionHistory />
      </div>
    </section>
  )
}
