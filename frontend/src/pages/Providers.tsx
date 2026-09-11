import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { HistoryEntry, Provider, ProviderIn, Task, Trade } from '../api/types'
import Field from '../components/Field'
import StatusBadge from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import { EditIcon, TrashIcon } from '../components/icons'
import { errorMessage, formatAmount, formatDate } from '../lib/format'

const EMPTY: ProviderIn = {
  name: '',
  specialty: null,
  phone: null,
  email: null,
  website: null,
  address: null,
  customer_ref: null,
  notes: null,
}

function tradeLabel(trades: Trade[], slug: string | null): string | null {
  if (!slug) return null
  // Un metier retire du fichier laisse son slug : mieux vaut l'afficher brut que
  // perdre l'information (meme principe que les cles de catalogue, ADR-0008).
  return trades.find((trade) => trade.slug === slug)?.label ?? slug
}

/** Lien « tel: » ou « mailto: » : appeler est l'usage numero un d'une fiche. */
function ContactLink({ href, children }: { href: string; children: string }) {
  return <a href={href}>{children}</a>
}

export default function Providers() {
  const [providers, setProviders] = useState<Provider[] | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<ProviderIn>(EMPTY)
  const [detailed, setDetailed] = useState(false)
  const { showToast } = useToast()

  async function reload() {
    const [providerList, taskList] = await Promise.all([api.providers(), api.tasks()])
    setProviders(providerList)
    setTasks(taskList)
  }

  useEffect(() => {
    let cancelled = false
    reload().catch((caught: unknown) => {
      if (!cancelled) setError(errorMessage(caught))
    })
    api
      .trades()
      .then((rows) => {
        if (!cancelled) setTrades(rows)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  async function add(event: FormEvent) {
    event.preventDefault()
    const name = form.name.trim()
    if (!name) return
    setError(null)
    try {
      await api.createProvider({ ...form, name })
      setForm(EMPTY)
      setDetailed(false)
      showToast('Prestataire ajouté')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  async function remove(id: number) {
    setError(null)
    try {
      await api.deleteProvider(id)
      showToast('Prestataire supprimé')
      await reload()
    } catch (caught: unknown) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Prestataires</h1>
      <p className="page__lead">Les entreprises et artisans qui interviennent chez vous.</p>

      {error && <p className="status status--error">{error}</p>}

      <div className="card">
        <h2 className="card__title">Ajouter un prestataire</h2>
        <form className="form form--inline" onSubmit={(event) => void add(event)}>
          <Field label="Nom">
            <input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="Dupont Chauffage..."
            />
          </Field>
          <Field label="Metier">
            <select
              value={form.specialty ?? ''}
              onChange={(event) => setForm({ ...form, specialty: event.target.value || null })}
            >
              <option value="">Non precise</option>
              {trades.map((trade) => (
                <option key={trade.slug} value={trade.slug}>
                  {trade.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Telephone">
            <input
              value={form.phone ?? ''}
              onChange={(event) => setForm({ ...form, phone: event.target.value || null })}
              placeholder="04 72 00 00 00"
            />
          </Field>
          {/* Le reste est replie : on cree souvent une fiche avec un nom et un
              numero, au milieu d'autre chose. */}
          {detailed && (
            <>
              <Field label="Email">
                <input
                  value={form.email ?? ''}
                  onChange={(event) => setForm({ ...form, email: event.target.value || null })}
                />
              </Field>
              <Field label="Site / espace client">
                <input
                  value={form.website ?? ''}
                  onChange={(event) => setForm({ ...form, website: event.target.value || null })}
                  placeholder="https://..."
                />
              </Field>
              <Field label="Adresse">
                <input
                  value={form.address ?? ''}
                  onChange={(event) => setForm({ ...form, address: event.target.value || null })}
                />
              </Field>
              <Field label="N° client / contrat" hint="Ce qu'on vous reclame au telephone.">
                <input
                  value={form.customer_ref ?? ''}
                  onChange={(event) =>
                    setForm({ ...form, customer_ref: event.target.value || null })
                  }
                />
              </Field>
              <Field label="Notes">
                <textarea
                  rows={2}
                  value={form.notes ?? ''}
                  onChange={(event) => setForm({ ...form, notes: event.target.value || null })}
                  placeholder="Ne repond pas le lundi..."
                />
              </Field>
            </>
          )}
          {!detailed && (
            <button type="button" className="btn btn--small" onClick={() => setDetailed(true)}>
              Plus de details
            </button>
          )}
          <button type="submit" className="btn btn--primary">
            Ajouter
          </button>
        </form>
      </div>

      <div className="card">
        <h2 className="card__title">Annuaire</h2>
        {providers === null && !error && <p className="muted">Chargement...</p>}
        {providers && providers.length === 0 && (
          <p className="muted">
            Aucun prestataire. Ils se creent aussi a la volee en assignant un entretien ou en le
            marquant comme fait.
          </p>
        )}
        {providers && providers.length > 0 && (
          <ul className="tree">
            {providers.map((provider) => (
              <ProviderRow
                key={provider.id}
                provider={provider}
                trades={trades}
                tasks={tasks.filter((task) => task.assignee_provider_id === provider.id)}
                onError={setError}
                onChanged={() => void reload()}
                onDelete={() => void remove(provider.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function ProviderRow({
  provider,
  trades,
  tasks,
  onError,
  onChanged,
  onDelete,
}: {
  provider: Provider
  trades: Trade[]
  tasks: Task[]
  onError: (message: string | null) => void
  onChanged: () => void
  onDelete: () => void
}) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<ProviderIn>(provider)
  /** Ce que ce prestataire a realise. Charge a l'ouverture de la fiche : la
   *  plupart des lignes de l'annuaire ne seront pas depliees. */
  const [history, setHistory] = useState<HistoryEntry[] | null>(null)
  const { showToast } = useToast()

  const specialty = tradeLabel(trades, provider.specialty)
  const total = (history ?? []).reduce((sum, entry) => sum + (entry.cost?.amount_cents ?? 0), 0)
  const currency = history?.find((entry) => entry.cost)?.cost?.currency ?? 'EUR'

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next && history === null) {
      try {
        setHistory(await api.interventions({ limit: 20, offset: 0, providerId: provider.id }))
      } catch (caught: unknown) {
        onError(errorMessage(caught))
      }
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    onError(null)
    try {
      await api.patchProvider(provider.id, { ...form, name: form.name.trim() })
      setEditing(false)
      showToast('Prestataire modifié')
      onChanged()
    } catch (caught: unknown) {
      onError(errorMessage(caught))
    }
  }

  return (
    <li>
      <div className="tree__row">
        <strong>{provider.name}</strong>
        {specialty && <span className="muted">{specialty}</span>}
        {provider.phone && <ContactLink href={`tel:${provider.phone}`}>{provider.phone}</ContactLink>}
        <button type="button" className="btn btn--small" onClick={() => void toggle()}>
          {open ? 'Masquer' : 'Voir'}
        </button>
        <button
          type="button"
          className="btn btn--small btn--edit"
          onClick={() => setEditing((current) => !current)}
        >
          <EditIcon /> Modifier
        </button>
        <button type="button" className="btn btn--small btn--delete" onClick={onDelete}>
          <TrashIcon /> Supprimer
        </button>
      </div>

      {editing && (
        <form className="form form--inline" onSubmit={(event) => void save(event)}>
          <Field label="Nom">
            <input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
          <Field label="Metier">
            <select
              value={form.specialty ?? ''}
              onChange={(event) => setForm({ ...form, specialty: event.target.value || null })}
            >
              <option value="">Non precise</option>
              {trades.map((trade) => (
                <option key={trade.slug} value={trade.slug}>
                  {trade.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Telephone">
            <input
              value={form.phone ?? ''}
              onChange={(event) => setForm({ ...form, phone: event.target.value || null })}
            />
          </Field>
          <Field label="Email">
            <input
              value={form.email ?? ''}
              onChange={(event) => setForm({ ...form, email: event.target.value || null })}
            />
          </Field>
          <Field label="Site / espace client">
            <input
              value={form.website ?? ''}
              onChange={(event) => setForm({ ...form, website: event.target.value || null })}
            />
          </Field>
          <Field label="Adresse">
            <input
              value={form.address ?? ''}
              onChange={(event) => setForm({ ...form, address: event.target.value || null })}
            />
          </Field>
          <Field label="N° client / contrat">
            <input
              value={form.customer_ref ?? ''}
              onChange={(event) => setForm({ ...form, customer_ref: event.target.value || null })}
            />
          </Field>
          <Field label="Notes">
            <textarea
              rows={2}
              value={form.notes ?? ''}
              onChange={(event) => setForm({ ...form, notes: event.target.value || null })}
            />
          </Field>
          <button type="submit" className="btn btn--primary btn--small">
            OK
          </button>
        </form>
      )}

      {open && (
        <>
          <dl className="facts">
            {provider.email && (
              <>
                <dt>Email</dt>
                <dd>
                  <ContactLink href={`mailto:${provider.email}`}>{provider.email}</ContactLink>
                </dd>
              </>
            )}
            {provider.website && (
              <>
                <dt>Site</dt>
                <dd>
                  <a href={provider.website} target="_blank" rel="noreferrer">
                    {provider.website}
                  </a>
                </dd>
              </>
            )}
            {provider.address && (
              <>
                <dt>Adresse</dt>
                <dd>{provider.address}</dd>
              </>
            )}
            {provider.customer_ref && (
              <>
                <dt>N° client</dt>
                <dd>{provider.customer_ref}</dd>
              </>
            )}
            {provider.notes && (
              <>
                <dt>Notes</dt>
                <dd className="muted">{provider.notes}</dd>
              </>
            )}
          </dl>

          {tasks.length > 0 && (
            <>
              <h3 className="card__subtitle">Entretiens qui lui sont confies</h3>
              <ul className="rows">
                {tasks.map((task) => (
                  <li key={task.id}>
                    <div className="rows__link">
                      <span>
                        {task.asset_id ? (
                          <Link to={`/equipements/${task.asset_id}`}>{task.name}</Link>
                        ) : (
                          task.name
                        )}
                        <span className="muted">
                          {task.asset_name}
                          {' · prochain '}
                          {formatDate(task.next_due_on)}
                        </span>
                      </span>
                      <StatusBadge status={task.status} />
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h3 className="card__subtitle">
            Interventions realisees
            {total > 0 && <span className="muted"> · {formatAmount(total, currency)} en tout</span>}
          </h3>
          {history === null && <p className="muted">Chargement...</p>}
          {history !== null && history.length === 0 && (
            <p className="muted">
              Rien a son nom pour l'instant. L'historique se remplit quand on choisit cette fiche
              en marquant un entretien comme fait.
            </p>
          )}
          {history !== null && history.length > 0 && (
            <ul className="rows">
              {history.map((entry) => (
                <li key={entry.id}>
                  <div className="rows__link">
                    <span>
                      <Link to={`/equipements/${entry.asset_id}`}>
                        {entry.task_name ?? entry.asset_name}
                      </Link>
                      <span className="muted">
                        {entry.task_name ? ` · ${entry.asset_name}` : ''}
                        {' · '}
                        {formatDate(entry.performed_on)}
                        {entry.cost
                          ? ` · ${formatAmount(entry.cost.amount_cents, entry.cost.currency)}`
                          : ''}
                      </span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </li>
  )
}
