import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import type { Category, HaDevice, Location } from '../api/types'
import CategorySelect from '../components/CategorySelect'
import Field from '../components/Field'
import { emptyToNull, equipmentCategories, errorMessage, optionalId } from '../lib/format'

export default function AssetNew() {
  const navigate = useNavigate()
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [devices, setDevices] = useState<HaDevice[] | null>(null)
  const [haUnavailable, setHaUnavailable] = useState(false)

  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [locationId, setLocationId] = useState('')
  const [installDate, setInstallDate] = useState('')
  const [brand, setBrand] = useState('')
  const [model, setModel] = useState('')
  const [serial, setSerial] = useState('')
  const [notes, setNotes] = useState('')
  const [warrantyStart, setWarrantyStart] = useState('')
  const [warrantyMonths, setWarrantyMonths] = useState('')
  const [haDeviceId, setHaDeviceId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.categories(), api.locations()])
      .then(([nextCategories, nextLocations]) => {
        if (cancelled) return
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
          setDevices([])
        } else {
          setError(errorMessage(caught))
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  function applyDevice(deviceId: string) {
    setHaDeviceId(deviceId)
    const device = devices?.find((row) => row.ha_device_id === deviceId)
    if (!device) return
    setName((current) => current || device.name)
    setBrand((current) => current || device.manufacturer || '')
    setModel((current) => current || device.model || '')
    if (device.area_name && !locationId) {
      const match = locations.find(
        (location) => location.name.toLowerCase() === device.area_name?.toLowerCase(),
      )
      if (match) setLocationId(String(match.id))
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const selected = devices?.find((row) => row.ha_device_id === haDeviceId)
    try {
      const created = await api.createAsset({
        name: name.trim(),
        category_id: optionalId(categoryId),
        location_id: optionalId(locationId),
        brand: emptyToNull(brand),
        model: emptyToNull(model),
        serial_number: emptyToNull(serial),
        install_date: emptyToNull(installDate),
        notes: emptyToNull(notes),
        warranty: warrantyStart
          ? {
              start_date: warrantyStart,
              duration_months: warrantyMonths ? Number(warrantyMonths) : null,
            }
          : null,
      })
      if (selected) {
        try {
          await api.putHaLink(created.id, {
            ha_device_id: selected.ha_device_id,
            name_at_link: selected.name,
            entity_id_at_link: selected.entity_id,
            domain_at_link: selected.domain,
            area_name: optionalId(locationId) ? null : selected.area_name,
          })
        } catch {
          /* La fiche existe : le lien se retente depuis le detail. */
        }
      }
      navigate(`/equipements/${created.id}`)
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const selectedDevice = devices?.find((row) => row.ha_device_id === haDeviceId)
  const proposedArea =
    selectedDevice?.area_name &&
    !locationId &&
    !locations.some(
      (location) => location.name.toLowerCase() === selectedDevice.area_name?.toLowerCase(),
    )
      ? selectedDevice.area_name
      : null

  return (
    <section className="page">
      <p className="page__crumb">
        <Link to="/equipements">Equipements</Link>
      </p>
      <h1 className="page__title">Nouvel equipement</h1>
      <p className="page__lead">
        Une fiche par appareil. Le lien Home Assistant est facultatif : il pre-remplit le nom et
        peut proposer un lieu.
      </p>

      {error && <p className="status status--error">{error}</p>}

      <form className="card form" onSubmit={(event) => void submit(event)}>
        {!haUnavailable && devices && devices.length > 0 && (
          <Field label="Appareil Home Assistant (facultatif)">
            <select value={haDeviceId} onChange={(event) => applyDevice(event.target.value)}>
              <option value="">Ne pas lier</option>
              {devices.map((device) => (
                <option key={device.ha_device_id} value={device.ha_device_id}>
                  {device.name}
                  {device.area_name ? ` (${device.area_name})` : ''}
                </option>
              ))}
            </select>
          </Field>
        )}
        {haUnavailable && (
          <p className="muted">
            Liaison Home Assistant indisponible ici (hors add-on). Vous pourrez lier l'appareil
            depuis la fiche une fois installe.
          </p>
        )}
        {proposedArea && (
          <p className="notice">
            Le lieu « {proposedArea} » n'existe pas encore : il sera cree au rattachement.
          </p>
        )}

        <Field label="Nom">
          <input required value={name} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label="Categorie">
          <CategorySelect categories={categories} value={categoryId} onChange={setCategoryId} />
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
        <Field label="Debut de garantie (facultatif)">
          <input
            type="date"
            value={warrantyStart}
            onChange={(event) => setWarrantyStart(event.target.value)}
          />
        </Field>
        <Field label="Duree de garantie (mois)">
          <input
            type="number"
            min={1}
            value={warrantyMonths}
            onChange={(event) => setWarrantyMonths(event.target.value)}
          />
        </Field>
        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Creer la fiche
          </button>
          <Link to="/equipements" className="btn">
            Annuler
          </Link>
        </div>
      </form>
    </section>
  )
}
