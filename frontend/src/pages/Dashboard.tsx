import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { HealthResponse } from '../api/types'
import { resolveBasePath } from '../base-path'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; health: HealthResponse }
  | { kind: 'error'; message: string }

/**
 * Le tableau de bord definitif affichera les compteurs en retard / bientot / a
 * jour (cahier des charges section 19), lus sur `/api/ha/summary` pour rester
 * identiques aux capteurs Home Assistant.
 *
 * Pour l'instant, il verifie que la chaine complete fonctionne : resolution du
 * prefixe d'ingress, appel a l'API, reponse du backend.
 */
export default function Dashboard() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false

    api
      .health()
      .then((health) => {
        if (!cancelled) setState({ kind: 'ready', health })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ kind: 'error', message: error instanceof Error ? error.message : 'Erreur' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="page">
      <h1 className="page__title">Tableau de bord</h1>
      <p className="page__lead">
        Toute l'histoire de la maison, retrouvable au meme endroit.
      </p>

      <div className="card">
        <h2 className="card__title">Etat de l'application</h2>
        {state.kind === 'loading' && <p className="muted">Connexion a l'API...</p>}
        {state.kind === 'error' && (
          <p className="status status--error">API injoignable : {state.message}</p>
        )}
        {state.kind === 'ready' && (
          <dl className="facts">
            <dt>API</dt>
            <dd className="status status--ok">operationnelle</dd>
            <dt>Version</dt>
            <dd>{state.health.version}</dd>
            <dt>Contrat Home Assistant</dt>
            <dd>v{state.health.api_schema_version}</dd>
            <dt>Chemin de base</dt>
            <dd>
              <code>{resolveBasePath()}</code>
            </dd>
          </dl>
        )}
      </div>

      <div className="notice">
        <strong>Squelette d'architecture.</strong>
        <p>
          L'architecture et le modele de donnees sont documentes et valides avant tout
          developpement metier, comme demande par le cahier des charges. Les compteurs
          d'entretiens en retard et a venir arriveront avec la V1.
        </p>
      </div>
    </section>
  )
}
