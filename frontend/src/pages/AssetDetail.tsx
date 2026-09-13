import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type {
  Asset,
  AssetDeleteResult,
  AssetLifecycleStatus,
  Category,
  CostType,
  Costs,
  DocType,
  DocumentDraft,
  DocumentMeta,
  HaDevice,
  Location,
  Member,
  Provider,
  Trade,
} from '../api/types'
import { draftIsEmpty, emptyDraft } from '../api/types'
import BackLink from '../components/BackLink'
import CategorySelect from '../components/CategorySelect'
import CompleteTask from '../components/CompleteTask'
import DocumentEdit, { DOC_TYPES } from '../components/DocumentEdit'
import DocumentInput from '../components/DocumentInput'
import Field from '../components/Field'
import { EditIcon, TrashIcon } from '../components/icons'
import PrioritySelect from '../components/PrioritySelect'
import StatusBadge from '../components/StatusBadge'
import TaskForm from '../components/TaskForm'
import TaskPrepInfo from '../components/TaskPrepInfo'
import { useToast } from '../components/Toast'
import { categoryIcon } from '../lib/categoryIcon'
import {
  COST_TYPE_OPTIONS,
  costTypeLabel,
  docTypeLabel,
  documentWhere,
  emptyToNull,
  equipmentCategories,
  errorMessage,
  formatAmount,
  formatDate,
  formatRecurrence,
  optionalId,
  storageModeLabel,
  structureCategories,
  warrantyAlert,
  warrantyAlertLabel,
} from '../lib/format'

const PHOTO_ACCEPT = '.jpg,.jpeg,.png,.heic'

function WarrantyBadge({ endDate }: { endDate: string | null | undefined }) {
  const level = warrantyAlert(endDate)
  if (level === null) return null
  return <span className={`badge badge--${level === 'expired' ? 'overdue' : 'due_soon'}`}>{warrantyAlertLabel(level)}</span>
}

export default function AssetDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const isElement = location.pathname.startsWith('/elements')
  const basePath = isElement ? '/elements' : '/equipements'
  const baseLabel = isElement ? 'Éléments de la maison' : 'Équipements'
  const assetId = Number(id)
  const [asset, setAsset] = useState<Asset | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [documents, setDocuments] = useState<DocumentMeta[]>([])
  const [devices, setDevices] = useState<HaDevice[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [haUnavailable, setHaUnavailable] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [activeTab, setActiveTab] = useState<'entretiens' | 'details' | 'documents'>('entretiens')

  async function reload() {
    const next = await api.asset(assetId)
    setAsset(next)
  }

  async function reloadDocuments() {
    setDocuments(await api.assetDocuments(assetId))
  }

  useEffect(() => {
    let cancelled = false
    if (!Number.isFinite(assetId)) {
      setError('Fiche introuvable')
      return
    }
    Promise.all([
      api.asset(assetId),
      api.categories(),
      api.locations(),
      api.assetDocuments(assetId),
      api.members(),
      api.providers(),
      api.trades(),
    ])
      .then(
        ([
          nextAsset,
          nextCategories,
          nextLocations,
          nextDocuments,
          nextMembers,
          nextProviders,
          nextTrades,
        ]) => {
        if (cancelled) return
        setAsset(nextAsset)
        setCategories(
          nextAsset.kind === 'building_element'
            ? structureCategories(nextCategories)
            : equipmentCategories(nextCategories),
        )
        setLocations(nextLocations)
        setDocuments(nextDocuments)
        setMembers(nextMembers)
        setProviders(nextProviders)
        setTrades(nextTrades)
      },
      )
      .catch((caught: unknown) => {
        if (!cancelled) setError(errorMessage(caught))
      })
    api
      .haDevices()
      .then((rows) => {
        if (!cancelled) setDevices(rows)
      })
      .catch((caught: unknown) => {
        if (cancelled) return
        if (caught instanceof ApiError && caught.status === 503) {
          setHaUnavailable(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [assetId])

  if (error && asset === null) {
    return (
      <section className="page">
        <p className="status status--error">{error}</p>
        <BackLink to={basePath} label={baseLabel} />
      </section>
    )
  }

  if (asset === null) {
    return (
      <section className="page">
        <p className="muted">Chargement...</p>
      </section>
    )
  }

  const invoiceDocument = documents.find((document) => document.doc_type === 'invoice')
  const isEquipment = asset.kind === 'equipment'

  return (
    <section className="page">
      <BackLink to={basePath} label={baseLabel} />
      <div className="page__header">
        <div className="field__row">
          <AssetPhoto
            asset={asset}
            onChanged={() => void reload().catch((caught) => setError(errorMessage(caught)))}
            onError={setError}
          />
          <div>
            <h1 className="page__title">
              {asset.name} {isEquipment && <WarrantyBadge endDate={asset.warranty?.end_date} />}
              {/* Une fiche retiree se lit comme les autres : sans ce badge, rien
                  ne dirait pourquoi ses entretiens ont disparu du planning. */}
              {asset.status === 'removed' && <span className="badge badge--unscheduled">Retiré</span>}
            </h1>
            <p className="page__lead">
              {[asset.category_name, asset.location_path, formatDate(asset.install_date)]
                .filter((part) => part && part !== '—')
                .join(' · ') || (isEquipment ? 'Fiche appareil' : 'Fiche élément')}
            </p>
          </div>
        </div>
        <button type="button" className="btn btn--edit" onClick={() => setEditing((value) => !value)}>
          {editing ? (
            'Fermer'
          ) : (
            <>
              <EditIcon /> Modifier
            </>
          )}
        </button>
      </div>

      {error && <p className="status status--error">{error}</p>}

      {editing && (
        <EditAsset
          asset={asset}
          categories={categories}
          locations={locations}
          onSaved={(next) => {
            setAsset(next)
            setEditing(false)
          }}
          onError={setError}
          onCategoryCreated={(category) => setCategories((current) => [...current, category])}
        />
      )}

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'entretiens'}
          className={`tabs__tab${activeTab === 'entretiens' ? ' tabs__tab--active' : ''}`}
          onClick={() => setActiveTab('entretiens')}
        >
          Entretiens
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'details'}
          className={`tabs__tab${activeTab === 'details' ? ' tabs__tab--active' : ''}`}
          onClick={() => setActiveTab('details')}
        >
          Details
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'documents'}
          className={`tabs__tab${activeTab === 'documents' ? ' tabs__tab--active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          Documents
        </button>
      </div>

      {activeTab === 'entretiens' && (
        <div className="card">
          {asset.tasks.length === 0 ? (
            <p className="muted">Aucun entretien sur cette fiche.</p>
          ) : (
            <ul className="task-list">
              {asset.tasks.map((task) => (
                <li key={task.id} className="task">
                  <div className="task__main">
                    <strong>{task.name}</strong>
                    <StatusBadge status={task.status} />
                    <PrioritySelect
                      task={task}
                      onChanged={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                    />
                    <p className="muted">
                      {formatRecurrence(task)}
                      {' · dernier '}
                      {formatDate(task.last_completed_on)}
                      {' · prochain '}
                      {formatDate(task.next_due_on)}
                    </p>
                    <TaskPrepInfo task={task} />
                  </div>
                  <CompleteTask
                    task={task}
                    members={members}
                    providers={providers}
                    trades={trades}
                    onMemberCreated={(member) => setMembers((current) => [...current, member])}
                    onProviderCreated={(provider) =>
                      setProviders((current) => [...current, provider])
                    }
                    onCompleted={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                    onEdited={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                    onDeleted={() => void reload().catch((caught) => setError(errorMessage(caught)))}
                  />
                </li>
              ))}
            </ul>
          )}
          <h3 className="card__subtitle">Ajouter un entretien</h3>
          <TaskForm
            members={members}
            providers={providers}
            trades={trades}
            onMemberCreated={(member) => setMembers((current) => [...current, member])}
            onProviderCreated={(provider) => setProviders((current) => [...current, provider])}
            onSubmit={async (body) => {
              await api.createTask(asset.id, body)
              await reload()
            }}
          />
        </div>
      )}

      {activeTab === 'details' && (
        <>
          <div className="card">
            <dl className="facts">
              {isEquipment && (
                <>
                  <dt>Marque</dt>
                  <dd>{asset.brand || '—'}</dd>
                  <dt>Modèle</dt>
                  <dd>{asset.model || '—'}</dd>
                  <dt>N° de serie</dt>
                  <dd>{asset.serial_number || '—'}</dd>
                  <dt>Garantie</dt>
                  <dd>
                    {asset.warranty
                      ? `${formatDate(asset.warranty.start_date)} → ${formatDate(asset.warranty.end_date)}`
                      : '—'}{' '}
                    <WarrantyBadge endDate={asset.warranty?.end_date} />
                    {invoiceDocument && (
                      <>
                        {' · '}
                        <a href={api.documentFileUrl(invoiceDocument.id)} target="_blank" rel="noreferrer">
                          Facture
                        </a>
                      </>
                    )}
                  </dd>
                </>
              )}
              <dt>Notes</dt>
              <dd>{asset.notes || '—'}</dd>
            </dl>
          </div>

          {isEquipment && (
            <HaLinkCard
              asset={asset}
              devices={devices}
              haUnavailable={haUnavailable}
              onChanged={(next) => setAsset(next)}
              onError={setError}
            />
          )}

          <AssetCostsCard
            assetId={asset.id}
            purchaseDate={asset.purchase_date}
            onError={setError}
          />

          <AssetRemovalCard
            asset={asset}
            documentCount={documents.length}
            onChanged={(next) => setAsset(next)}
            onDeleted={() => navigate(basePath, { replace: true })}
            onError={setError}
          />
        </>
      )}

      {activeTab === 'documents' && (
        <AssetDocuments
          assetId={asset.id}
          documents={documents}
          onChanged={() => void reloadDocuments().catch((caught) => setError(errorMessage(caught)))}
          onError={setError}
        />
      )}
    </section>
  )
}

function AssetPhoto({
  asset,
  onChanged,
  onError,
}: {
  asset: Asset
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()

  async function upload(file: File) {
    setBusy(true)
    onError(null)
    try {
      await api.createAssetDocument(asset.id, { mode: 'local_file', file }, { doc_type: 'photo' })
      showToast('Photo mise à jour')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (asset.photo_document_id === null) return
    setBusy(true)
    onError(null)
    try {
      await api.deleteDocument(asset.photo_document_id)
      showToast('Photo supprimée')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="asset-photo">
      <span className="asset-avatar asset-avatar--lg">
        {asset.photo_document_id !== null ? (
          <img src={api.documentFileUrl(asset.photo_document_id)} alt="" />
        ) : (
          categoryIcon(asset.category_slug)
        )}
      </span>
      <input
        ref={inputRef}
        type="file"
        accept={PHOTO_ACCEPT}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) void upload(file)
        }}
      />
      <div className="asset-photo__actions">
        <button
          type="button"
          className="btn btn--small btn--edit"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          <EditIcon /> Changer l'image
        </button>
        {asset.photo_document_id !== null && (
          <button
            type="button"
            className="btn btn--small btn--delete"
            disabled={busy}
            onClick={() => void remove()}
          >
            <TrashIcon /> Supprimer
          </button>
        )}
      </div>
    </div>
  )
}

function DocumentLine({ document }: { document: DocumentMeta }) {
  const where = documentWhere(document)
  const meta = `${docTypeLabel(document.doc_type)} · ${storageModeLabel(document.storage_mode)}`
  return (
    <div className="task__main">
      {document.storage_mode === 'local_file' && (
        <a href={api.documentFileUrl(document.id)} target="_blank" rel="noreferrer">
          <strong>{document.name}</strong>
        </a>
      )}
      {document.storage_mode === 'external_link' && document.url !== null && (
        <a href={document.url} target="_blank" rel="noreferrer">
          <strong>{document.name}</strong>
        </a>
      )}
      {document.storage_mode === 'reference_note' && <strong>{document.name}</strong>}
      <p className="muted">
        {meta}
        {where && ' · '}
        {where && <span className="doc-where">{where}</span>}
      </p>
    </div>
  )
}

function AssetDocuments({
  assetId,
  documents,
  onChanged,
  onError,
}: {
  assetId: number
  documents: DocumentMeta[]
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const [docType, setDocType] = useState<DocType>('manual')
  const [name, setName] = useState('')
  const [draft, setDraft] = useState<DocumentDraft>(emptyDraft())
  const [editing, setEditing] = useState<DocumentMeta | null>(null)
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()

  async function add(event: FormEvent) {
    event.preventDefault()
    if (draftIsEmpty(draft)) {
      onError("Ce document a besoin d'un contenu : un fichier, un lien ou une note.")
      return
    }
    if (draft.mode !== 'local_file' && name.trim() === '') {
      onError('Ce document a besoin d\'un nom : sans fichier, il n\'y en a pas a reprendre.')
      return
    }
    setBusy(true)
    onError(null)
    try {
      await api.createAssetDocument(assetId, draft, { doc_type: docType, name: name.trim() })
      setName('')
      setDraft(emptyDraft())
      showToast('Document ajouté')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove(documentId: number) {
    setBusy(true)
    onError(null)
    try {
      await api.deleteDocument(documentId)
      showToast('Document supprimé')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <p className="muted">
        Notice, facture d'achat, garantie ou contrat d'entretien. Chaque document est un fichier
        déposé ici, un lien vers votre propre stockage, ou une simple note disant où le trouver.
      </p>
      {documents.length === 0 ? (
        <p className="muted">Aucun document pour l'instant.</p>
      ) : (
        <ul className="task-list">
          {documents.map((document) => (
            <li key={document.id} className="task">
              <DocumentLine document={document} />
              <div className="doc-actions">
                <button
                  type="button"
                  className="btn btn--small btn--edit"
                  disabled={busy}
                  onClick={() => {
                    onError(null)
                    setEditing(document)
                  }}
                >
                  <EditIcon /> Modifier
                </button>
                <button
                  type="button"
                  className="btn btn--small btn--delete"
                  disabled={busy}
                  onClick={() => void remove(document.id)}
                >
                  <TrashIcon /> Supprimer
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <h3 className="card__subtitle">Ajouter un document</h3>
      <form className="form" onSubmit={(event) => void add(event)}>
        <div className="doc-form__row">
          <Field label="Type">
            <select value={docType} onChange={(event) => setDocType(event.target.value as DocType)}>
              {DOC_TYPES.map((value) => (
                <option key={value} value={value}>
                  {docTypeLabel(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label={draft.mode === 'local_file' ? 'Nom (facultatif)' : 'Nom'}
            hint={draft.mode === 'local_file' ? 'Par défaut, le nom du fichier.' : undefined}
          >
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Facture d'achat"
            />
          </Field>
        </div>
        <div className="field">
          <span className="field__label">Où se trouve ce document</span>
          <DocumentInput value={draft} onChange={setDraft} disabled={busy} />
        </div>
        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Ajouter
          </button>
        </div>
      </form>
      {editing !== null && (
        <DocumentEdit
          document={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            onChanged()
          }}
          onError={onError}
        />
      )}
    </div>
  )
}

function EditAsset({
  asset,
  categories,
  locations,
  onSaved,
  onError,
  onCategoryCreated,
}: {
  asset: Asset
  categories: Category[]
  locations: Location[]
  onSaved: (asset: Asset) => void
  onError: (message: string | null) => void
  onCategoryCreated: (category: Category) => void
}) {
  const [name, setName] = useState(asset.name)
  const [categoryId, setCategoryId] = useState(asset.category_id ? String(asset.category_id) : '')
  const [locationId, setLocationId] = useState(asset.location_id ? String(asset.location_id) : '')
  const [installDate, setInstallDate] = useState(asset.install_date ?? '')
  const [brand, setBrand] = useState(asset.brand ?? '')
  const [model, setModel] = useState(asset.model ?? '')
  const [serial, setSerial] = useState(asset.serial_number ?? '')
  const [notes, setNotes] = useState(asset.notes ?? '')
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()
  const isEquipment = asset.kind === 'equipment'

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    onError(null)
    try {
      const next = await api.patchAsset(asset.id, {
        name: name.trim(),
        category_id: optionalId(categoryId),
        location_id: optionalId(locationId),
        install_date: emptyToNull(installDate),
        brand: emptyToNull(brand),
        model: emptyToNull(model),
        serial_number: emptyToNull(serial),
        notes: emptyToNull(notes),
      })
      showToast('Fiche mise à jour')
      onSaved(next)
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card form" onSubmit={(event) => void submit(event)}>
      <Field label="Nom">
        <input required value={name} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="Catégorie">
        <CategorySelect
          categories={categories}
          value={categoryId}
          onChange={setCategoryId}
          onCreated={onCategoryCreated}
        />
      </Field>
      <Field label="Lieu">
        <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
          <option value="">Non rangé</option>
          {locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.path}
            </option>
          ))}
        </select>
      </Field>
      <Field label="1re mise en service">
        <input
          type="date"
          value={installDate}
          onChange={(event) => setInstallDate(event.target.value)}
        />
      </Field>
      {isEquipment && (
        <>
          <Field label="Marque">
            <input value={brand} onChange={(event) => setBrand(event.target.value)} />
          </Field>
          <Field label="Modèle">
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </Field>
          <Field label="Numéro de série">
            <input value={serial} onChange={(event) => setSerial(event.target.value)} />
          </Field>
        </>
      )}
      <Field label="Notes">
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
      </Field>
      <button type="submit" className="btn btn--primary" disabled={busy}>
        Enregistrer
      </button>
    </form>
  )
}

function HaLinkCard({
  asset,
  devices,
  haUnavailable,
  onChanged,
  onError,
}: {
  asset: Asset
  devices: HaDevice[]
  haUnavailable: boolean
  onChanged: (asset: Asset) => void
  onError: (message: string | null) => void
}) {
  const [deviceId, setDeviceId] = useState(asset.ha_link?.ha_device_id ?? '')
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()

  async function link() {
    const selected = devices.find((row) => row.ha_device_id === deviceId)
    if (!selected) return
    setBusy(true)
    onError(null)
    try {
      const next = await api.putHaLink(asset.id, {
        ha_device_id: selected.ha_device_id,
        name_at_link: selected.name,
        entity_id_at_link: selected.entity_id,
        domain_at_link: selected.domain,
        area_name: asset.location_id ? null : selected.area_name,
      })
      showToast('Appareil lié')
      onChanged(next)
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function unlink() {
    setBusy(true)
    onError(null)
    try {
      onChanged(await api.deleteHaLink(asset.id))
      showToast('Appareil détaché')
      setDeviceId('')
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <h2 className="card__title">Lien Home Assistant</h2>
      {asset.ha_link ? (
        <p>
          Lie a <strong>{asset.ha_link.name_at_link}</strong>
          {asset.ha_link.entity_id_at_link ? ` (${asset.ha_link.entity_id_at_link})` : ''}.
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => void unlink()}>
            Detacher
          </button>
        </p>
      ) : haUnavailable ? (
        <p className="muted">Indisponible hors add-on Home Assistant.</p>
      ) : (
        <form
          className="form form--inline"
          onSubmit={(event) => {
            event.preventDefault()
            void link()
          }}
        >
          <select value={deviceId} onChange={(event) => setDeviceId(event.target.value)}>
            <option value="">Choisir un appareil</option>
            {devices.map((device) => (
              <option key={device.ha_device_id} value={device.ha_device_id}>
                {device.name}
                {device.area_name ? ` (${device.area_name})` : ''}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn--primary" disabled={busy || !deviceId}>
            Lier
          </button>
        </form>
      )}
    </div>
  )
}

/** Les deux sorties d'une fiche, et la difference entre les deux.
 *
 *  `schema.sql` tranche : un equipement retire reste en base, parce que son
 *  historique et ses couts font partie de l'histoire de la maison. C'est donc
 *  « Retirer » qui est propose en premier, et la suppression definitive qui doit
 *  se justifier — le doublon, la fiche creee par erreur pendant le didacticiel.
 *  La confirmation annonce ce qui va partir avant de partir : une fiche vide ne
 *  merite pas le meme avertissement qu'une fiche portant dix ans d'entretiens. */
function AssetRemovalCard({
  asset,
  documentCount,
  onChanged,
  onDeleted,
  onError,
}: {
  asset: Asset
  documentCount: number
  onChanged: (asset: Asset) => void
  onDeleted: () => void
  onError: (message: string | null) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()
  const isRemoved = asset.status === 'removed'
  const noun = asset.kind === 'building_element' ? 'Cet élément' : 'Cet appareil'

  async function setStatus(status: AssetLifecycleStatus, message: string) {
    setBusy(true)
    onError(null)
    try {
      onChanged(await api.patchAsset(asset.id, { status }))
      showToast(message)
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    onError(null)
    try {
      const result = await api.deleteAsset(asset.id)
      showToast(`${asset.name} supprimé · ${summarise(result)}`)
      onDeleted()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
      setBusy(false)
      setConfirming(false)
    }
  }

  return (
    <div className="card">
      <h2 className="card__title">Sortie de la fiche</h2>

      {isRemoved ? (
        <>
          <p className="muted">
            {noun} est marqué comme retiré : il ne compte plus dans le planning, mais sa fiche, son
            historique et ses coûts restent consultables.
          </p>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void setStatus('active', 'Remis en service')}
          >
            Remettre en service
          </button>
        </>
      ) : (
        <>
          <p className="muted">
            Vendu, remplacé, déposé ? Retirez-le plutôt que de le supprimer : ses entretiens
            quittent le planning, et son historique reste dans celui de la maison.
          </p>
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void setStatus('removed', 'Retiré de la maison')}
          >
            Retirer de la maison
          </button>
        </>
      )}

      <hr className="card__rule" />

      {confirming ? (
        <>
          <p className="status status--error">
            Supprimer définitivement « {asset.name} » ? Cette action efface aussi{' '}
            {countList(asset.tasks.length, documentCount)}, et ne peut pas être annulée.
          </p>
          <div className="complete__actions">
            <button type="button" className="btn btn--delete" disabled={busy} onClick={() => void remove()}>
              <TrashIcon /> Oui, tout supprimer
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setConfirming(false)}>
              Annuler
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="muted">
            Fiche créée par erreur, doublon, mauvaise saisie : la suppression définitive emporte la
            fiche, ses entretiens, son historique, ses coûts et ses fichiers.
          </p>
          <button
            type="button"
            className="btn btn--small btn--delete"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            <TrashIcon /> Supprimer définitivement
          </button>
        </>
      )}
    </div>
  )
}

/** « 3 entretiens et 2 documents », sans les zeros qui n'apprennent rien. */
function countList(tasks: number, documents: number): string {
  const parts: string[] = []
  if (tasks > 0) parts.push(`${tasks} entretien${tasks > 1 ? 's' : ''} et leur historique`)
  if (documents > 0) parts.push(`${documents} document${documents > 1 ? 's' : ''}`)
  if (parts.length === 0) return 'tout ce qui y est rattaché'
  return parts.join(' et ')
}

function summarise(result: AssetDeleteResult): string {
  const parts: string[] = []
  if (result.deleted_tasks > 0) parts.push(`${result.deleted_tasks} entretien(s)`)
  if (result.deleted_interventions > 0) parts.push(`${result.deleted_interventions} intervention(s)`)
  if (result.deleted_files > 0) parts.push(`${result.deleted_files} fichier(s)`)
  return parts.length > 0 ? parts.join(', ') : 'rien d’autre n’y était rattaché'
}

/** Ce que l'appareil a coute, depuis son achat.
 *
 *  `schema.sql` annonce « la section 18 affiche explicitement un total par
 *  equipement », et le README promet de savoir « combien il a coute ». En
 *  pratique, seule la validation d'un entretien ecrivait une ligne, toujours en
 *  `maintenance` : le prix d'achat et la pose n'existaient nulle part, et rien
 *  n'additionnait. Le total compte tout, entretiens compris — c'est la question
 *  posee. */
function AssetCostsCard({
  assetId,
  purchaseDate,
  onError,
}: {
  assetId: number
  purchaseDate: string | null
  onError: (message: string | null) => void
}) {
  const [costs, setCosts] = useState<Costs | null>(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [type, setType] = useState<CostType>('purchase')
  const [amount, setAmount] = useState('')
  const [label, setLabel] = useState('')
  const [on, setOn] = useState('')
  const { showToast } = useToast()

  useEffect(() => {
    let cancelled = false
    api
      .assetCosts(assetId)
      .then((next) => {
        if (!cancelled) setCosts(next)
      })
      .catch((caught: unknown) => {
        if (!cancelled) onError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [assetId, onError])

  async function reload() {
    setCosts(await api.assetCosts(assetId))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    // Saisi en euros, stocke en centimes : additionner des flottants pour
    // afficher un total produit des erreurs d'arrondi visibles (schema.sql).
    const cents = Math.round(Number(amount.replace(',', '.')) * 100)
    if (!Number.isFinite(cents) || cents <= 0) {
      onError('Le montant doit être un nombre supérieur à zéro.')
      return
    }
    setBusy(true)
    onError(null)
    try {
      await api.createAssetCost(assetId, {
        cost_type: type,
        amount_cents: cents,
        label: label.trim() || null,
        incurred_on: on || null,
      })
      setAmount('')
      setLabel('')
      setOn('')
      setAdding(false)
      await reload()
      showToast('Dépense ajoutée')
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove(costId: number) {
    setBusy(true)
    onError(null)
    try {
      await api.deleteCost(costId)
      await reload()
      showToast('Dépense supprimée')
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  if (costs === null) return null

  return (
    <div className="card">
      <h2 className="card__title">
        Coûts
        {costs.total_cents > 0 && (
          <span className="card__total">{formatAmount(costs.total_cents, costs.currency)}</span>
        )}
      </h2>

      {costs.items.length === 0 ? (
        <p className="muted">
          Aucune dépense enregistrée. Ajoutez le prix d'achat pour savoir, plus tard, ce que cet
          appareil vous aura coûté.
        </p>
      ) : (
        <ul className="cost-list">
          {costs.items.map((item) => (
            <li key={item.id} className="cost">
              <span className="cost__amount">{formatAmount(item.amount_cents, item.currency)}</span>
              <span className="cost__detail">
                {costTypeLabel(item.cost_type)}
                {item.task_name ? ` · ${item.task_name}` : ''}
                {item.label ? ` · ${item.label}` : ''}
                {` · ${formatDate(item.incurred_on)}`}
              </span>
              {item.intervention_id === null ? (
                <button
                  type="button"
                  className="btn btn--small btn--delete"
                  disabled={busy}
                  onClick={() => void remove(item.id)}
                  aria-label={`Supprimer la dépense de ${formatAmount(item.amount_cents, item.currency)}`}
                >
                  <TrashIcon />
                </button>
              ) : (
                // Saisie en validant un entretien : elle se corrige la-bas, sinon
                // l'historique annoncerait un montant introuvable.
                <span className="muted cost__origine">depuis l'historique</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {adding ? (
        <form className="form form--inline" onSubmit={submit}>
          <select value={type} onChange={(event) => setType(event.target.value as CostType)}>
            {COST_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="0,00"
            aria-label="Montant en euros"
            required
          />
          <input
            type="date"
            value={on}
            onChange={(event) => setOn(event.target.value)}
            aria-label="Date de la dépense"
            placeholder={purchaseDate ?? ''}
          />
          <input
            type="text"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Intitulé (facultatif)"
            aria-label="Intitulé"
          />
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Ajouter
          </button>
          <button type="button" className="btn" disabled={busy} onClick={() => setAdding(false)}>
            Annuler
          </button>
        </form>
      ) : (
        <button type="button" className="btn btn--small" onClick={() => setAdding(true)}>
          Ajouter une dépense
        </button>
      )}
    </div>
  )
}
