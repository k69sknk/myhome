import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { AssetListItem } from '../api/types'
import StatusBadge from '../components/StatusBadge'
import { categoryIcon } from '../lib/categoryIcon'
import { errorMessage, formatDate } from '../lib/format'

export default function HouseElements() {
  const [elements, setElements] = useState<AssetListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .assets('building_element')
      .then((rows) => {
        if (!cancelled) setElements(rows)
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(errorMessage(caught))
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="page">
      <div className="page__header">
        <div>
          <h1 className="page__title">Éléments de la maison</h1>
          <p className="page__lead">Joints, toiture, façade, volets... tout ce qui n'est pas un appareil.</p>
        </div>
        <Link to="/elements/nouveau" className="btn btn--primary">
          Ajouter
        </Link>
      </div>

      {error && <p className="status status--error">{error}</p>}
      {elements === null && !error && <p className="muted">Chargement...</p>}
      {elements && elements.length === 0 && (
        <p className="muted">
          Aucun élément. <Link to="/elements/nouveau">Creer la premiere fiche</Link>.
        </p>
      )}
      {elements && elements.length > 0 && (
        <ul className="rows rows--card">
          {elements.map((element) => (
            <li key={element.id}>
              <Link className="rows__link" to={`/elements/${element.id}`}>
                <div className="rows__main">
                  <span className="asset-avatar" aria-hidden="true">
                    {element.photo_document_id !== null ? (
                      <img src={api.documentFileUrl(element.photo_document_id)} alt="" />
                    ) : (
                      categoryIcon(element.category_slug)
                    )}
                  </span>
                  <span>
                    <strong>{element.name}</strong>
                    <span className="muted">
                      {[element.category_name, element.location_path, formatDate(element.install_date)]
                        .filter((part) => part && part !== '—')
                        .join(' · ')}
                    </span>
                  </span>
                </div>
                <div className="rows__badges">
                  <StatusBadge status={element.task_status} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
