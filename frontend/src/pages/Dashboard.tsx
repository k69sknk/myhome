import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { HaSummary, HealthResponse } from '../api/types'
import StatusBadge from '../components/StatusBadge'
import { errorMessage, formatDate } from '../lib/format'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; summary: HaSummary; health: HealthResponse }
  | { kind: 'error'; message: string }

export default function Dashboard() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false

    Promise.all([api.summary(), api.health()])
      .then(([summary, health]) => {
        if (!cancelled) setState({ kind: 'ready', summary, health })
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ kind: 'error', message: errorMessage(error) })
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="page">
      <h1 className="page__title">Tableau de bord</h1>
      <p className="page__lead">Ce qu'il faut faire dans la maison, au meme endroit.</p>

      {state.kind === 'loading' && <p className="muted">Chargement...</p>}
      {state.kind === 'error' && (
        <p className="status status--error">API injoignable : {state.message}</p>
      )}
      {state.kind === 'ready' && <Ready summary={state.summary} health={state.health} />}
    </section>
  )
}

function Ready({ summary, health }: { summary: HaSummary; health: HealthResponse }) {
  const { counts, next_task: nextTask } = summary
  const hasTasks =
    counts.overdue + counts.due_soon + counts.ok + counts.unscheduled > 0

  return (
    <>
      <div className="counts">
        <CountCard
          to="/entretiens"
          label="En retard"
          value={counts.overdue}
          tone="overdue"
        />
        <CountCard
          to="/entretiens"
          label="Bientot"
          value={counts.due_soon}
          tone="due_soon"
        />
        <CountCard to="/entretiens" label="A jour" value={counts.ok} tone="ok" />
        <CountCard
          to="/entretiens"
          label="Non planifies"
          value={counts.unscheduled}
          tone="unscheduled"
        />
      </div>

      <div className="card">
        <h2 className="card__title">Prochain entretien</h2>
        {nextTask === null ? (
          <p className="muted">
            {hasTasks
              ? 'Aucun entretien date pour le moment.'
              : 'Ajoutez un equipement, puis un entretien, pour voir les echeances ici.'}
          </p>
        ) : (
          <p>
            <Link
              to={nextTask.asset_id ? `/equipements/${nextTask.asset_id}` : '/entretiens'}
            >
              {nextTask.name}
            </Link>
            {nextTask.asset_name ? ` — ${nextTask.asset_name}` : ''}
            {' · '}
            {formatDate(nextTask.due_date)}
            {nextTask.days_until < 0
              ? ` (${Math.abs(nextTask.days_until)} j de retard)`
              : nextTask.days_until === 0
                ? " (aujourd'hui)"
                : ` (dans ${nextTask.days_until} j)`}
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="card__title">Equipements</h2>
        {summary.assets.length === 0 ? (
          <p className="muted">
            Aucun appareil pour l'instant.{' '}
            <Link to="/equipements/nouveau">Ajouter un equipement</Link>
          </p>
        ) : (
          <ul className="rows">
            {summary.assets.map((asset) => (
              <li key={asset.id}>
                <Link className="rows__link" to={`/equipements/${asset.id}`}>
                  <span>{asset.name}</span>
                  <StatusBadge status={asset.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {summary.warranties_expiring.length > 0 && (
        <div className="card">
          <h2 className="card__title">Garanties qui expirent sous 30 jours</h2>
          <ul className="rows">
            {summary.warranties_expiring.map((warranty) => (
              <li key={warranty.asset_id}>
                <Link className="rows__link" to={`/equipements/${warranty.asset_id}`}>
                  <span>{warranty.asset_name}</span>
                  <span className="muted">{formatDate(warranty.end_date)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="muted page__meta">
        HomeKeeper {health.version} · contrat HA v{health.api_schema_version}
      </p>
    </>
  )
}

function CountCard({
  to,
  label,
  value,
  tone,
}: {
  to: string
  label: string
  value: number
  tone: 'overdue' | 'due_soon' | 'ok' | 'unscheduled'
}) {
  return (
    <Link to={to} className={`count count--${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </Link>
  )
}
