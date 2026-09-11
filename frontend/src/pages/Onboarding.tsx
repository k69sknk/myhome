import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type {
  AssetKind,
  AssetListItem,
  Catalog,
  CatalogItem,
  CatalogProposal,
  CatalogRoomState,
  LocationType,
  MaintenanceSelection,
  Member,
  Provider,
  RecurrenceType,
  TaskIn,
  Trade,
} from '../api/types'
import Field from '../components/Field'
import Modal from '../components/Modal'
import TaskForm from '../components/TaskForm'
import { useToast } from '../components/Toast'
import { EditIcon } from '../components/icons'
import { errorMessage, formatRecurrence, formatSeason } from '../lib/format'
import { matches, normalize } from '../lib/search'

type Phase = 'zones' | 'objets' | 'entretiens' | 'fin'

/** Un entretien en attente de validation : pré-rempli depuis le catalogue, ou
 *  ajouté de toutes pièces. Rien n'est créé en base avant le clic final, donc le
 *  crayon édite ce brouillon — et on ne perd pas le reste du récapitulatif. */
interface Draft {
  id: string
  catalogKey: string | null
  assetId: number | null
  assetName: string | null
  locationPath: string | null
  task: TaskIn
}

/** Zone ajoutee par l'utilisateur : le catalogue ne couvrira jamais tous les
 *  logements (atelier, veranda, cellier...). Elle n'a pas de cle de catalogue. */
interface CustomRoom {
  label: string
  locationId: number
}

export default function Onboarding() {
  const navigate = useNavigate()
  const { showToast } = useToast()

  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [state, setState] = useState<CatalogRoomState[]>([])
  const [locationTypes, setLocationTypes] = useState<LocationType[]>([])
  const [phase, setPhase] = useState<Phase>('zones')
  const [roomKeys, setRoomKeys] = useState<string[]>([])
  const [customRooms, setCustomRooms] = useState<CustomRoom[]>([])
  const [roomIndex, setRoomIndex] = useState(0)
  const [checked, setChecked] = useState<string[]>([])
  /** Objets du catalogue tires dans la zone courante alors qu'elle ne les
   *  proposait pas : un adoucisseur peut vivre a la cuisine comme au cellier. */
  const [extraKeys, setExtraKeys] = useState<string[]>([])
  /** Ce que le catalogue ne connait pas du tout, cree avec la zone. */
  const [customItems, setCustomItems] = useState<{ name: string; kind: AssetKind }[]>([])
  /** Ce qui existe deja dans la maison, pour prevenir avant de creer un sosie
   *  dans une autre piece. Rafraichi apres chaque zone enregistree. */
  const [assets, setAssets] = useState<AssetListItem[]>([])
  const [filter, setFilter] = useState('')
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [rejected, setRejected] = useState<string[]>([])
  const [editing, setEditing] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.catalog(),
      api.catalogState(),
      api.locationTypes(),
      api.members(),
      api.assets(),
      api.providers(),
      api.trades(),
    ])
      .then(
        ([
          nextCatalog,
          nextState,
          nextTypes,
          nextMembers,
          nextAssets,
          nextProviders,
          nextTrades,
        ]) => {
        if (cancelled) return
        setCatalog(nextCatalog)
        setState(nextState)
        setLocationTypes(nextTypes)
        setMembers(nextMembers)
        setAssets(nextAssets)
        setProviders(nextProviders)
        setTrades(nextTrades)
        },
      )
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
  const stateByRoom = new Map(state.map((row) => [row.room_key, row]))
  const allItemKeys = catalog.items.filter((item) => !item.deprecated).map((item) => item.key)

  /** Une étape du tour : une zone du catalogue, ou une zone créée par l'utilisateur.
   *  Une zone perso n'a pas de liste d'objets propre, on propose donc tout le
   *  catalogue — sinon un atelier ne pourrait contenir que des objets prévus ailleurs. */
  const stops = [
    ...roomKeys.flatMap((key) => {
      const room = rooms.find((candidate) => candidate.key === key)
      return room === undefined
        ? []
        : [
            {
              label: room.label,
              roomKey: room.key as string | null,
              locationId: null as number | null,
              items: room.items,
              present: stateByRoom.get(room.key)?.present_items ?? [],
            },
          ]
    }),
    ...customRooms.map((room) => ({
      label: room.label,
      roomKey: null as string | null,
      locationId: room.locationId as number | null,
      items: allItemKeys,
      present: [] as string[],
    })),
  ]
  const currentRoom = stops[roomIndex]

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
  }

  function startTour() {
    if (stops.length === 0) return
    setRoomIndex(0)
    setChecked([])
    setExtraKeys([])
    setCustomItems([])
    setPhase('objets')
  }

  async function addCustomRoom(label: string, locationTypeId: number) {
    setBusy(true)
    setError(null)
    try {
      const created = await api.createLocation({
        name: label.trim(),
        location_type_id: locationTypeId,
      })
      setCustomRooms([...customRooms, { label: created.name, locationId: created.id }])
      showToast('Zone ajoutée')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function goToProposals() {
    setBusy(true)
    setError(null)
    try {
      const rows = await api.catalogProposals()
      setDrafts(rows.map(toDraft))
      setPhase('entretiens')
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  function updateDraft(id: string, task: TaskIn) {
    setDrafts(drafts.map((draft) => (draft.id === id ? { ...draft, task } : draft)))
  }

  /** Le « + » d'un élément : un entretien que le catalogue ne propose pas. */
  function addDraft(assetId: number | null, assetName: string | null, path: string | null) {
    const id = `ajout:${assetId ?? 'maison'}:${Date.now()}`
    setDrafts([
      ...drafts,
      {
        id,
        catalogKey: null,
        assetId,
        assetName,
        locationPath: path,
        task: { name: '', recurrence_type: 'months', recurrence_interval: 6 },
      },
    ])
    setEditing(id)
  }

  /** Enregistre la zone courante avant d'avancer : l'app est utilisable a mi-parcours. */
  async function nextRoom(save: boolean) {
    if (currentRoom === undefined) return
    setBusy(true)
    setError(null)
    try {
      if (save && (checked.length > 0 || customItems.length > 0)) {
        await api.applyCatalogRoom(
          { roomKey: currentRoom.roomKey, locationId: currentRoom.locationId },
          checked,
          customItems,
        )
        // La zone suivante doit savoir ce qui vient d'etre cree : c'est ce qui
        // permet de signaler « existe deja dans la cuisine ».
        setAssets(await api.assets())
      }
      setChecked([])
      setExtraKeys([])
      setCustomItems([])
      setFilter('')
      if (roomIndex + 1 < stops.length) {
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

  const retained = drafts.filter(
    (draft) => !rejected.includes(draft.id) && draft.task.name.trim() !== '',
  )
  const editingDraft = drafts.find((draft) => draft.id === editing)

  async function createMaintenances() {
    setBusy(true)
    setError(null)
    try {
      const selections: MaintenanceSelection[] = retained.map((draft) => ({
        key: draft.catalogKey,
        asset_id: draft.assetId,
        task: draft.task,
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
            {rooms.map((room) => {
              const known = stateByRoom.get(room.key)
              const count = known?.present_items.length ?? 0
              return (
                <label key={room.key} className="complete__checkbox">
                  <input
                    type="checkbox"
                    checked={roomKeys.includes(room.key)}
                    onChange={() => setRoomKeys(toggle(roomKeys, room.key))}
                  />
                  {room.label}
                  {known?.location_id != null && (
                    <span className="muted">
                      {count > 0
                        ? ` · déjà renseignée, ${count} élément${count > 1 ? 's' : ''}`
                        : ' · déjà créée'}
                    </span>
                  )}
                </label>
              )
            })}
            {customRooms.map((room) => (
              <label key={room.locationId} className="complete__checkbox">
                <input type="checkbox" checked readOnly />
                {room.label}
                <span className="muted"> · à vous</span>
              </label>
            ))}

            <CustomRoomForm
              locationTypes={locationTypes}
              busy={busy}
              onAdd={(label, typeId) => void addCustomRoom(label, typeId)}
            />

            <div className="form__actions">
              <button
                type="button"
                className="btn btn--primary"
                disabled={stops.length === 0}
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
            Zone {roomIndex + 1} sur {stops.length} — cochez ce que vous avez. Pas de date
            d'achat ni de facture à ce stade, on ne fait que lister.
          </p>
          <div className="card">
            <h2 className="card__title">{currentRoom.label}</h2>
            {currentRoom.locationId !== null && (
              <p className="muted">
                Zone que vous avez ajoutée : tout le catalogue vous est proposé. Tapez pour
                filtrer.
              </p>
            )}
            {currentRoom.locationId !== null && (
              <Field label="Filtrer">
                <input value={filter} onChange={(event) => setFilter(event.target.value)} />
              </Field>
            )}
            {[...currentRoom.items, ...extraKeys]
              .filter((itemKey) => {
                if (currentRoom.locationId === null || filter.trim() === '') return true
                const item = itemsByKey.get(itemKey)
                return item !== undefined && matches([item.label], filter)
              })
              .map((itemKey) => {
                const item = itemsByKey.get(itemKey)
                if (item === undefined) return null
                const already = currentRoom.present.includes(itemKey)
                return (
                  <label key={itemKey} className="complete__checkbox">
                    <input
                      type="checkbox"
                      checked={already || checked.includes(itemKey)}
                      disabled={already}
                      onChange={() => setChecked(toggle(checked, itemKey))}
                    />
                    {item.label}
                    {already && <span className="muted"> · déjà là</span>}
                  </label>
                )
              })}
            {customItems.map((item) => (
              <label key={item.name} className="complete__checkbox">
                {/* Decocher un ajout manuel le retire : une ligne ajoutee puis
                    decochee ne veut rien dire, contrairement a une case du catalogue. */}
                <input
                  type="checkbox"
                  checked
                  onChange={() =>
                    setCustomItems(customItems.filter((row) => row.name !== item.name))
                  }
                />
                {item.name}
                <span className="muted"> · à vous</span>
              </label>
            ))}

            <ItemAdd
              items={catalog.items.filter((item) => !item.deprecated)}
              shown={[...currentRoom.items, ...extraKeys]}
              customNames={customItems.map((item) => item.name)}
              assets={assets}
              onPick={(item) => {
                // Deja propose par la zone : il n'y a qu'a le cocher, l'ajouter
                // une seconde fois afficherait deux lignes identiques.
                if (!currentRoom.items.includes(item.key)) {
                  setExtraKeys((current) =>
                    current.includes(item.key) ? current : [...current, item.key],
                  )
                }
                setChecked((current) =>
                  current.includes(item.key) ? current : [...current, item.key],
                )
              }}
              onAdd={(name, kind) => setCustomItems([...customItems, { name, kind }])}
            />

            <div className="form__actions">
              <button
                type="button"
                className="btn btn--primary"
                disabled={busy}
                onClick={() => void nextRoom(true)}
              >
                {roomIndex + 1 < stops.length ? 'Suivant' : 'Terminer le tour'}
              </button>
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => void nextRoom(false)}
              >
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
          {drafts.length > 0 && <Volume drafts={retained} />}
          {drafts.length === 0 ? (
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
              {groupDrafts(drafts).map((group) => (
                <div className="card" key={group.key}>
                  <h2 className="card__title">{group.label}</h2>
                  {group.drafts.map((draft) => (
                    <div key={draft.id} className="task">
                      <div className="task__main">
                        <div className="proposal__header">
                          <label className="complete__checkbox">
                            <input
                              type="checkbox"
                              checked={!rejected.includes(draft.id)}
                              onChange={() => setRejected(toggle(rejected, draft.id))}
                            />
                            <strong>{draft.task.name || 'Sans nom'}</strong>
                          </label>
                          <button
                            type="button"
                            className="btn btn--small"
                            aria-label={`Modifier ${draft.task.name}`}
                            onClick={() => setEditing(draft.id)}
                          >
                            <EditIcon />
                          </button>
                        </div>
                        {draft.task.notes && <p className="muted">{draft.task.notes}</p>}
                        {draft.task.recurrence_type === 'annual_fixed' ? (
                          <p className="muted">{formatRecurrence(draft.task)}</p>
                        ) : (
                          <p className="muted interval">
                            Tous les
                            <input
                              type="number"
                              min={1}
                              value={draft.task.recurrence_interval ?? 1}
                              onChange={(event) =>
                                updateDraft(draft.id, {
                                  ...draft.task,
                                  recurrence_interval: Number(event.target.value),
                                })
                              }
                            />
                            {unitLabel(draft.task.recurrence_type)}
                            {/* La saison n'est pas modifiable ici : le crayon ouvre
                                la fiche complete. Elle est affichee pour qu'on ne
                                croie pas a un entretien hebdomadaire toute l'annee. */}
                            {formatSeason(
                              draft.task.season_start_month,
                              draft.task.season_end_month,
                            )}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="form__actions">
                    <button
                      type="button"
                      className="btn btn--small"
                      onClick={() =>
                        addDraft(group.assetId, group.assetName, group.locationPath)
                      }
                    >
                      + Ajouter un entretien
                    </button>
                  </div>
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

          {editingDraft !== undefined && (
            <Modal
              title={editingDraft.task.name || 'Nouvel entretien'}
              onClose={() => {
                // Un ajout abandonne sans nom ne doit pas rester dans la liste.
                if (editingDraft.task.name.trim() === '') {
                  setDrafts(drafts.filter((draft) => draft.id !== editingDraft.id))
                }
                setEditing(null)
              }}
            >
              <TaskForm
                members={members}
                providers={providers}
                trades={trades}
                onMemberCreated={(member) => setMembers((current) => [...current, member])}
                onProviderCreated={(provider) => setProviders((current) => [...current, provider])}
                initial={editingDraft.task}
                onSubmit={async (body) => {
                  updateDraft(editingDraft.id, body)
                  setEditing(null)
                }}
                onCancel={() => setEditing(null)}
              />
            </Modal>
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

/** Ajouter a la zone courante ce que la liste ne propose pas.

 *  Deux sorties, et c'est tout l'interet : un nom que le catalogue connait
 *  ramene a SA fiche type — sinon on obtiendrait une jumelle sans entretiens —
 *  et seul un nom vraiment inconnu cree une fiche libre. Un objet du meme nom
 *  ailleurs dans la maison n'est pas interdit (deux salles d'eau, deux lavabos)
 *  mais il est signale : c'est le plus souvent une saisie en double.
 */
function ItemAdd({
  items,
  shown,
  customNames,
  assets,
  onPick,
  onAdd,
}: {
  items: CatalogItem[]
  shown: string[]
  customNames: string[]
  assets: AssetListItem[]
  onPick: (item: CatalogItem) => void
  onAdd: (name: string, kind: AssetKind) => void
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  const trimmed = query.trim()
  const needle = normalize(trimmed)
  const inZone = new Set(shown)
  // Les objets deja affiches dans la zone restent proposes, signales comme tels :
  // les masquer laisserait « creer » pour seule issue a qui tape « hotte », et
  // ferait naitre le sosie que cet ecran cherche justement a eviter.
  const found = items.filter((item) => matches([item.label], trimmed))
  const knownLabel = items.some((item) => normalize(item.label) === needle)
  const alreadyHere = customNames.some((name) => normalize(name) === needle)
  const canCreate = trimmed !== '' && !knownLabel && !alreadyHere
  /** Ou ce nom existe deja dans la maison. Plusieurs fois : plusieurs lieux. */
  const elsewhere = assets
    .filter((asset) => normalize(asset.name) === needle)
    .map((asset) => asset.location_path ?? 'sans lieu')

  function pick(item: CatalogItem) {
    onPick(item)
    setQuery('')
    setOpen(false)
  }

  function create(kind: AssetKind) {
    onAdd(trimmed, kind)
    setQuery('')
    setOpen(false)
  }

  return (
    <div className="combobox combobox--clearable" ref={containerRef}>
      <input
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        placeholder="Ajouter autre chose : adoucisseur, aquarium..."
      />
      {query !== '' && (
        <button
          type="button"
          className="combobox__clear"
          aria-label="Effacer"
          onClick={() => setQuery('')}
        >
          ×
        </button>
      )}
      {open && trimmed !== '' && (
        <ul className="combobox__list">
          {found.map((item) => {
            const seen = assets.filter((asset) => normalize(asset.name) === normalize(item.label))
            const places = seen.map((asset) => asset.location_path ?? 'sans lieu')
            return (
              <li key={item.key}>
                <button type="button" className="combobox__option" onClick={() => pick(item)}>
                  {item.label}
                  <span className="combobox__option-meta">
                    {inZone.has(item.key) && ' · dans la liste ci-dessus, cochez-le'}
                    {places.length > 0 && ` · déjà dans ${places.join(', ')}`}
                  </span>
                </button>
              </li>
            )
          })}
          {alreadyHere && <li className="combobox__empty">Déjà ajouté à cette zone.</li>}
          {elsewhere.length > 0 && (
            <li className="combobox__empty">
              « {trimmed} » existe déjà dans {elsewhere.join(', ')}. Deux exemplaires, c'est
              possible ; deux fois le même, non.
            </li>
          )}
          {canCreate && (
            <>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  onClick={() => create('equipment')}
                >
                  + Ajouter l'appareil « {trimmed} »
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="combobox__option combobox__option--create"
                  onClick={() => create('building_element')}
                >
                  + Ajouter l'élément de la maison « {trimmed} »
                </button>
              </li>
            </>
          )}
          {found.length === 0 && !canCreate && !alreadyHere && (
            <li className="combobox__empty">Rien de ce nom au catalogue.</li>
          )}
        </ul>
      )}
    </div>
  )
}

function CustomRoomForm({
  locationTypes,
  busy,
  onAdd,
}: {
  locationTypes: LocationType[]
  busy: boolean
  onAdd: (label: string, locationTypeId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [typeId, setTypeId] = useState('')

  const defaultType = locationTypes.find((type) => type.slug === 'room') ?? locationTypes[0]
  if (defaultType === undefined) return null

  if (!open) {
    return (
      <div className="form__actions">
        <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
          + Ajouter une zone
        </button>
      </div>
    )
  }

  return (
    <div className="card">
      <p className="muted">Une pièce que le catalogue ne propose pas : atelier, véranda…</p>
      <Field label="Nom">
        <input value={label} onChange={(event) => setLabel(event.target.value)} autoFocus />
      </Field>
      <Field label="Type de lieu">
        <select value={typeId} onChange={(event) => setTypeId(event.target.value)}>
          <option value="">{defaultType.name}</option>
          {locationTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name}
            </option>
          ))}
        </select>
      </Field>
      <div className="form__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || label.trim() === ''}
          onClick={() => {
            onAdd(label, typeId === '' ? defaultType.id : Number(typeId))
            setLabel('')
            setTypeId('')
            setOpen(false)
          }}
        >
          Ajouter
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          Annuler
        </button>
      </div>
    </div>
  )
}

/** Ce que la sélection engage réellement, pour que le choix soit éclairé plutôt
 *  que validé d'un clic sur quarante entretiens pré-cochés. */
function Volume({ drafts }: { drafts: Draft[] }) {
  const perYear = drafts.reduce((total, draft) => {
    const interval = draft.task.recurrence_interval ?? 1
    if (draft.task.recurrence_type === 'annual_fixed') return total + 1
    if (draft.task.recurrence_type === 'days') return total + 365 / interval
    if (draft.task.recurrence_type === 'years') return total + 1 / interval
    if (draft.task.recurrence_type === 'custom_date') return total + 1
    return total + 12 / interval
  }, 0)
  // Sous un par mois, la cadence annuelle se lit beaucoup mieux que « 0,8 par mois ».
  const cadence =
    perYear >= 12
      ? `environ ${Math.round(perYear / 12)} par mois`
      : `environ ${Math.round(perYear)} par an`

  if (drafts.length === 0) {
    return <p className="notice">Aucun entretien retenu pour l'instant.</p>
  }
  return (
    <p className="notice">
      <strong>
        {drafts.length} entretien{drafts.length > 1 ? 's' : ''} retenu
        {drafts.length > 1 ? 's' : ''}
      </strong>{' '}
      — {cadence} une fois en place.
    </p>
  )
}

function toDraft(proposal: CatalogProposal): Draft {
  return {
    // Un meme entretien concerne parfois plusieurs fiches : la cle seule ne suffit pas.
    id: `${proposal.maintenance.key}:${proposal.asset_id ?? 'maison'}`,
    catalogKey: proposal.maintenance.key,
    assetId: proposal.asset_id,
    assetName: proposal.asset_name,
    locationPath: proposal.location_path,
    task: proposal.draft,
  }
}

interface DraftGroup {
  key: string
  label: string
  assetId: number | null
  assetName: string | null
  locationPath: string | null
  drafts: Draft[]
}

/** Groupe par FICHE et non par nom : un même objet existe souvent dans plusieurs
 *  zones (volets, fenêtres, siphon), et grouper par nom empilait des entretiens
 *  identiques sans rien pour les distinguer. Le lieu lève l'ambiguïté. */
function groupDrafts(drafts: Draft[]): DraftGroup[] {
  const groups = new Map<string, DraftGroup>()
  for (const draft of drafts) {
    const key = String(draft.assetId ?? 'maison')
    const existing = groups.get(key)
    if (existing === undefined) {
      groups.set(key, {
        key,
        label:
          draft.assetName === null
            ? 'Toute la maison'
            : draft.locationPath
              ? `${draft.assetName} — ${draft.locationPath}`
              : draft.assetName,
        assetId: draft.assetId,
        assetName: draft.assetName,
        locationPath: draft.locationPath,
        drafts: [draft],
      })
    } else {
      existing.drafts.push(draft)
    }
  }
  return [...groups.values()]
}

function unitLabel(type: RecurrenceType): string {
  if (type === 'days') return 'jours'
  if (type === 'years') return 'ans'
  return 'mois'
}
