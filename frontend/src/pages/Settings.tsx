import { useEffect, useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { CalendarSyncResult, HaCalendarOption, Home, LocationType } from '../api/types'
import Field from '../components/Field'
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

  async function reload() {
    const [nextHome, nextTypes] = await Promise.all([api.home(), api.locationTypes()])
    setHome(nextHome)
    setHomeName(nextHome.name)
    setThreshold(String(nextHome.due_soon_threshold_days))
    setTypes(nextTypes)
    setCalendarEntityId(nextHome.ha_calendar_entity_id ?? '')
    setCalendarSyncEnabled(nextHome.ha_calendar_sync_enabled)

    try {
      setCalendars(await api.haCalendars())
      setCalendarsError(null)
    } catch (caught: unknown) {
      setCalendarsError(errorMessage(caught))
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

  async function addType(event: FormEvent) {
    event.preventDefault()
    const name = newTypeName.trim()
    if (!name) return
    setError(null)
    try {
      await api.createLocationType({ name })
      setNewTypeName('')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function removeType(id: number) {
    setError(null)
    try {
      await api.deleteLocationType(id)
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Parametres</h1>
      <p className="page__lead">Reglages de la maison et types de lieux personnalisables.</p>

      {error && <p className="status status--error">{error}</p>}

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

  async function rename(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchLocationType(type.id, { name: name.trim() })
      setRenaming(false)
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
