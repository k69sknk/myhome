import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { Home, Location, LocationType } from '../api/types'
import Field from '../components/Field'
import { errorMessage } from '../lib/format'

const LOCATION_TYPES: { value: LocationType; label: string }[] = [
  { value: 'room', label: 'Piece' },
  { value: 'floor', label: 'Etage' },
  { value: 'zone', label: 'Zone' },
  { value: 'building', label: 'Batiment' },
  { value: 'outdoor', label: 'Exterieur' },
  { value: 'technical', label: 'Technique' },
]

interface TreeNode {
  location: Location
  children: TreeNode[]
}

function buildTree(locations: Location[]): TreeNode[] {
  const children = new Map<number | null, Location[]>()
  for (const location of locations) {
    const siblings = children.get(location.parent_id) ?? []
    siblings.push(location)
    children.set(location.parent_id, siblings)
  }
  const nest = (parentId: number | null): TreeNode[] =>
    (children.get(parentId) ?? []).map((location) => ({
      location,
      children: nest(location.id),
    }))
  return nest(null)
}

export default function Locations() {
  const [home, setHome] = useState<Home | null>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [error, setError] = useState<string | null>(null)
  const [homeName, setHomeName] = useState('')
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState<LocationType>('room')
  const [newParent, setNewParent] = useState('')

  async function reload() {
    const [nextHome, nextLocations] = await Promise.all([api.home(), api.locations()])
    setHome(nextHome)
    setHomeName(nextHome.name)
    setLocations(nextLocations)
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

  const tree = useMemo(() => buildTree(locations), [locations])

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

  async function addLocation(event: FormEvent) {
    event.preventDefault()
    const name = newName.trim()
    if (!name) return
    setError(null)
    try {
      await api.createLocation({
        name,
        location_type: newType,
        parent_id: newParent === '' ? null : Number(newParent),
      })
      setNewName('')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Lieux</h1>
      <p className="page__lead">
        Arbre libre : etages, pieces, garage, exterieur... Rangez vos appareils la ou ils sont.
      </p>

      {error && <p className="status status--error">{error}</p>}

      {home && (
        <form className="card form form--inline" onSubmit={(event) => void saveHome(event)}>
          <Field label="Nom de la maison">
            <input value={homeName} onChange={(event) => setHomeName(event.target.value)} />
          </Field>
          <button type="submit" className="btn">
            Enregistrer
          </button>
        </form>
      )}

      <div className="card">
        <h2 className="card__title">Ajouter un lieu</h2>
        <form className="form" onSubmit={(event) => void addLocation(event)}>
          <Field label="Nom">
            <input
              required
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="RDC, Cuisine, Garage..."
            />
          </Field>
          <Field label="Type">
            <select
              value={newType}
              onChange={(event) => setNewType(event.target.value as LocationType)}
            >
              {LOCATION_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Dans">
            <select value={newParent} onChange={(event) => setNewParent(event.target.value)}>
              <option value="">A la racine</option>
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.path}
                </option>
              ))}
            </select>
          </Field>
          <button type="submit" className="btn btn--primary">
            Ajouter
          </button>
        </form>
      </div>

      <div className="card">
        <h2 className="card__title">Arborescence</h2>
        {tree.length === 0 ? (
          <p className="muted">Aucun lieu pour l'instant.</p>
        ) : (
          <ul className="tree">
            {tree.map((node) => (
              <LocationNode
                key={node.location.id}
                node={node}
                onError={setError}
                onChanged={() => void reload()}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function LocationNode({
  node,
  onError,
  onChanged,
}: {
  node: TreeNode
  onError: (message: string | null) => void
  onChanged: () => void
}) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(node.location.name)
  const [adding, setAdding] = useState(false)
  const [childName, setChildName] = useState('')

  async function rename(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchLocation(node.location.id, { name: name.trim() })
      setRenaming(false)
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  async function addChild(event: FormEvent) {
    event.preventDefault()
    const trimmed = childName.trim()
    if (!trimmed) return
    onError(null)
    try {
      await api.createLocation({
        name: trimmed,
        parent_id: node.location.id,
        location_type: 'room',
      })
      setChildName('')
      setAdding(false)
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  async function remove() {
    onError(null)
    try {
      await api.deleteLocation(node.location.id)
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  return (
    <li>
      <div className="tree__row">
        <strong>{node.location.name}</strong>
        <span className="muted">
          {node.location.asset_count} appareil{node.location.asset_count === 1 ? '' : 's'}
        </span>
        <button type="button" className="btn btn--small" onClick={() => setRenaming((value) => !value)}>
          Renommer
        </button>
        <button type="button" className="btn btn--small" onClick={() => setAdding((value) => !value)}>
          Ajouter un lieu
        </button>
        <button type="button" className="btn btn--small" onClick={() => void remove()}>
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
      {adding && (
        <form className="form form--inline" onSubmit={(event) => void addChild(event)}>
          <input
            value={childName}
            onChange={(event) => setChildName(event.target.value)}
            placeholder={`Dans ${node.location.name}`}
          />
          <button type="submit" className="btn btn--primary btn--small">
            Ajouter
          </button>
        </form>
      )}
      {node.children.length > 0 && (
        <ul className="tree">
          {node.children.map((child) => (
            <LocationNode
              key={child.location.id}
              node={child}
              onError={onError}
              onChanged={onChanged}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
