import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Catalog, CatalogProposal, CatalogRecurrence, MaintenanceSelection } from '../api/types'
import { useToast } from '../components/Toast'
import { errorMessage, formatCatalogRecurrence } from '../lib/format'

type Phase = 'zones' | 'objets' | 'entretiens' | 'fin'

export default function Onboarding() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [phase, setPhase] = useState<Phase>('zones')
  const [roomKeys, setRoomKeys] = useState<string[]>([])
  const [roomIndex, setRoomIndex] = useState(0)
  const [checked, setChecked] = useState<string[]>([])
  const [proposals, setProposals] = useState<CatalogProposal[]>([])
  const [rejected, setRejected] = useState<string[]>([])
  const [intervals, setIntervals] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .catalog()
      .then((next) => {
        if (!cancelled) setCatalog(next)
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const itemsByKey = useMemo(
    () => new Map((catalog?.items ?? []).map((item) => [item.key, item])),
    [catalog],
  )

  if (error && catalog === null) {
    return (
      <section className="page">
        <p className="status status--error">{error}</p>
      </section>
    )
  }
  if (catalog === null) {
    return (
      <section className="page">
        <p className="muted">Chargement...</p>
      </section>
    )
  }

  const rooms = catalog.rooms.filter((room) => !room.deprecated)
  const selectedRooms = roomKeys
    .map((key) => rooms.find((room) => room.key === key))
    .filter((room) => room !== undefined)
  const currentRoom = selectedRooms[roomIndex]

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
  }

  function startTour() {
    if (roomKeys.length === 0) return
    setRoomIndex(0)
    setChecked([])
    setPhase('objets')
  }

  async function goToProposals() {
    setBusy(true)
    setError(null)
    try {
      setProposals(await api.catalogProposals())
      setPhase('entretiens')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  /** Enregistre la zone courante avant d'avancer : l'app est utilisable a mi-parcours. */
  async function nextRoom(save: boolean) {
    if (currentRoom === undefined) return
    setBusy(true)
    setError(null)
    try {
      if (save && checked.length > 0) {
        await api.applyCatalogRoom(currentRoom.key, checked)
      }
      setChecked([])
      if (roomIndex + 1 < selectedRooms.length) {
        setRoomIndex(roomIndex + 1)
      } else {
        await goToProposals()
      }
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function createMaintenances() {
    setBusy(true)
    setError(null)
    try {
      const selections: MaintenanceSelection[] = proposals
        .filter((proposal) => !rejected.includes(proposalId(proposal)))
        .map((proposal) => ({
          key: proposal.maintenance.key,
          asset_id: proposal.asset_id,
          recurrence: adjusted(proposal, intervals[proposalId(proposal)]),
        }))
      await api.applyCatalogMaintenances(selections)
      showToast(`${selections.length} entretiens planifiés`)
      setPhase('fin')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Configurer MaBarak</h1>

      {error && <p className="status status--error">{error}</p>}

      {phase === 'zones' && (
        <>
          <p className="page__lead">
            On va faire le tour de chez vous, pièce par pièce. Cochez d'abord ce que vous avez —
            le reste vient après, rien n'est définitif.
          </p>
          <div className="card">
            <h2 className="card__title">Quelles zones avez-vous ?</h2>
            {rooms.map((room) => (
              <label key={room.key} className="complete__checkbox">
                <input
                  type="checkbox"
                  checked={roomKeys.includes(room.key)}
                  onChange={() => setRoomKeys(toggle(roomKeys, room.key))}
                />
                {room.label}
              </label>
            ))}
            <div className="form__actions">
              <button
                type="button"
                className="btn btn--primary"
                disabled={roomKeys.length === 0}
                onClick={startTour}
              >
                Commencer le tour
              </button>
            </div>
          </div>
        </>
      )}

      {phase === 'objets' && currentRoom !== undefined && (
        <>
          <p className="page__lead">
            Zone {roomIndex + 1} sur {selectedRooms.length} — cochez ce que vous avez. Pas de
            date d'achat ni de facture à ce stade, on ne fait que lister.
          </p>
          <div className="card">
            <h2 className="card__title">{currentRoom.label}</h2>
            {currentRoom.items.map((itemKey) => {
              const item = itemsByKey.get(itemKey)
              if (item === undefined) return null
              return (
                <label key={itemKey} className="complete__checkbox">
                  <input
                    type="checkbox"
                    checked={checked.includes(itemKey)}
                    onChange={() => setChecked(toggle(checked, itemKey))}
                  />
                  {item.label}
                </label>
              )
            })}
            <div className="form__actions">
              <button
                type="button"
                className="btn btn--primary"
                disabled={busy}
                onClick={() => void nextRoom(true)}
              >
                {roomIndex + 1 < selectedRooms.length ? 'Suivant' : 'Terminer le tour'}
              </button>
              <button type="button" className="btn" disabled={busy} onClick={() => void nextRoom(false)}>
                Passer cette zone
              </button>
            </div>
          </div>
        </>
      )}

      {phase === 'entretiens' && (
        <>
          <p className="page__lead">
            Voici les entretiens qu'on vous propose. Décochez ce qui ne vous concerne pas et
            ajustez les fréquences qui comptent — tout reste modifiable ensuite.
          </p>
          {proposals.length === 0 ? (
            <div className="card">
              <p className="muted">
                Rien à proposer : aucune fiche n'a été créée, ou tous les entretiens existent déjà.
              </p>
              <div className="form__actions">
                <button type="button" className="btn btn--primary" onClick={() => setPhase('fin')}>
                  Terminer
                </button>
              </div>
            </div>
          ) : (
            <>
              {groupByAsset(proposals).map(([groupName, groupProposals]) => (
                <div className="card" key={groupName}>
                  <h2 className="card__title">{groupName}</h2>
                  {groupProposals.map((proposal) => {
                    const id = proposalId(proposal)
                    const recurrence = proposal.maintenance.recurrence
                    return (
                      <div key={id} className="task">
                        <div className="task__main">
                          <label className="complete__checkbox">
                            <input
                              type="checkbox"
                              checked={!rejected.includes(id)}
                              onChange={() => setRejected(toggle(rejected, id))}
                            />
                            <strong>{proposal.maintenance.label}</strong>
                          </label>
                          {proposal.maintenance.description && (
                            <p className="muted">{proposal.maintenance.description}</p>
                          )}
                          {recurrence.type === 'annual_fixed' ? (
                            <p className="muted">{formatCatalogRecurrence(recurrence)}</p>
                          ) : (
                            <p className="muted interval">
                              Tous les
                              <input
                                type="number"
                                min={1}
                                value={intervals[id] ?? recurrence.interval ?? 1}
                                onChange={(event) =>
                                  setIntervals({ ...intervals, [id]: Number(event.target.value) })
                                }
                              />
                              {unitLabel(recurrence)}
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ))}
              <div className="form__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={busy}
                  onClick={() => void createMaintenances()}
                >
                  Planifier ces entretiens
                </button>
              </div>
            </>
          )}
        </>
      )}

      {phase === 'fin' && (
        <div className="card">
          <h2 className="card__title">C'est prêt</h2>
          <p>
            Votre planning est rempli. Vous pouvez maintenant ajouter vos factures et notices sur
            chaque fiche, au fil du temps — inutile de tout scanner maintenant.
          </p>
          <div className="form__actions">
            <button type="button" className="btn btn--primary" onClick={() => navigate('/')}>
              Voir le tableau de bord
            </button>
            <Link to="/entretiens" className="btn">
              Voir les entretiens
            </Link>
          </div>
        </div>
      )}
    </section>
  )
}

/** Un meme entretien peut concerner plusieurs fiches : la cle seule ne suffit pas. */
function proposalId(proposal: CatalogProposal): string {
  return `${proposal.maintenance.key}:${proposal.asset_id ?? 'maison'}`
}

function groupByAsset(proposals: CatalogProposal[]): [string, CatalogProposal[]][] {
  const groups = new Map<string, CatalogProposal[]>()
  for (const proposal of proposals) {
    const name = proposal.asset_name ?? 'Toute la maison'
    groups.set(name, [...(groups.get(name) ?? []), proposal])
  }
  return [...groups.entries()]
}

function unitLabel(recurrence: CatalogRecurrence): string {
  if (recurrence.type === 'days') return 'jours'
  if (recurrence.type === 'years') return 'ans'
  return 'mois'
}

function adjusted(
  proposal: CatalogProposal,
  interval: number | undefined,
): CatalogRecurrence | null {
  const recurrence = proposal.maintenance.recurrence
  if (interval === undefined || interval === recurrence.interval) return null
  return { ...recurrence, interval }
}
