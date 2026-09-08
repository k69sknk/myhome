import type { Category, RecurrenceType, Task, TaskStatus } from '../api/types'

const MONTHS = [
  'janvier',
  'fevrier',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'aout',
  'septembre',
  'octobre',
  'novembre',
  'decembre',
] as const

export function todayIso(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [year, month, day] = iso.split('-')
  if (!year || !month || !day) return iso
  return `${day}/${month}/${year}`
}

export function monthName(month: number): string {
  return MONTHS[month - 1] ?? String(month)
}

export function statusLabel(status: TaskStatus): string {
  switch (status) {
    case 'overdue':
      return 'En retard'
    case 'due_soon':
      return 'Bientot'
    case 'ok':
      return 'A jour'
    case 'unscheduled':
      return 'Non planifie'
  }
}

export function formatRecurrence(task: Pick<Task, 'recurrence_type' | 'recurrence_interval' | 'fixed_month' | 'fixed_day'>): string {
  const type = task.recurrence_type as RecurrenceType | string
  if (type === 'none') return 'Ponctuel'
  if (type === 'months') {
    const interval = task.recurrence_interval ?? 1
    return interval === 1 ? 'Tous les mois' : `Tous les ${interval} mois`
  }
  if (type === 'years') {
    const interval = task.recurrence_interval ?? 1
    return interval === 1 ? 'Tous les ans' : `Tous les ${interval} ans`
  }
  if (type === 'annual_fixed') {
    const day = task.fixed_day ?? 1
    const month = monthName(task.fixed_month ?? 1)
    return `Chaque annee le ${day} ${month}`
  }
  if (type === 'days') {
    const interval = task.recurrence_interval ?? 1
    return interval === 1 ? 'Tous les jours' : `Tous les ${interval} jours`
  }
  return type
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Erreur inattendue'
}

/** Categories d'appareils seulement : le batiment reste hors UI (fiche construction plus tard). */
export function equipmentCategories(all: Category[]): Category[] {
  const structure = all.find((row) => row.slug === 'structure')
  if (structure === undefined) return all
  const hidden = new Set<number>([structure.id])
  for (const row of all) {
    if (row.parent_id !== null && hidden.has(row.parent_id)) hidden.add(row.id)
  }
  return all.filter((row) => !hidden.has(row.id))
}

export function emptyToNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

export function optionalId(value: string): number | null {
  if (value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}
