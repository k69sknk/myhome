import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { AssetListItem } from '../api/types'
import StatusBadge from '../components/StatusBadge'
import { errorMessage, formatDate } from '../lib/format'

export default function Assets() {
  const [assets, setAssets] = useState<AssetListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .assets()
      .then((rows) => {
        if (!cancelled) setAssets(rows)
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
          <h1 className="page__title">Equipements</h1>
          <p className="page__lead">PAC, VMC, electromenager, tableau electrique...</p>
        </div>
        <Link to="/equipements/nouveau" className="btn btn--primary">
          Ajouter
        </Link>
      </div>

      {error && <p className="status status--error">{error}</p>}
      {assets === null && !error && <p className="muted">Chargement...</p>}
      {assets && assets.length === 0 && (
        <p className="muted">
          Aucun appareil. <Link to="/equipements/nouveau">Creer la premiere fiche</Link>.
        </p>
      )}
      {assets && assets.length > 0 && (
        <ul className="rows rows--card">
          {assets.map((asset) => (
            <li key={asset.id}>
              <Link className="rows__link" to={`/equipements/${asset.id}`}>
                <span>
                  <strong>{asset.name}</strong>
                  <span className="muted">
                    {[asset.category_name, asset.location_path, formatDate(asset.install_date)]
                      .filter((part) => part && part !== '—')
                      .join(' · ')}
                  </span>
                </span>
                <StatusBadge status={asset.task_status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
