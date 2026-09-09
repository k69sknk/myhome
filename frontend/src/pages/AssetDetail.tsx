import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { Asset, Category, HaDevice, Location } from '../api/types'
import CategorySelect from '../components/CategorySelect'
import CompleteTask from '../components/CompleteTask'
import Field from '../components/Field'
import StatusBadge from '../components/StatusBadge'
import TaskForm from '../components/TaskForm'
import {
  emptyToNull,
  equipmentCategories,
  errorMessage,
  formatDate,
  formatRecurrence,
  optionalId,
} from '../lib/format'

export default function AssetDetail() {
  const { id } = useParams()
  const assetId = Number(id)
  const [asset, setAsset] = useState<Asset | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [devices, setDevices] = useState<HaDevice[]>([])
  const [haUnavailable, setHaUnavailable] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  async function reload() {
    const next = await api.asset(assetId)
    setAsset(next)
  }

  useEffect(() => {
    let cancelled = false
    if (!Number.isFinite(assetId)) {
      setError('Fiche introuvable')
      return
    }
    Promise.all([api.asset(assetId), api.categories(), api.locations()])
      .then(([nextAsset, nextCategories, nextLocations]) => {
        if (cancelled) return
        setAsset(nextAsset)
        setCategories(equipmentCategories(nextCategories))
        setLocations(nextLocations)
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
        <Link to="/equipements">Retour aux equipements</Link>
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

  return (
    <section className="page">
      <p className="page__crumb">
        <Link to="/equipements">Equipements</Link>
      </p>
      <div className="page__header">
        <div>
          <h1 className="page__title">{asset.name}</h1>
          <p className="page__lead">
            {[asset.category_name, asset.location_path, formatDate(asset.install_date)]
              .filter((part) => part && part !== '—')
              .join(' · ') || 'Fiche appareil'}
          </p>
        </div>
        <button type="button" className="btn" onClick={() => setEditing((value) => !value)}>
          {editing ? 'Fermer' : 'Modifier'}
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

      <div className="card">
        <h2 className="card__title">Entretiens</h2>
        {asset.tasks.length === 0 ? (
          <p className="muted">Aucun entretien sur cette fiche.</p>
        ) : (
          <ul className="task-list">
            {asset.tasks.map((task) => (
              <li key={task.id} className="task">
                <div className="task__main">
                  <strong>{task.name}</strong>
                  <StatusBadge status={task.status} />
                  <p className="muted">
                    {formatRecurrence(task)}
                    {' · dernier '}
                    {formatDate(task.last_completed_on)}
                    {' · prochain '}
                    {formatDate(task.next_due_on)}
                  </p>
                </div>
                <CompleteTask task={task} onCompleted={() => void reload().catch((caught) => setError(errorMessage(caught)))} />
              </li>
            ))}
          </ul>
        )}
        <h3 className="card__subtitle">Ajouter un entretien</h3>
        <TaskForm
          onCreate={async (body) => {
            await api.createTask(asset.id, body)
            await reload()
          }}
        />
      </div>

      <div className="card">
        <h2 className="card__title">Details</h2>
        <dl className="facts">
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
              : '—'}
          </dd>
          <dt>Notes</dt>
          <dd>{asset.notes || '—'}</dd>
        </dl>
      </div>

      <HaLinkCard
        asset={asset}
        devices={devices}
        haUnavailable={haUnavailable}
        onChanged={(next) => setAsset(next)}
        onError={setError}
      />
    </section>
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
      <Field label="Marque">
        <input value={brand} onChange={(event) => setBrand(event.target.value)} />
      </Field>
      <Field label="Modele">
        <input value={model} onChange={(event) => setModel(event.target.value)} />
      </Field>
      <Field label="Numero de serie">
        <input value={serial} onChange={(event) => setSerial(event.target.value)} />
      </Field>
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
