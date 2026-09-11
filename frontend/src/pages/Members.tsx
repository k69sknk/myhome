import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import type { HaPersonOption, HistoryEntry, Member, MemberIn, MemberType, Task } from '../api/types'
import Field from '../components/Field'
import StatusBadge from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import { EditIcon, TrashIcon } from '../components/icons'
import { errorMessage, formatAmount, formatDate, formatRecurrence } from '../lib/format'

const MEMBER_TYPE_LABEL: Record<MemberType, string> = {
  household: 'Foyer',
  friend: 'Ami',
}

export default function Members() {
  const [members, setMembers] = useState<Member[] | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [persons, setPersons] = useState<HaPersonOption[]>([])
  const [notifyServices, setNotifyServices] = useState<string[]>([])
  const [haError, setHaError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [memberType, setMemberType] = useState<MemberType>('household')
  const [contact, setContact] = useState('')
  const [personEntityId, setPersonEntityId] = useState('')
  const [notifyService, setNotifyService] = useState('')
  const { showToast } = useToast()

  async function reload() {
    const [memberList, taskList] = await Promise.all([api.members(), api.tasks()])
    setMembers(memberList)
    setTasks(taskList)
  }

  useEffect(() => {
    let cancelled = false
    reload().catch((caught: unknown) => {
      if (!cancelled) setError(errorMessage(caught))
    })
    Promise.all([api.haPersons(), api.haNotifyServices()])
      .then(([personList, serviceList]) => {
        if (cancelled) return
        setPersons(personList)
        setNotifyServices(serviceList)
      })
      .catch((caught: unknown) => {
        if (cancelled) return
        setHaError(
          caught instanceof ApiError
            ? caught.message
            : 'Home Assistant injoignable pour lister les personnes et services de notification.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function addMember(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setError(null)
    const body: MemberIn = {
      name: trimmed,
      member_type: memberType,
      contact: contact.trim() || null,
      ha_person_entity_id: personEntityId || null,
      ha_notify_service: notifyService || null,
    }
    try {
      await api.createMember(body)
      setName('')
      setContact('')
      setPersonEntityId('')
      setNotifyService('')
      showToast('Membre ajouté')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function removeMember(id: number) {
    setError(null)
    try {
      await api.deleteMember(id)
      showToast('Membre supprimé')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Membres</h1>
      <p className="page__lead">
        Le foyer et les proches a qui confier un entretien. Les entreprises ont leur propre
        annuaire, <Link to="/prestataires">Prestataires</Link>.
      </p>

      {error && <p className="status status--error">{error}</p>}

      <div className="card">
        <h2 className="card__title">Ajouter un membre</h2>
        {haError && <p className="muted">{haError}</p>}
        <form className="form form--inline" onSubmit={(event) => void addMember(event)}>
          <Field label="Nom">
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Alice, Dupont Chauffage..."
            />
          </Field>
          <Field label="Type">
            <select
              value={memberType}
              onChange={(event) => setMemberType(event.target.value as MemberType)}
            >
              <option value="household">Foyer</option>
              <option value="friend">Ami</option>
            </select>
          </Field>
          <Field label="Contact (facultatif)">
            <input
              value={contact}
              onChange={(event) => setContact(event.target.value)}
              placeholder="Telephone, email..."
            />
          </Field>
          {!haError && (
            <>
              <Field label="Personne Home Assistant (facultatif)">
                <select value={personEntityId} onChange={(event) => setPersonEntityId(event.target.value)}>
                  <option value="">Aucune</option>
                  {persons.map((person) => (
                    <option key={person.entity_id} value={person.entity_id}>
                      {person.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Service de notification (facultatif)">
                <select value={notifyService} onChange={(event) => setNotifyService(event.target.value)}>
                  <option value="">Aucun</option>
                  {notifyServices.map((service) => (
                    <option key={service} value={service}>
                      {service}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          )}
          <button type="submit" className="btn btn--primary">
            Ajouter
          </button>
        </form>
      </div>

      <div className="card">
        <h2 className="card__title">Annuaire</h2>
        {members === null && !error && <p className="muted">Chargement...</p>}
        {members && members.length === 0 && <p className="muted">Aucun membre pour l'instant.</p>}
        {members && members.length > 0 && (
          <ul className="tree">
            {members.map((member) => (
              <MemberRow
                key={member.id}
                member={member}
                tasks={tasks.filter((task) => task.assignee_id === member.id)}
                persons={persons}
                notifyServices={notifyServices}
                haError={haError}
                onError={setError}
                onChanged={() => void reload()}
                onDelete={() => void removeMember(member.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function MemberRow({
  member,
  tasks,
  persons,
  notifyServices,
  haError,
  onError,
  onChanged,
  onDelete,
}: {
  member: Member
  tasks: Task[]
  persons: HaPersonOption[]
  notifyServices: string[]
  haError: string | null
  onError: (message: string | null) => void
  onChanged: () => void
  onDelete: () => void
}) {
  const [renaming, setRenaming] = useState(false)
  /** Ce que ce membre a deja realise. Charge a la demande, comme l'historique
   *  d'un entretien : la plupart des lignes de l'annuaire ne seront pas ouvertes. */
  const [history, setHistory] = useState<HistoryEntry[] | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [name, setName] = useState(member.name)
  const [memberType, setMemberType] = useState<MemberType>(member.member_type)
  const [contact, setContact] = useState(member.contact ?? '')
  const [personEntityId, setPersonEntityId] = useState(member.ha_person_entity_id ?? '')
  const [notifyService, setNotifyService] = useState(member.ha_notify_service ?? '')
  const { showToast } = useToast()

  async function save(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchMember(member.id, {
        name: name.trim(),
        member_type: memberType,
        contact: contact.trim() || null,
        ha_person_entity_id: personEntityId || null,
        ha_notify_service: notifyService || null,
      })
      setRenaming(false)
      showToast('Membre modifié')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  async function toggleHistory() {
    const next = !historyOpen
    setHistoryOpen(next)
    if (next && history === null) {
      try {
        setHistory(await api.interventions({ limit: 20, offset: 0, memberId: member.id }))
      } catch (caught: unknown) {
        onError(errorMessage(caught))
      }
    }
  }

  return (
    <li>
      <div className="tree__row">
        <strong>{member.name}</strong>
        <span className="muted">{MEMBER_TYPE_LABEL[member.member_type]}</span>
        {member.contact && <span className="muted">{member.contact}</span>}
        <button type="button" className="btn btn--small" onClick={() => void toggleHistory()}>
          {historyOpen ? 'Masquer' : 'Interventions'}
        </button>
        <button
          type="button"
          className="btn btn--small btn--edit"
          onClick={() => setRenaming((current) => !current)}
        >
          <EditIcon /> Modifier
        </button>
        <button type="button" className="btn btn--small btn--delete" onClick={onDelete}>
          <TrashIcon /> Supprimer
        </button>
      </div>
      {renaming && (
        <form className="form form--inline" onSubmit={(event) => void save(event)}>
          <Field label="Nom">
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="Type">
            <select
              value={memberType}
              onChange={(event) => setMemberType(event.target.value as MemberType)}
            >
              <option value="household">Foyer</option>
              <option value="friend">Ami</option>
            </select>
          </Field>
          <Field label="Contact">
            <input value={contact} onChange={(event) => setContact(event.target.value)} />
          </Field>
          {!haError && (
            <>
              <Field label="Personne Home Assistant">
                <select value={personEntityId} onChange={(event) => setPersonEntityId(event.target.value)}>
                  <option value="">Aucune</option>
                  {persons.map((person) => (
                    <option key={person.entity_id} value={person.entity_id}>
                      {person.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Service de notification">
                <select value={notifyService} onChange={(event) => setNotifyService(event.target.value)}>
                  <option value="">Aucun</option>
                  {notifyServices.map((service) => (
                    <option key={service} value={service}>
                      {service}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          )}
          <button type="submit" className="btn btn--primary btn--small">
            OK
          </button>
        </form>
      )}
      {historyOpen && (
        <ul className="rows">
          {history === null && (
            <li>
              <span className="muted">Chargement...</span>
            </li>
          )}
          {history !== null && history.length === 0 && (
            <li>
              <span className="muted">
                Aucun entretien realise a son nom. L'historique se remplit quand on choisit cette
                fiche en marquant un entretien comme fait.
              </span>
            </li>
          )}
          {history?.map((entry) => (
            <li key={entry.id}>
              <div className="rows__link">
                <span>
                  <Link to={`/equipements/${entry.asset_id}`}>
                    {entry.task_name ?? entry.asset_name}
                  </Link>
                  <span className="muted">
                    {entry.task_name ? ` · ${entry.asset_name}` : ''}
                    {' · '}
                    {formatDate(entry.performed_on)}
                    {entry.cost
                      ? ` · ${formatAmount(entry.cost.amount_cents, entry.cost.currency)}`
                      : ''}
                  </span>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {tasks.length > 0 && (
        <ul className="rows">
          {tasks.map((task) => (
            <li key={task.id}>
              <div className="rows__link">
                <span>
                  {task.asset_id ? (
                    <Link to={`/equipements/${task.asset_id}`}>{task.name}</Link>
                  ) : (
                    task.name
                  )}
                  <span className="muted">
                    {task.asset_name}
                    {' · '}
                    {formatRecurrence(task)}
                    {' · prochain '}
                    {formatDate(task.next_due_on)}
                  </span>
                </span>
                <StatusBadge status={task.status} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
