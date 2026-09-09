import { useEffect, useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { Home, LocationType } from '../api/types'
import Field from '../components/Field'
import { errorMessage } from '../lib/format'

export default function Settings() {
  const [home, setHome] = useState<Home | null>(null)
  const [homeName, setHomeName] = useState('')
  const [types, setTypes] = useState<LocationType[]>([])
  const [newTypeName, setNewTypeName] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    const [nextHome, nextTypes] = await Promise.all([api.home(), api.locationTypes()])
    setHome(nextHome)
    setHomeName(nextHome.name)
    setTypes(nextTypes)
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
      const updated = await api.patchHome({ name: homeName.trim() })
      setHome(updated)
    } catch (caught: unknown) {
      setError(errorMessage(caught))
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
            <button type="submit" className="btn">
              Enregistrer
            </button>
          </form>
        </div>
      )}

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
        <button type="button" className="btn btn--small" onClick={() => setRenaming((v) => !v)}>
          Renommer
        </button>
        <button
          type="button"
          className="btn btn--small"
          disabled={type.is_builtin}
          title={type.is_builtin ? 'Un type integre ne peut pas etre supprime, seulement renomme' : undefined}
          onClick={onDelete}
        >
          Supprimer
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
