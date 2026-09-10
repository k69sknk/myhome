import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { Asset, Category, DocumentMeta, HaDevice, Location, Member } from '../api/types'
import BackLink from '../components/BackLink'
import CategorySelect from '../components/CategorySelect'
import CompleteTask from '../components/CompleteTask'
import Field from '../components/Field'
import { EditIcon, TrashIcon } from '../components/icons'
import PrioritySelect from '../components/PrioritySelect'
import StatusBadge from '../components/StatusBadge'
import TaskForm from '../components/TaskForm'
import TaskPrepInfo from '../components/TaskPrepInfo'
import { useToast } from '../components/Toast'
import { categoryIcon } from '../lib/categoryIcon'
import {
  docTypeLabel,
  emptyToNull,
  equipmentCategories,
  errorMessage,
  formatDate,
  formatRecurrence,
  optionalId,
  structureCategories,
  warrantyAlert,
  warrantyAlertLabel,
} from '../lib/format'

const DOCUMENT_ACCEPT = '.pdf,.jpg,.jpeg,.png,.heic,.doc,.docx'
const PHOTO_ACCEPT = '.jpg,.jpeg,.png,.heic'

function WarrantyBadge({ endDate }: { endDate: string | null | undefined }) {
  const level = warrantyAlert(endDate)
  if (level === null) return null
  return <span className={`badge badge--${level === 'expired' ? 'overdue' : 'due_soon'}`}>{warrantyAlertLabel(level)}</span>
}

export default function AssetDetail() {
  const { id } = useParams()
  const location = useLocation()
  const isElement = location.pathname.startsWith('/elements')
  const basePath = isElement ? '/elements' : '/equipements'
  const baseLabel = isElement ? 'Éléments de la maison' : 'Equipements'
  const assetId = Number(id)
  const [asset, setAsset] = useState<Asset | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [documents, setDocuments] = useState<DocumentMeta[]>([])
  const [devices, setDevices] = useState<HaDevice[]>([])
  const [members, setMembers] = useState<Member[]>([])
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
    ])
      .then(([nextAsset, nextCategories, nextLocations, nextDocuments, nextMembers]) => {
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
      })
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
                  <dt>Modele</dt>
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
      await api.uploadAssetDocument(asset.id, file, 'photo')
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
  const [docType, setDocType] = useState<'manual' | 'invoice' | 'other'>('manual')
  const [customName, setCustomName] = useState('')
  const [busy, setBusy] = useState(false)
  const { showToast } = useToast()

  async function upload(file: File) {
    setBusy(true)
    onError(null)
    try {
      await api.uploadAssetDocument(assetId, file, docType, customName.trim())
      setCustomName('')
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
      <p className="muted">Manuel d'utilisation, facture d'achat, ou tout autre document utile.</p>
      {documents.length === 0 ? (
        <p className="muted">Aucun document pour l'instant.</p>
      ) : (
        <ul className="task-list">
          {documents.map((document) => (
            <li key={document.id} className="task">
              <div className="task__main">
                <a href={api.documentFileUrl(document.id)} target="_blank" rel="noreferrer">
                  <strong>{document.name}</strong>
                </a>
                <p className="muted">{docTypeLabel(document.doc_type)}</p>
              </div>
              <button
                type="button"
                className="btn btn--small btn--delete"
                disabled={busy}
                onClick={() => void remove(document.id)}
              >
                <TrashIcon /> Supprimer
              </button>
            </li>
          ))}
        </ul>
      )}
      <h3 className="card__subtitle">Ajouter un document</h3>
      <div className="form form--inline">
        <select
          value={docType}
          onChange={(event) => {
            setDocType(event.target.value as 'manual' | 'invoice' | 'other')
            setCustomName('')
          }}
        >
          <option value="manual">Manuel d'utilisation</option>
          <option value="invoice">Facture d'achat</option>
          <option value="other">Autre</option>
        </select>
        {docType === 'other' && (
          <input
            type="text"
            value={customName}
            onChange={(event) => setCustomName(event.target.value)}
            placeholder="Nom du document"
          />
        )}
        <input
          type="file"
          accept={DOCUMENT_ACCEPT}
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) void upload(file)
          }}
        />
      </div>
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
      <Field label="Categorie">
        <CategorySelect
          categories={categories}
          value={categoryId}
          onChange={setCategoryId}
          onCreated={onCategoryCreated}
        />
      </Field>
      <Field label="Lieu">
        <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
          <option value="">Non range</option>
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
          <Field label="Modele">
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </Field>
          <Field label="Numero de serie">
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
