import { useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type { Category } from '../api/types'
import { errorMessage } from '../lib/format'
import { useToast } from './Toast'

interface Option {
  id: number
  label: string
}

function buildOptions(categories: Category[]): Option[] {
  const byId = new Map(categories.map((row) => [row.id, row]))
  return categories.map((row) => {
    const parent = row.parent_id !== null ? byId.get(row.parent_id) : undefined
    return { id: row.id, label: parent ? `${parent.name} > ${row.name}` : row.name }
  })
}

export default function CategorySelect({
  categories,
  value,
  onChange,
  onCreated,
}: {
  categories: Category[]
  value: string
  onChange: (value: string) => void
  onCreated?: (category: Category) => void
}) {
  const options = useMemo(() => buildOptions(categories), [categories])
  const selectedLabel = options.find((option) => String(option.id) === value)?.label ?? ''

  const [query, setQuery] = useState(selectedLabel)
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
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
    (option) => option.label.toLowerCase() === trimmed.toLowerCase(),
  )
  const canCreate = trimmed !== '' && !hasExactMatch

  function select(option: Option | null) {
    onChange(option ? String(option.id) : '')
    setQuery(option?.label ?? '')
    setOpen(false)
  }

  async function createAndSelect() {
    if (!trimmed || creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createCategory({ name: trimmed })
      onCreated?.(created)
      onChange(String(created.id))
      setQuery(created.name)
      setOpen(false)
      showToast('Catégorie ajoutée')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="combobox" ref={containerRef}>
      <input
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
          if (event.target.value.trim() === '') onChange('')
        }}
        onFocus={() => setOpen(true)}
        placeholder="Sans categorie, ou tapez pour chercher..."
      />
      {open && (
        <ul className="combobox__list">
          <li>
            <button type="button" className="combobox__option" onClick={() => select(null)}>
              Sans categorie
            </button>
          </li>
          {matches.map((option) => (
            <li key={option.id}>
              <button type="button" className="combobox__option" onClick={() => select(option)}>
                {option.label}
              </button>
            </li>
          ))}
          {canCreate && (
            <li>
              <button
                type="button"
                className="combobox__option combobox__option--create"
                disabled={creating}
                onClick={() => void createAndSelect()}
              >
                + Creer la categorie « {trimmed} »
              </button>
            </li>
          )}
        </ul>
      )}
      {error && <p className="status status--error">{error}</p>}
    </div>
  )
}
