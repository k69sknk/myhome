import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type { AssetListItem, Category } from '../api/types'
import { errorMessage } from '../lib/format'
import { useToast } from './Toast'

interface Option {
  id: number
  name: string
  categoryPath: string | null
  locationSegments: string[]
  /** Nom + parents, pour l'input une fois l'equipement selectionne. */
  label: string
}

interface LocationGroup {
  segment: string
  children: LocationGroup[]
  items: Option[]
}

interface MutableGroup {
  segment: string
  children: Map<string, MutableGroup>
  items: Option[]
}

/** Chemin complet parent > enfant d'une categorie, comme location_path cote backend. */
function categoryPath(byId: Map<number, Category>, bySlug: Map<string, Category>, slug: string | null): string | null {
  let current = slug ? bySlug.get(slug) : undefined
  if (!current) return null
  const parts: string[] = []
  const seen = new Set<number>()
  while (current && !seen.has(current.id)) {
    seen.add(current.id)
    parts.unshift(current.name)
    current = current.parent_id !== null ? byId.get(current.parent_id) : undefined
  }
  return parts.join(' > ')
}

function buildOptions(assets: AssetListItem[], categories: Category[]): Option[] {
  const byId = new Map(categories.map((row) => [row.id, row]))
  const bySlug = new Map(categories.map((row) => [row.slug, row]))
  return assets.map((asset) => {
    const catPath = categoryPath(byId, bySlug, asset.category_slug)
    const context = [catPath, asset.location_path].filter((part): part is string => Boolean(part)).join(' · ')
    return {
      id: asset.id,
      name: asset.name,
      categoryPath: catPath,
      locationSegments: asset.location_path ? asset.location_path.split(' > ') : [],
      label: context ? `${asset.name} — ${context}` : asset.name,
    }
  })
}

function sortGroups(nodes: Map<string, MutableGroup>): LocationGroup[] {
  return [...nodes.values()]
    .sort((a, b) => a.segment.localeCompare(b.segment))
    .map((node) => ({
      segment: node.segment,
      children: sortGroups(node.children),
      items: [...node.items].sort((a, b) => a.name.localeCompare(b.name)),
    }))
}

/** Arbre des equipements groupes par lieu (chaque niveau = un lieu parent) ; les
 * equipements sans lieu vont dans un groupe "Sans lieu" a part. */
function buildLocationTree(options: Option[]): { noLocation: Option[]; roots: LocationGroup[] } {
  const noLocation: Option[] = []
  const rootMap = new Map<string, MutableGroup>()
  for (const option of options) {
    if (option.locationSegments.length === 0) {
      noLocation.push(option)
      continue
    }
    let map = rootMap
    let node: MutableGroup | undefined
    for (const segment of option.locationSegments) {
      node = map.get(segment)
      if (!node) {
        node = { segment, children: new Map(), items: [] }
        map.set(segment, node)
      }
      map = node.children
    }
    node?.items.push(option)
  }
  return {
    noLocation: [...noLocation].sort((a, b) => a.name.localeCompare(b.name)),
    roots: sortGroups(rootMap),
  }
}

function GroupRow({
  node,
  depth,
  onSelect,
}: {
  node: LocationGroup
  depth: number
  onSelect: (option: Option) => void
}) {
  return (
    <>
      <li className="combobox__group" style={{ paddingLeft: `${0.55 + depth * 0.9}rem` }}>
        {node.segment}
      </li>
      {node.children.map((child) => (
        <GroupRow key={child.segment} node={child} depth={depth + 1} onSelect={onSelect} />
      ))}
      {node.items.map((option) => (
        <li key={option.id}>
          <button
            type="button"
            className="combobox__option"
            style={{ paddingLeft: `${0.55 + (depth + 1) * 0.9}rem` }}
            onClick={() => onSelect(option)}
          >
            {option.name}
            {option.categoryPath && <span className="combobox__option-meta"> · {option.categoryPath}</span>}
          </button>
        </li>
      ))}
    </>
  )
}

export default function AssetSelect({
  assets,
  categories,
  value,
  onChange,
  onCreated,
}: {
  assets: AssetListItem[]
  categories: Category[]
  value: string
  onChange: (value: string) => void
  onCreated?: (asset: AssetListItem) => void
}) {
  const options = useMemo(() => buildOptions(assets, categories), [assets, categories])
  const selectedLabel = options.find((option) => String(option.id) === value)?.label ?? ''

  const [query, setQuery] = useState(selectedLabel)
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()

  useEffect(() => {
    setQuery(selectedLabel)
  }, [selectedLabel])

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
        setQuery(selectedLabel)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [selectedLabel])

  const trimmed = query.trim()
  const matches = trimmed
    ? options.filter((option) => option.label.toLowerCase().includes(trimmed.toLowerCase()))
    : options
  const hasExactMatch = options.some(
    (option) =>
      option.name.toLowerCase() === trimmed.toLowerCase() ||
      option.label.toLowerCase() === trimmed.toLowerCase(),
  )
  const canCreate = trimmed !== '' && !hasExactMatch
  const tree = useMemo(() => buildLocationTree(matches), [matches])

  function select(option: Option) {
    onChange(String(option.id))
    setQuery(option.label)
    setOpen(false)
  }

  function clear() {
    onChange('')
    setQuery('')
    setOpen(true)
    inputRef.current?.focus()
  }

  async function createAndSelect() {
    if (!trimmed || creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createAsset({ name: trimmed })
      const listItem: AssetListItem = {
        id: created.id,
        name: created.name,
        kind: created.kind,
        category_name: created.category_name,
        category_slug: created.category_slug,
        location_path: created.location_path,
        install_date: created.install_date,
        status: created.status,
        task_status: 'unscheduled',
        photo_document_id: created.photo_document_id,
        warranty_end_date: created.warranty?.end_date ?? null,
      }
      onCreated?.(listItem)
      onChange(String(created.id))
      setQuery(created.name)
      setOpen(false)
      showToast('Équipement ajouté')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="combobox combobox--clearable" ref={containerRef}>
      <input
        ref={inputRef}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
          if (event.target.value.trim() === '') onChange('')
        }}
        onFocus={() => setOpen(true)}
        placeholder="Tapez pour chercher un équipement..."
      />
      {query !== '' && (
        <button type="button" className="combobox__clear" aria-label="Effacer" onClick={clear}>
          ×
        </button>
      )}
      {open && (
        <ul className="combobox__list">
          {tree.noLocation.length > 0 && (
            <GroupRow
              node={{ segment: 'Sans lieu', children: [], items: tree.noLocation }}
              depth={0}
              onSelect={select}
            />
          )}
          {tree.roots.map((node) => (
            <GroupRow key={node.segment} node={node} depth={0} onSelect={select} />
          ))}
          {matches.length === 0 && !canCreate && <li className="combobox__empty">Aucun équipement</li>}
          {canCreate && (
            <li>
              <button
                type="button"
                className="combobox__option combobox__option--create"
                disabled={creating}
                onClick={() => void createAndSelect()}
              >
                + Créer l'équipement « {trimmed} »
              </button>
            </li>
          )}
        </ul>
      )}
      {error && <p className="status status--error">{error}</p>}
    </div>
  )
}
