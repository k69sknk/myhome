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
  Issue,
  IssuePatch,
  IssueSeverity,
  Location,
  Member,
  Provider,
  TimelineEntry,
  Trade,
} from '../api/types'
import { draftIsEmpty, emptyDraft } from '../api/types'
import BackLink from '../components/BackLink'
import CategorySelect from '../components/CategorySelect'
import CompleteTask from '../components/CompleteTask'
import DocumentEdit, { DOC_TYPES } from '../components/DocumentEdit'
import DocumentInput from '../components/DocumentInput'
import Field from '../components/Field'
import Modal from '../components/Modal'
import { EditIcon, MoreIcon, TrashIcon } from '../components/icons'
import PrioritySelect from '../components/PrioritySelect'
import StatusBadge from '../components/StatusBadge'
import TaskForm from '../components/TaskForm'
import TaskPrepInfo from '../components/TaskPrepInfo'
import { useToast } from '../components/Toast'
import { categoryIcon } from '../lib/categoryIcon'
import {
  COST_TYPE_OPTIONS,
  ISSUE_SEVERITY_OPTIONS,
  costTypeLabel,
  docTypeLabel,
  documentWhere,
  emptyToNull,
  equipmentCategories,
  errorMessage,
  formatAmount,
  formatDate,
  formatRecurrence,
  issueSeverityBadge,
  issueSeverityLabel,
  issueStatusLabel,
  optionalId,
  storageModeLabel,
  structureCategories,
  timelineEventLabel,
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
  const [activeTab, setActiveTab] = useState<'entretiens' | 'chronologie' | 'details' | 'documents'>('entretiens')

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
        <div className="page__actions">
          <button
            type="button"
            className="btn btn--edit"
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? (
              'Fermer'
            ) : (
              <>
                <EditIcon /> Modifier
              </>
            )}
          </button>
          <AssetActionsMenu
            asset={asset}
            documentCount={documents.length}
            onChanged={(next) => setAsset(next)}
            onDeleted={() => navigate(basePath, { replace: true })}
            onError={setError}
          />
        </div>
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
          aria-selected={activeTab === 'chronologie'}
          className={`tabs__tab${activeTab === 'chronologie' ? ' tabs__tab--active' : ''}`}
          onClick={() => setActiveTab('chronologie')}
        >
          Chronologie
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

          <AssetIssuesCard assetId={asset.id} onError={setError} />

          <AssetCostsCard
            assetId={asset.id}
            purchaseDate={asset.purchase_date}
            onError={setError}
          />
        </>
      )}

      {activeTab === 'chronologie' && <AssetTimeline assetId={asset.id} onError={setError} />}

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

/** Les deux sorties d'une fiche, dans le menu de l'en-tete.
 *
 *  Elles ont d'abord vecu dans une carte au bas de l'onglet « Details », loin
 *  du regard pour qu'on ne les clique pas par accident. Trop loin : le premier
 *  utilisateur a chercher comment supprimer une fiche ne l'a pas trouvee, et la
 *  carte avait encore recule quand les problemes et les couts sont passes
 *  au-dessus. Une action qu'on cherche est une action mal placee.
 *
 *  Elles remontent donc a cote de « Modifier », sans devenir cliquables par
 *  megarde : le menu demande une premiere intention, et `schema.sql` decide de
 *  la suite — un equipement retire passe en `status = 'removed'` et garde son
 *  historique, qui fait partie de l'histoire de la maison. Le retrait est donc
 *  immediat, parce qu'il se defait ; la suppression passe par une boite qui
 *  annonce ce qui va disparaitre, parce qu'elle ne se defait pas. */
function AssetActionsMenu({
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
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const conteneur = useRef<HTMLDivElement>(null)
  const { showToast } = useToast()
  const isRemoved = asset.status === 'removed'
  const noun = asset.kind === 'building_element' ? 'cet élément' : 'cet appareil'

  useEffect(() => {
    if (!open) return
    function auClic(event: MouseEvent) {
      if (!conteneur.current?.contains(event.target as Node)) setOpen(false)
    }
    function auClavier(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', auClic)
    document.addEventListener('keydown', auClavier)
    return () => {
      document.removeEventListener('mousedown', auClic)
      document.removeEventListener('keydown', auClavier)
    }
  }, [open])

  async function setStatus(status: AssetLifecycleStatus, message: string) {
    setBusy(true)
    setOpen(false)
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
    <div className="menu" ref={conteneur}>
      <button
        type="button"
        className={open ? 'btn btn--active' : 'btn'}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Autres actions"
        onClick={() => setOpen((current) => !current)}
      >
        <MoreIcon />
      </button>

      {open && (
        <div className="menu__panel" role="menu">
          {isRemoved ? (
            <button
              type="button"
              role="menuitem"
              className="menu__item"
              onClick={() => void setStatus('active', 'Remis en service')}
            >
              Remettre en service
              <span className="menu__hint">Ses entretiens reviennent au planning.</span>
            </button>
          ) : (
            <button
              type="button"
              role="menuitem"
              className="menu__item"
              onClick={() => void setStatus('removed', 'Retiré de la maison')}
            >
              Retirer de la maison
              <span className="menu__hint">
                Vendu, remplacé, déposé. L'historique reste, et ça se défait.
              </span>
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className="menu__item menu__item--danger"
            onClick={() => {
              setOpen(false)
              setConfirming(true)
            }}
          >
            <span className="menu__label">
              <TrashIcon /> Supprimer définitivement
            </span>
            <span className="menu__hint">Doublon, fiche créée par erreur. Sans retour.</span>
          </button>
        </div>
      )}

      {confirming && (
        <Modal title={`Supprimer « ${asset.name} » ?`} onClose={() => setConfirming(false)}>
          <p>
            La suppression emporte la fiche de {noun}, {countList(asset.tasks.length, documentCount)}
            , ses coûts et ses fichiers. <strong>Elle ne peut pas être annulée.</strong>
          </p>
          <p className="muted">
            Si l'appareil a seulement quitté la maison, fermez cette boîte et choisissez plutôt
            « Retirer de la maison » : son historique fait partie de celui de la maison.
          </p>
          <div className="complete__actions">
            <button
              type="button"
              className="btn btn--delete"
              disabled={busy}
              onClick={() => void remove()}
            >
              <TrashIcon /> Oui, tout supprimer
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Annuler
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

/** « 3 entretiens et leur historique, 2 documents », sans les zeros qui
 *  n'apprennent rien. La virgule, et non « et » : « et leur historique et 2
 *  documents » s'entend a la lecture. */
function countList(tasks: number, documents: number): string {
  const parts: string[] = []
  if (tasks > 0) parts.push(`${tasks} entretien${tasks > 1 ? 's' : ''} et leur historique`)
  if (documents > 0) parts.push(`${documents} document${documents > 1 ? 's' : ''}`)
  if (parts.length === 0) return 'tout ce qui y est rattaché'
  return parts.join(', ')
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

/** Les problemes constates sur l'appareil.
 *
 *  La table `issue` existe dans schema.sql depuis l'origine, avec sa place dans
 *  `v_asset_timeline` — et rien ne l'ecrivait. Un probleme n'est pas une
 *  intervention : l'intervention est une action datee, le probleme dure. « La
 *  VMC fait du bruit » commence un jour, appelle peut-etre trois passages, et se
 *  resout un autre jour. C'est cette duree que la fiche ne savait pas porter. */
function AssetIssuesCard({
  assetId,
  onError,
}: {
  assetId: number
  onError: (message: string | null) => void
}) {
  const [issues, setIssues] = useState<Issue[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<IssueSeverity>('normal')
  const { showToast } = useToast()

  useEffect(() => {
    let cancelled = false
    api
      .assetIssues(assetId)
      .then((rows) => {
        if (!cancelled) setIssues(rows)
      })
      .catch((caught: unknown) => {
        if (!cancelled) onError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [assetId, onError])

  async function reload() {
    setIssues(await api.assetIssues(assetId))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    setBusy(true)
    onError(null)
    try {
      await api.createIssue(assetId, {
        title: title.trim(),
        description: description.trim() || null,
        severity,
      })
      setTitle('')
      setDescription('')
      setSeverity('normal')
      setAdding(false)
      await reload()
      showToast('Problème signalé')
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function change(issue: Issue, body: IssuePatch, message: string) {
    setBusy(true)
    onError(null)
    try {
      await api.patchIssue(issue.id, body)
      await reload()
      showToast(message)
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  async function remove(issue: Issue) {
    setBusy(true)
    onError(null)
    try {
      await api.deleteIssue(issue.id)
      await reload()
      showToast('Problème supprimé')
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  if (issues === null) return null
  const ouverts = issues.filter((issue) => issue.status !== 'resolved').length

  return (
    <div className="card">
      <h2 className="card__title">
        Problèmes
        {ouverts > 0 && (
          <span className="badge badge--overdue">
            {ouverts} en cours
          </span>
        )}
      </h2>

      {issues.length === 0 ? (
        <p className="muted">
          Rien à signaler. Un bruit, une fuite, une panne : notez-le ici pour en garder la date,
          même si vous ne vous en occupez pas tout de suite.
        </p>
      ) : (
        <ul className="issue-list">
          {issues.map((issue) => (
            <li
              key={issue.id}
              className={`issue${issue.status === 'resolved' ? ' issue--resolved' : ''}`}
            >
              <div className="issue__head">
                <strong>{issue.title}</strong>
                <span className={`badge badge--${issueSeverityBadge(issue.severity)}`}>
                  {issueSeverityLabel(issue.severity)}
                </span>
                <span className="muted">
                  {issueStatusLabel(issue.status)} · ouvert le {formatDate(issue.opened_on)}
                  {issue.resolved_on ? ` · résolu le ${formatDate(issue.resolved_on)}` : ''}
                </span>
              </div>
              {issue.description && <p className="muted">{issue.description}</p>}
              {issue.result && <p className="muted">Résultat : {issue.result}</p>}
              <div className="complete__actions">
                {issue.status === 'open' && (
                  <button
                    type="button"
                    className="btn btn--small"
                    disabled={busy}
                    onClick={() => void change(issue, { status: 'in_progress' }, 'Pris en charge')}
                  >
                    Je m'en occupe
                  </button>
                )}
                {issue.status !== 'resolved' ? (
                  <button
                    type="button"
                    className="btn btn--small btn--primary"
                    disabled={busy}
                    onClick={() => void change(issue, { status: 'resolved' }, 'Problème résolu')}
                  >
                    Marquer résolu
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn--small"
                    disabled={busy}
                    onClick={() => void change(issue, { status: 'open' }, 'Problème rouvert')}
                  >
                    Rouvrir
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn--small btn--delete"
                  disabled={busy}
                  onClick={() => void remove(issue)}
                  aria-label={`Supprimer « ${issue.title} »`}
                >
                  <TrashIcon />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {adding ? (
        <form className="form" onSubmit={submit}>
          <Field label="Ce qui ne va pas">
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="La VMC fait beaucoup de bruit"
              required
            />
          </Field>
          <Field label="Détails" hint="Facultatif : depuis quand, dans quelles conditions.">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
            />
          </Field>
          <Field label="Gravité">
            <select
              value={severity}
              onChange={(event) => setSeverity(event.target.value as IssueSeverity)}
            >
              {ISSUE_SEVERITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="complete__actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              Signaler
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setAdding(false)}>
              Annuler
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn btn--small" onClick={() => setAdding(true)}>
          Signaler un problème
        </button>
      )}
    </div>
  )
}

/** L'histoire de l'appareil, telle que la base la raconte.
 *
 *  `v_asset_timeline` existait depuis l'origine et n'etait interrogee nulle
 *  part. Elle reunit la pose, les interventions, les problemes ouverts et
 *  resolus, les depenses autonomes et la fin de garantie — six tables qui, sans
 *  elle, ne se lisaient que separement. L'ordre vient du SQL et non d'ici : deux
 *  appelants ne peuvent donc pas raconter deux histoires differentes (ADR-0003). */
function AssetTimeline({
  assetId,
  onError,
}: {
  assetId: number
  onError: (message: string | null) => void
}) {
  const [entries, setEntries] = useState<TimelineEntry[] | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .assetTimeline(assetId)
      .then((rows) => {
        if (!cancelled) setEntries(rows)
      })
      .catch((caught: unknown) => {
        if (!cancelled) onError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [assetId, onError])

  if (entries === null) return <p className="muted">Chargement...</p>

  if (entries.length === 0) {
    return (
      <div className="card">
        <p className="muted">
          Rien à raconter pour l'instant. La date d'installation, les entretiens réalisés, les
          problèmes et les dépenses viendront s'inscrire ici au fur et à mesure.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <ol className="timeline">
        {entries.map((entry) => (
          <li
            key={`${entry.source_table}-${entry.source_id}-${entry.event_type}`}
            className={`timeline__item timeline__item--${entry.event_type}`}
          >
            <span className="timeline__date">{formatDate(entry.occurred_on)}</span>
            <span className="timeline__body">
              <strong>{timelineEventLabel(entry.event_type)}</strong>
              {entry.title && entry.title !== timelineEventLabel(entry.event_type) && (
                <> · {entry.title}</>
              )}
              {entry.amount_cents !== null && <> · {formatAmount(entry.amount_cents, 'EUR')}</>}
              {entry.detail && <span className="muted"> — {entry.detail}</span>}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
