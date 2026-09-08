/**
 * Types du contrat de l'API.
 *
 * Les noms de champs sont en `snake_case`, comme le JSON produit par le backend.
 * L'integration Home Assistant consomme le meme contrat en Python : convertir en
 * `camelCase` cote frontend imposerait une couche de transformation, et surtout
 * ferait diverger deux descriptions d'un meme contrat.
 *
 * `HaSummary` decrit `/api/ha/summary`, unique point de couplage entre l'add-on
 * et l'integration (docs/ARCHITECTURE.md section 5.3). Il est declare ici parce
 * que le tableau de bord affiche exactement les memes compteurs que les capteurs
 * Home Assistant : les deux doivent lire la meme source pour ne pas diverger.
 */

export interface HealthResponse {
  status: 'ok'
  app: string
  version: string
  api_schema_version: number
}

/** Statut derive d'une tache, calcule par le backend (vue SQL `v_task_status`). */
export type TaskStatus = 'ok' | 'due_soon' | 'overdue' | 'unscheduled'

export interface NextTask {
  id: number
  name: string
  asset_name: string | null
  due_date: string
  days_until: number
}

export interface AssetStatus {
  id: number
  name: string
  status: TaskStatus
}

export interface ExpiringWarranty {
  asset_id: number
  asset_name: string
  end_date: string
}

export interface HaSummary {
  generated_at: string
  counts: Record<TaskStatus, number>
  next_task: NextTask | null
  assets: AssetStatus[]
  warranties_expiring: ExpiringWarranty[]
}
