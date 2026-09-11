import { Fragment, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type { Member, MemberType } from '../api/types'
import { errorMessage } from '../lib/format'
import { useToast } from './Toast'

/** Ordre d'affichage des groupes : le foyer d'abord, les prestataires ensuite. */
const GROUPS: { type: MemberType; label: string }[] = [
  { type: 'household', label: 'Foyer' },
  { type: 'friend', label: 'Amis' },
  { type: 'company', label: 'Entreprises' },
]

const TYPE_LABEL: Record<MemberType, string> = {
  household: 'Foyer',
  friend: 'Ami',
  company: 'Entreprise',
}

function memberLabel(member: Member): string {
  const context = [TYPE_LABEL[member.member_type], member.contact]
    .filter((part): part is string => Boolean(part))
    .join(' · ')
  return `${member.name} — ${context}`
}

/** Choix de l'assigne : une personne du foyer, un ami, ou une entreprise —
 *  qu'on peut creer sans quitter la fiche (l'installateur de la pompe a chaleur
 *  n'a pas a passer par l'annuaire avant d'exister). */
export default function AssigneeSelect({
  members,
  value,
  onChange,
  onCreated,
}: {
  members: Member[]
  value: string
  onChange: (value: string) => void
  onCreated?: (member: Member) => void
}) {
  const selected = members.find((member) => String(member.id) === value)
  const selectedLabel = selected ? memberLabel(selected) : ''

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
  const matches = useMemo(() => {
    const needle = trimmed.toLowerCase()
    const visible = needle
      ? members.filter((member) => memberLabel(member).toLowerCase().includes(needle))
      : members
    return [...visible].sort((a, b) => a.name.localeCompare(b.name))
  }, [members, trimmed])
  const hasExactMatch = members.some((member) => {
    const needle = trimmed.toLowerCase()
    return member.name.toLowerCase() === needle || memberLabel(member).toLowerCase() === needle
  })
  const canCreate = trimmed !== '' && !hasExactMatch

  function select(member: Member) {
    onChange(String(member.id))
    setQuery(memberLabel(member))
    setOpen(false)
  }

  function clear() {
    onChange('')
    setQuery('')
    setOpen(true)
    inputRef.current?.focus()
  }

  async function createAndSelect(memberType: MemberType) {
    if (!trimmed || creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createMember({ name: trimmed, member_type: memberType })
      onCreated?.(created)
      onChange(String(created.id))
      setQuery(memberLabel(created))
      setOpen(false)
      showToast(memberType === 'company' ? 'Entreprise ajoutée' : 'Membre ajouté')
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
        placeholder="Personne, ou tapez un nom..."
      />
      {query !== '' && (
        <button type="button" className="combobox__clear" aria-label="Effacer" onClick={clear}>
          ×
        </button>
      )}
      {open && (
        <ul className="combobox__list">
          {GROUPS.map(({ type, label }) => {
            const group = matches.filter((member) => member.member_type === type)
            if (group.length === 0) return null
            return (
              <Fragment key={type}>
                <li className="combobox__group">{label}</li>
                {group.map((member) => (
                  <li key={member.id}>
                    <button type="button" className="combobox__option" onClick={() => select(member)}>
                      {member.name}
                      {member.contact && <span className="combobox__option-meta"> · {member.contact}</span>}
                    </button>
                  </li>
                ))}
              </Fragment>
            )
          })}
          {matches.length === 0 && !canCreate && <li className="combobox__empty">Aucun membre</li>}
          {canCreate && (
            <>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  disabled={creating}
                  onClick={() => void createAndSelect('company')}
                >
                  + Créer l'entreprise « {trimmed} »
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  disabled={creating}
                  onClick={() => void createAndSelect('household')}
                >
                  + Créer la personne « {trimmed} »
                </button>
              </li>
            </>
          )}
        </ul>
      )}
      {error && <p className="status status--error">{error}</p>}
    </div>
  )
}
