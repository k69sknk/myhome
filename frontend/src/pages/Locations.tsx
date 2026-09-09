import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { Location, LocationType } from '../api/types'
import Field from '../components/Field'
import { EditIcon, TrashIcon } from '../components/icons'
import { errorMessage } from '../lib/format'

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

interface FlatLocation {
  location: Location
  depth: number
}

function flattenTree(nodes: TreeNode[], depth = 0): FlatLocation[] {
  return nodes.flatMap((node) => [
    { location: node.location, depth },
    ...flattenTree(node.children, depth + 1),
  ])
}

/** Comme flattenTree, mais saute un noeud (et donc tout son sous-arbre) : sert a
 * proposer un nouveau parent pour un lieu existant sans jamais pouvoir creer de cycle. */
function flattenExcludingSubtree(nodes: TreeNode[], excludeId: number, depth = 0): FlatLocation[] {
  return nodes.flatMap((node) => {
    if (node.location.id === excludeId) return []
    return [
      { location: node.location, depth },
      ...flattenExcludingSubtree(node.children, excludeId, depth + 1),
    ]
  })
}

function optionLabel(location: Location, depth: number): string {
  return `${'  '.repeat(depth)}${depth > 0 ? '└ ' : ''}${location.name}`
}

export default function Locations() {
  const [locations, setLocations] = useState<Location[]>([])
  const [types, setTypes] = useState<LocationType[]>([])
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [newTypeId, setNewTypeId] = useState('')
  const [newParent, setNewParent] = useState('')

  async function reload() {
    const [nextLocations, nextTypes] = await Promise.all([api.locations(), api.locationTypes()])
    setLocations(nextLocations)
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

  const tree = useMemo(() => buildTree(locations), [locations])
  const flatLocations = useMemo(() => flattenTree(tree), [tree])
  const defaultTypeId = types.find((type) => type.slug === 'room')?.id ?? types[0]?.id ?? null

  useEffect(() => {
    if (newTypeId === '' && defaultTypeId !== null) {
      setNewTypeId(String(defaultTypeId))
    }
  }, [defaultTypeId, newTypeId])

  async function addLocation(event: FormEvent) {
    event.preventDefault()
    const name = newName.trim()
    if (!name) return
    setError(null)
    try {
      await api.createLocation({
        name,
        location_type_id: newTypeId === '' ? null : Number(newTypeId),
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
            <select value={newTypeId} onChange={(event) => setNewTypeId(event.target.value)}>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Lieu parent"
            hint="Le nouveau lieu sera imbrique a l'interieur du lieu choisi. Laissez sur « A la racine » pour un lieu de premier niveau."
          >
            <select value={newParent} onChange={(event) => setNewParent(event.target.value)}>
              <option value="">A la racine</option>
              {flatLocations.map(({ location, depth }) => (
                <option key={location.id} value={location.id}>
                  {optionLabel(location, depth)}
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
                fullTree={tree}
                defaultTypeId={defaultTypeId}
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
  fullTree,
  defaultTypeId,
  onError,
  onChanged,
}: {
  node: TreeNode
  fullTree: TreeNode[]
  defaultTypeId: number | null
  onError: (message: string | null) => void
  onChanged: () => void
}) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(node.location.name)
  const [adding, setAdding] = useState(false)
  const [childName, setChildName] = useState('')
  const [moving, setMoving] = useState(false)
  const [newParent, setNewParent] = useState('')

  const moveOptions = useMemo(
    () => flattenExcludingSubtree(fullTree, node.location.id),
    [fullTree, node.location.id],
  )

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
        location_type_id: defaultTypeId,
      })
      setChildName('')
      setAdding(false)
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  async function move(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchLocation(node.location.id, {
        parent_id: newParent === '' ? null : Number(newParent),
      })
      setMoving(false)
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
        <span className="muted">{node.location.location_type_name}</span>
        <span className="muted">
          {node.location.asset_count} appareil{node.location.asset_count === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          className="btn btn--small btn--edit"
          onClick={() => setRenaming((value) => !value)}
        >
          <EditIcon /> Renommer
        </button>
        <button type="button" className="btn btn--small" onClick={() => setAdding((value) => !value)}>
          Ajouter un lieu
        </button>
        <button
          type="button"
          className="btn btn--small"
          onClick={() => {
            setNewParent(node.location.parent_id?.toString() ?? '')
            setMoving((value) => !value)
          }}
        >
          Deplacer
        </button>
        <button type="button" className="btn btn--small btn--delete" onClick={() => void remove()}>
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
      {moving && (
        <form className="form form--inline" onSubmit={(event) => void move(event)}>
          <select value={newParent} onChange={(event) => setNewParent(event.target.value)}>
            <option value="">A la racine</option>
            {moveOptions.map(({ location, depth }) => (
              <option key={location.id} value={location.id}>
                {optionLabel(location, depth)}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn--primary btn--small">
            Deplacer ici
          </button>
        </form>
      )}
      {node.children.length > 0 && (
        <ul className="tree">
          {node.children.map((child) => (
            <LocationNode
              key={child.location.id}
              node={child}
              fullTree={fullTree}
              defaultTypeId={defaultTypeId}
              onError={onError}
              onChanged={onChanged}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
