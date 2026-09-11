import { Fragment, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'
import type { Member, MemberType, Provider, Trade } from '../api/types'
import { errorMessage } from '../lib/format'
import { matches, normalize } from '../lib/search'
import { useToast } from './Toast'

/** Un choix possible : quelqu'un du foyer, ou un prestataire. Les deux profils
 *  sont distincts (ADR-0011) mais se choisissent au meme endroit — l'utilisateur
 *  tape un nom, il n'a pas a designer d'abord une categorie. */
export interface Assignee {
  kind: 'member' | 'provider'
  id: number
  name: string
  /** Ce qui distingue deux homonymes : « Foyer », « Chauffagiste · 04 72... ». */
  meta: string
}

/** La valeur echangee avec le formulaire : « member:3 », « provider:7 », ou ''. */
export function assigneeValue(kind: Assignee['kind'], id: number): string {
  return `${kind}:${id}`
}

export function parseAssignee(value: string): { kind: Assignee['kind']; id: number } | null {
  const [kind, id] = value.split(':')
  if ((kind !== 'member' && kind !== 'provider') || !id) return null
  return { kind, id: Number(id) }
}

const MEMBER_GROUP: Record<MemberType, string> = {
  household: 'Foyer',
  friend: 'Amis',
}

const GROUPS = ['Foyer', 'Amis', 'Prestataires'] as const

function optionsFrom(members: Member[], providers: Provider[], trades: Trade[]): Assignee[] {
  const labels = new Map(trades.map((trade) => [trade.slug, trade.label]))
  return [
    ...members.map((member) => ({
      kind: 'member' as const,
      id: member.id,
      name: member.name,
      meta: [MEMBER_GROUP[member.member_type], member.contact]
        .filter((part): part is string => Boolean(part))
        .join(' · '),
    })),
    ...providers.map((provider) => ({
      kind: 'provider' as const,
      id: provider.id,
      // Le metier avant le telephone : c'est ce qui identifie un prestataire
      // quand deux entreprises portent des noms voisins.
      name: provider.name,
      meta: [
        provider.specialty ? (labels.get(provider.specialty) ?? provider.specialty) : null,
        provider.phone,
      ]
        .filter((part): part is string => Boolean(part))
        .join(' · '),
    })),
  ]
}

function groupOf(option: Assignee, members: Member[]): (typeof GROUPS)[number] {
  if (option.kind === 'provider') return 'Prestataires'
  const member = members.find((row) => row.id === option.id)
  return member?.member_type === 'friend' ? 'Amis' : 'Foyer'
}

function label(option: Assignee): string {
  return option.meta ? `${option.name} — ${option.meta}` : option.name
}

/** Choix de celui qui s'occupe d'un entretien, ou de celui qui l'a fait.
 *
 *  Les deux annuaires sont interroges ensemble et presentes en groupes ; un nom
 *  inconnu se cree sur place, en prestataire ou en personne, deux boutons
 *  distincts pour que le profil soit un choix et non une devinette.
 *
 *  `onFreeText` ouvre un second usage : l'historique, ou l'on veut bien noter
 *  « le voisin » sans lui ouvrir de fiche. Fourni, ce qui est tape et non choisi
 *  reste du texte ; absent, seule une fiche existante est acceptable.
 */
export default function AssigneeSelect({
  members,
  providers,
  trades = [],
  value,
  onChange,
  onMemberCreated,
  onProviderCreated,
  freeText,
  onFreeText,
  placeholder = 'Personne, ou tapez un nom...',
}: {
  members: Member[]
  providers: Provider[]
  trades?: Trade[]
  value: string
  /** Le choix accompagne son identifiant : l'appelant qui vient de le faire creer
   *  ne l'a pas encore dans ses listes, et attendre le prochain rendu pour savoir
   *  de qui il s'agit se paie en comportements d'un coup en retard. */
  onChange: (value: string, picked: Assignee | null) => void
  onMemberCreated?: (member: Member) => void
  onProviderCreated?: (provider: Provider) => void
  freeText?: string
  onFreeText?: (text: string) => void
  placeholder?: string
}) {
  const options = useMemo(
    () => optionsFrom(members, providers, trades),
    [members, providers, trades],
  )
  const selected = options.find((option) => assigneeValue(option.kind, option.id) === value)
  const selectedLabel = selected ? label(selected) : (freeText ?? '')

  const [query, setQuery] = useState(selectedLabel)
  /** Le champ affiche le choix courant ; tant qu'on n'a pas tape, ce texte n'est
   *  pas un filtre — sinon ouvrir la liste ne montrerait que la ligne deja
   *  choisie, et l'annuaire resterait invisible. */
  const [typed, setTyped] = useState(false)
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
        // Sans texte libre, une saisie qui ne designe personne ne veut rien dire
        // et on revient au choix courant. Avec, elle est la reponse : on la garde.
        if (onFreeText === undefined) setQuery(selectedLabel)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [selectedLabel, onFreeText])

  const trimmed = query.trim()
  const needle = typed ? trimmed : ''
  const found = useMemo(() => {
    // Nom ET metier : « chauffagiste » doit ramener Dupont Chauffage meme si on
    // ne se souvient plus de son nom, ce qui est le cas le plus frequent.
    const visible = options.filter((option) => matches([option.name, option.meta], needle))
    return [...visible].sort((a, b) => a.name.localeCompare(b.name))
  }, [options, needle])
  const normalized = normalize(needle)
  const hasExactMatch = options.some(
    (option) => normalize(option.name) === normalized || normalize(label(option)) === normalized,
  )
  const canCreate = typed && trimmed !== '' && !hasExactMatch

  function select(option: Assignee) {
    onChange(assigneeValue(option.kind, option.id), option)
    onFreeText?.('')
    setQuery(label(option))
    setTyped(false)
    setOpen(false)
  }

  function clear() {
    onChange('', null)
    onFreeText?.('')
    setQuery('')
    setTyped(false)
    setOpen(true)
    inputRef.current?.focus()
  }

  async function createProvider() {
    if (!trimmed || creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createProvider({
        name: trimmed,
        specialty: null,
        phone: null,
        email: null,
        website: null,
        address: null,
        customer_ref: null,
        notes: null,
      })
      onProviderCreated?.(created)
      select({ kind: 'provider', id: created.id, name: created.name, meta: '' })
      showToast('Prestataire ajouté')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setCreating(false)
    }
  }

  async function createMember() {
    if (!trimmed || creating) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createMember({ name: trimmed, member_type: 'household' })
      onMemberCreated?.(created)
      select({ kind: 'member', id: created.id, name: created.name, meta: 'Foyer' })
      showToast('Membre ajouté')
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
          setTyped(true)
          setOpen(true)
          if (onFreeText !== undefined) {
            // Taper defait le choix precedent : le texte ne designe plus personne.
            onChange('', null)
            onFreeText(event.target.value.trim())
          } else if (event.target.value.trim() === '') {
            onChange('', null)
          }
        }}
        onFocus={() => {
          setTyped(false)
          setOpen(true)
        }}
        placeholder={placeholder}
      />
      {query !== '' && (
        <button type="button" className="combobox__clear" aria-label="Effacer" onClick={clear}>
          ×
        </button>
      )}
      {open && (
        <ul className="combobox__list">
          {GROUPS.map((group) => {
            const rows = found.filter((option) => groupOf(option, members) === group)
            if (rows.length === 0) return null
            return (
              <Fragment key={group}>
                <li className="combobox__group">{group}</li>
                {rows.map((option) => (
                  <li key={`${option.kind}-${option.id}`}>
                    <button
                      type="button"
                      className="combobox__option"
                      onClick={() => select(option)}
                    >
                      {option.name}
                      {option.meta && <span className="combobox__option-meta"> · {option.meta}</span>}
                    </button>
                  </li>
                ))}
              </Fragment>
            )
          })}
          {found.length === 0 && !canCreate && <li className="combobox__empty">Aucune fiche</li>}
          {canCreate && (
            <>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  disabled={creating}
                  onClick={() => void createProvider()}
                >
                  + Créer le prestataire « {trimmed} »
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  disabled={creating}
                  onClick={() => void createMember()}
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
