import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type {
  CalendarSyncResult,
  HaCalendarOption,
  Home,
  LocationType,
  ReminderRunResult,
} from '../api/types'
import Field from '../components/Field'
import { useToast } from '../components/Toast'
import { EditIcon, TrashIcon } from '../components/icons'
import { errorMessage } from '../lib/format'

export default function Settings() {
  const [home, setHome] = useState<Home | null>(null)
  const [homeName, setHomeName] = useState('')
  const [threshold, setThreshold] = useState('')
  const [types, setTypes] = useState<LocationType[]>([])
  const [newTypeName, setNewTypeName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [calendars, setCalendars] = useState<HaCalendarOption[]>([])
  const [calendarsError, setCalendarsError] = useState<string | null>(null)
  const [calendarEntityId, setCalendarEntityId] = useState('')
  const [calendarSyncEnabled, setCalendarSyncEnabled] = useState(false)
  const [syncResult, setSyncResult] = useState<CalendarSyncResult | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const [taskNotificationsEnabled, setTaskNotificationsEnabled] = useState(false)
  const [reminderHour, setReminderHour] = useState('8')
  const [defaultNotifyService, setDefaultNotifyService] = useState('')
  const [notifyServices, setNotifyServices] = useState<string[]>([])
  const [notifyServicesError, setNotifyServicesError] = useState<string | null>(null)
  const [reminderResult, setReminderResult] = useState<ReminderRunResult | null>(null)
  const [reminderError, setReminderError] = useState<string | null>(null)
  const [remindersRunning, setRemindersRunning] = useState(false)
  const { showToast } = useToast()

  async function reload() {
    const [nextHome, nextTypes] = await Promise.all([api.home(), api.locationTypes()])
    setHome(nextHome)
    setHomeName(nextHome.name)
    setThreshold(String(nextHome.due_soon_threshold_days))
    setTypes(nextTypes)
    setCalendarEntityId(nextHome.ha_calendar_entity_id ?? '')
    setCalendarSyncEnabled(nextHome.ha_calendar_sync_enabled)
    setTaskNotificationsEnabled(nextHome.task_notifications_enabled)
    setReminderHour(String(nextHome.reminder_hour))
    setDefaultNotifyService(nextHome.default_notify_service ?? '')

    try {
      setCalendars(await api.haCalendars())
      setCalendarsError(null)
    } catch (caught: unknown) {
      setCalendarsError(errorMessage(caught))
    }

    try {
      setNotifyServices(await api.haNotifyServices())
      setNotifyServicesError(null)
    } catch (caught: unknown) {
      setNotifyServicesError(errorMessage(caught))
    }
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

  async function saveHome(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const updated = await api.patchHome({
        name: homeName.trim(),
        due_soon_threshold_days: Number(threshold),
      })
      setHome(updated)
      setThreshold(String(updated.due_soon_threshold_days))
      showToast('Réglages enregistrés')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function saveCalendarSync(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const updated = await api.patchHome({
        ha_calendar_entity_id: calendarEntityId || null,
        ha_calendar_sync_enabled: calendarSyncEnabled,
      })
      setHome(updated)
      showToast('Réglages enregistrés')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function syncNow() {
    setSyncing(true)
    setSyncError(null)
    setSyncResult(null)
    try {
      setSyncResult(await api.runCalendarSync())
    } catch (caught: unknown) {
      setSyncError(errorMessage(caught))
    } finally {
      setSyncing(false)
    }
  }

  async function toggleTaskNotifications(enabled: boolean) {
    setError(null)
    try {
      const updated = await api.patchHome({ task_notifications_enabled: enabled })
      setHome(updated)
      setTaskNotificationsEnabled(updated.task_notifications_enabled)
      showToast(enabled ? 'Notifications activées' : 'Notifications désactivées')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function saveReminders(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const updated = await api.patchHome({
        reminder_hour: Number(reminderHour),
        default_notify_service: defaultNotifyService || null,
      })
      setHome(updated)
      setReminderHour(String(updated.reminder_hour))
      showToast('Réglages enregistrés')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function sendRemindersNow() {
    setRemindersRunning(true)
    setReminderError(null)
    setReminderResult(null)
    try {
      setReminderResult(await api.runReminders())
    } catch (caught: unknown) {
      setReminderError(errorMessage(caught))
    } finally {
      setRemindersRunning(false)
    }
  }

  async function addType(event: FormEvent) {
    event.preventDefault()
    const name = newTypeName.trim()
    if (!name) return
    setError(null)
    try {
      await api.createLocationType({ name })
      setNewTypeName('')
      showToast('Type ajouté')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function removeType(id: number) {
    setError(null)
    try {
      await api.deleteLocationType(id)
      showToast('Type supprimé')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Paramètres</h1>
      <p className="page__lead">Réglages de la maison et types de lieux personnalisables.</p>

      {error && <p className="status status--error">{error}</p>}

      <div className="card">
        <h2 className="card__title">Configurer MaBarak</h2>
        <p className="muted">
          Le tour guidé de la maison : vous cochez vos pièces, ce que vous avez dans chacune, et
          l'application vous propose les entretiens correspondants. Vous pouvez le relancer autant
          de fois que vous voulez pour compléter — ce qui existe déjà n'est jamais recréé ni
          reproposé.
        </p>
        <div className="form__actions">
          <Link to="/demarrage" className="btn btn--primary">
            Faire le tour de la maison
          </Link>
        </div>
      </div>

      {home && (
        <div className="card">
          <h2 className="card__title">Maison</h2>
          <form className="form form--inline" onSubmit={(event) => void saveHome(event)}>
            <Field label="Nom de la maison">
              <input value={homeName} onChange={(event) => setHomeName(event.target.value)} />
            </Field>
            <Field
              label="Seuil 'bientot' (jours)"
              hint="Plafond. Un entretien mensuel ou hebdomadaire se resserre deja automatiquement selon sa propre frequence ; ce seuil s'applique tel quel aux entretiens annuels ou ponctuels, et peut resserrer les autres si tu le baisses."
            >
              <input
                type="number"
                required
                min={0}
                value={threshold}
                onChange={(event) => setThreshold(event.target.value)}
              />
            </Field>
            <button type="submit" className="btn">
              Enregistrer
            </button>
          </form>
        </div>
      )}

      <div className="card">
        <h2 className="card__title">Calendrier Home Assistant</h2>
        <p className="muted">
          Pousse les entretiens a venir vers un calendrier Home Assistant existant (Local
          Calendar, CalDAV...). Certains calendriers (Google Calendar, par exemple) ne permettent
          pas la creation d'evenements depuis Home Assistant : la synchronisation te previendra
          si c'est le cas.
        </p>
        {calendarsError && <p className="status status--error">{calendarsError}</p>}
        {!calendarsError && (
          <>
            <form className="form form--inline" onSubmit={(event) => void saveCalendarSync(event)}>
              <Field label="Calendrier cible">
                <select
                  value={calendarEntityId}
                  onChange={(event) => setCalendarEntityId(event.target.value)}
                >
                  <option value="">Aucun</option>
                  {calendars.map((calendar) => (
                    <option key={calendar.entity_id} value={calendar.entity_id}>
                      {calendar.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Synchronisation active">
                <input
                  type="checkbox"
                  checked={calendarSyncEnabled}
                  onChange={(event) => setCalendarSyncEnabled(event.target.checked)}
                />
              </Field>
              <button type="submit" className="btn">
                Enregistrer
              </button>
            </form>
            <button
              type="button"
              className="btn btn--small"
              disabled={syncing || !home?.ha_calendar_sync_enabled || !home?.ha_calendar_entity_id}
              onClick={() => void syncNow()}
            >
              {syncing ? 'Synchronisation...' : 'Synchroniser maintenant'}
            </button>
            {syncResult && (
              <p className="muted">
                {syncResult.created} cree(s), {syncResult.deleted} supprime(s),{' '}
                {syncResult.skipped} deja a jour.
              </p>
            )}
            {syncResult && syncResult.errors.length > 0 && (
              <p className="status status--error">{syncResult.errors.join(' ')}</p>
            )}
            {syncError && <p className="status status--error">{syncError}</p>}
          </>
        )}
      </div>

      <div className="card">
        <h2 className="card__title">Notifications</h2>
        <p className="muted">
          Un planning qu'il faut penser a aller consulter est un planning que personne ne suit.
          Une fois coche, MaBarak previent via Home Assistant : quand un entretien est confie a
          quelqu'un, et chaque jour a heure fixe pour ce qui arrive a echeance ou traine en
          retard.
        </p>
        <label className="complete__checkbox">
          <input
            type="checkbox"
            checked={taskNotificationsEnabled}
            onChange={(event) => void toggleTaskNotifications(event.target.checked)}
          />
          Envoyer les notifications via Home Assistant
        </label>

        {taskNotificationsEnabled && (
          <>
            <p className="muted">
              Un seul message par personne et par passage, jamais un par entretien. Un entretien
              deja signale se tait une semaine, meme s'il reste en retard.
            </p>
            {notifyServicesError && (
              <p className="status status--error">{notifyServicesError}</p>
            )}
            <form className="form form--inline" onSubmit={(event) => void saveReminders(event)}>
              <Field label="Heure du rappel" hint="Heure locale de Home Assistant.">
                <input
                  type="number"
                  required
                  min={0}
                  max={23}
                  value={reminderHour}
                  onChange={(event) => setReminderHour(event.target.value)}
                />
              </Field>
              <Field
                label="Destinataire par defaut"
                hint="Utilise pour les entretiens que personne n'a pris en charge. Chaque personne ayant son propre service de notification dans Membres recoit les siens."
              >
                <select
                  value={defaultNotifyService}
                  onChange={(event) => setDefaultNotifyService(event.target.value)}
                >
                  <option value="">Aucun</option>
                  {notifyServices.map((service) => (
                    <option key={service} value={service}>
                      notify.{service}
                    </option>
                  ))}
                </select>
              </Field>
              <button type="submit" className="btn">
                Enregistrer
              </button>
            </form>
            {!home?.default_notify_service && (
              <p className="muted">
                Sans destinataire par defaut, les entretiens qui ne sont assignes a personne ne
                rappellent rien. Les autres sont envoyes a la personne assignee (fiche dans{' '}
                <Link to="/membres">Membres</Link>).
              </p>
            )}
            <button
              type="button"
              className="btn btn--small"
              disabled={remindersRunning}
              onClick={() => void sendRemindersNow()}
            >
              {remindersRunning ? 'Envoi...' : 'Envoyer un rappel maintenant'}
            </button>
            {reminderResult && (
              <p className="muted">
                {reminderResult.sent === 0 && reminderResult.without_recipient === 0
                  ? 'Rien a rappeler pour le moment.'
                  : `${reminderResult.sent} message(s) envoye(s) pour ${reminderResult.tasks} entretien(s).`}
                {reminderResult.without_recipient > 0 &&
                  ` ${reminderResult.without_recipient} entretien(s) sans destinataire.`}
              </p>
            )}
            {reminderResult && reminderResult.errors.length > 0 && (
              <p className="status status--error">{reminderResult.errors.join(' ')}</p>
            )}
            {reminderError && <p className="status status--error">{reminderError}</p>}
          </>
        )}
      </div>

      <div className="card">
        <h2 className="card__title">Types de lieux</h2>
        <p className="muted">
          Utilises pour classer les lieux (Piece, Etage...). Les types integres peuvent etre
          renommes mais pas supprimes.
        </p>
        <ul className="tree">
          {types.map((type) => (
            <LocationTypeRow
              key={type.id}
              type={type}
              onError={setError}
              onChanged={() => void reload()}
              onDelete={() => void removeType(type.id)}
            />
          ))}
        </ul>
        <form className="form form--inline" onSubmit={(event) => void addType(event)}>
          <Field label="Nouveau type">
            <input
              required
              value={newTypeName}
              onChange={(event) => setNewTypeName(event.target.value)}
              placeholder="Combles, Cave..."
            />
          </Field>
          <button type="submit" className="btn btn--primary">
            Ajouter
          </button>
        </form>
      </div>
    </section>
  )
}

function LocationTypeRow({
  type,
  onError,
  onChanged,
  onDelete,
}: {
  type: LocationType
  onError: (message: string | null) => void
  onChanged: () => void
  onDelete: () => void
}) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(type.name)
  const { showToast } = useToast()

  async function rename(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchLocationType(type.id, { name: name.trim() })
      setRenaming(false)
      showToast('Type renommé')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  return (
    <li>
      <div className="tree__row">
        <strong>{type.name}</strong>
        {type.is_builtin && <span className="muted">integre</span>}
        <button
          type="button"
          className="btn btn--small btn--edit"
          onClick={() => setRenaming((v) => !v)}
        >
          <EditIcon /> Renommer
        </button>
        <button
          type="button"
          className="btn btn--small btn--delete"
          disabled={type.is_builtin}
          title={type.is_builtin ? 'Un type integre ne peut pas etre supprime, seulement renomme' : undefined}
          onClick={onDelete}
        >
          <TrashIcon /> Supprimer
        </button>
      </div>
      {renaming && (
        <form className="form form--inline" onSubmit={(event) => void rename(event)}>
          <input value={name} onChange={(event) => setName(event.target.value)} />
          <button type="submit" className="btn btn--primary btn--small">
            OK
          </button>
        </form>
      )}
    </li>
  )
}
