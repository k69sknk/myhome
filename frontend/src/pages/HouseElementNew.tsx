import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Category, Location } from '../api/types'
import BackLink from '../components/BackLink'
import CategorySelect from '../components/CategorySelect'
import Field from '../components/Field'
import { useToast } from '../components/Toast'
import { categoryIcon } from '../lib/categoryIcon'
import { emptyToNull, errorMessage, structureCategories } from '../lib/format'

export default function HouseElementNew() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<Location[]>([])

  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [locationId, setLocationId] = useState('')
  const [installDate, setInstallDate] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.categories(), api.locations()])
      .then(([nextCategories, nextLocations]) => {
        if (cancelled) return
        setCategories(structureCategories(nextCategories))
        setLocations(nextLocations)
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.createAsset({
        name: name.trim(),
        kind: 'building_element',
        category_id: categoryId ? Number(categoryId) : null,
        location_id: locationId ? Number(locationId) : null,
        install_date: emptyToNull(installDate),
        notes: emptyToNull(notes),
      })
      showToast('Élément ajouté')
      navigate(`/elements/${created.id}`)
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page">
      <BackLink to="/elements" label="Éléments de la maison" />
      <h1 className="page__title">Nouvel élément</h1>
      <p className="page__lead">
        Une fiche par élément de la maison : joints, toiture, façade, volets, gouttières...
      </p>

      {error && <p className="status status--error">{error}</p>}

      <form className="card form" onSubmit={(event) => void submit(event)}>
        <Field label="Nom">
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Joints de douche..."
          />
        </Field>
        <Field label="Categorie">
          <div className="field__row">
            <span className="asset-avatar" aria-hidden="true">
              {categoryIcon(categories.find((row) => String(row.id) === categoryId)?.slug)}
            </span>
            <CategorySelect
              categories={categories}
              value={categoryId}
              onChange={setCategoryId}
              onCreated={(category) => setCategories((current) => [...current, category])}
            />
          </div>
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
        <Field label="Date de pose / installation" hint="Facultatif">
          <input
            type="date"
            value={installDate}
            onChange={(event) => setInstallDate(event.target.value)}
          />
        </Field>
        <Field label="Notes">
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
        </Field>
        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Creer la fiche
          </button>
          <Link to="/elements" className="btn">
            Annuler
          </Link>
        </div>
      </form>
    </section>
  )
}
