/**
 * Types du contrat de l'API.
 *
 * Les noms de champs sont en `snake_case`, comme le JSON produit par le backend.
 * L'integration Home Assistant consomme le meme contrat en Python : convertir en
 * `camelCase` cote frontend imposerait une couche de transformation, et surtout
 * ferait diverger deux descriptions d'un meme contrat.
 *
 * `HaSummary` decrit `/api/ha/summary`, unique point de couplage entre l'add-on
 * et l'integration (docs/ARCHITECTURE.md section 5.3). Le tableau de bord affiche
 * exactement les memes compteurs que les capteurs Home Assistant.
 */

export interface HealthResponse {
  status: 'ok'
  app: string
  version: string
  api_schema_version: number
}

/** Statut derive d'une tache, calcule par le backend (vue SQL `v_task_status`). */
export type TaskStatus = 'ok' | 'due_soon' | 'overdue' | 'unscheduled'

export type RecurrenceType =
  | 'none'
  | 'days'
  | 'months'
  | 'years'
  | 'annual_fixed'
  | 'custom_date'

export interface LocationType {
  id: number
  slug: string
  name: string
  is_builtin: boolean
  sort_order: number
}

export interface LocationTypeIn {
  name: string
}

export interface NextTask {
  id: number
  name: string
  asset_name: string | null
  asset_id: number | null
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
  api_schema_version: number
  generated_at: string
  counts: Record<TaskStatus, number>
  next_task: NextTask | null
  assets: AssetStatus[]
  warranties_expiring: ExpiringWarranty[]
}

export interface Home {
  id: number
  name: string
  address: string | null
  currency: string
  due_soon_threshold_days: number
}

export interface Location {
  id: number
  name: string
  parent_id: number | null
  location_type_id: number
  location_type_name: string
  sort_order: number
  notes: string | null
  path: string
  asset_count: number
}

export interface LocationIn {
  name: string
  parent_id?: number | null
  location_type_id?: number | null
  sort_order?: number
  notes?: string | null
}

export interface Category {
  id: number
  parent_id: number | null
  name: string
  slug: string
  icon: string | null
  is_builtin: boolean
  sort_order: number
}

export interface CategoryIn {
  name: string
}

export interface Warranty {
  start_date: string
  duration_months: number | null
  end_date: string | null
  provider: string | null
  terms_url: string | null
  notes: string | null
}

export interface WarrantyIn {
  start_date: string
  duration_months?: number | null
  provider?: string | null
  notes?: string | null
}

export interface HaLink {
  ha_device_id: string | null
  name_at_link: string
  entity_id_at_link: string | null
  resolution_status: string
}

export interface HaLinkIn {
  ha_device_id: string
  name_at_link: string
  entity_id_at_link?: string | null
  domain_at_link?: string | null
  area_name?: string | null
}

export interface HaDevice {
  ha_device_id: string
  name: string
  manufacturer: string | null
  model: string | null
  area_name: string | null
  entity_id: string | null
  domain: string | null
}

export interface Task {
  id: number
  asset_id: number | null
  asset_name: string | null
  location_path: string | null
  name: string
  last_completed_on: string | null
  next_due_on: string | null
  status: TaskStatus
  days_until_due: number | null
  recurrence_type: RecurrenceType | string
  recurrence_interval: number | null
  fixed_month: number | null
  fixed_day: number | null
  last_intervention_id: number | null
  needs_part_replacement: boolean
  replacement_part_name: string | null
  replacement_part_source: string | null
  preparation_notes: string | null
  notes: string | null
}

export interface DocumentMeta {
  id: number
  name: string
  doc_type: string
  file_size: number | null
  mime_type: string | null
  created_at: string
}

export interface Cost {
  id: number
  amount_cents: number
  currency: string
  incurred_on: string
}

export interface Intervention {
  id: number
  performed_on: string
  performed_by: string | null
  notes: string | null
  cost: Cost | null
  documents: DocumentMeta[]
}

export interface HistoryEntry extends Intervention {
  asset_id: number
  asset_name: string
  task_id: number | null
  task_name: string | null
}

export interface TaskIn {
  name: string
  recurrence_type: RecurrenceType
  recurrence_interval?: number | null
  fixed_month?: number | null
  fixed_day?: number | null
  last_completed_on?: string | null
  needs_part_replacement?: boolean
  replacement_part_name?: string | null
  replacement_part_source?: string | null
  preparation_notes?: string | null
  notes?: string | null
}

export interface CompleteIn {
  performed_on?: string | null
  performed_by?: string | null
  notes?: string | null
  amount_cents?: number | null
}

export interface AssetListItem {
  id: number
  name: string
  category_name: string | null
  category_slug: string | null
  location_path: string | null
  install_date: string | null
  status: string
  task_status: TaskStatus
  photo_document_id: number | null
  warranty_end_date: string | null
}

export interface Asset {
  id: number
  name: string
  kind: string
  status: string
  category_id: number | null
  category_name: string | null
  category_slug: string | null
  location_id: number | null
  location_path: string | null
  brand: string | null
  model: string | null
  reference: string | null
  serial_number: string | null
  purchase_date: string | null
  install_date: string | null
  notes: string | null
  warranty: Warranty | null
  photo_document_id: number | null
  ha_link: HaLink | null
  tasks: Task[]
}

export interface AssetIn {
  name: string
  category_id?: number | null
  location_id?: number | null
  brand?: string | null
  model?: string | null
  reference?: string | null
  serial_number?: string | null
  purchase_date?: string | null
  install_date?: string | null
  notes?: string | null
  warranty?: WarrantyIn | null
}

export interface AssetPatch {
  name?: string
  category_id?: number | null
  location_id?: number | null
  brand?: string | null
  model?: string | null
  serial_number?: string | null
  install_date?: string | null
  notes?: string | null
}
