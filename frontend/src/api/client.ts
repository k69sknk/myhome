import { apiUrl } from '../base-path'
import type {
  ApplyRoomResult,
  Asset,
  AssetIn,
  AssetKind,
  AssetListItem,
  AssetPatch,
  CalendarSyncResult,
  Catalog,
  CatalogProposal,
  CatalogRoomState,
  Category,
  CategoryIn,
  CompleteIn,
  DocumentMeta,
  HaCalendarOption,
  HaDevice,
  HaLinkIn,
  HaPersonOption,
  HaSummary,
  HealthResponse,
  HistoryEntry,
  Home,
  Intervention,
  Location,
  LocationIn,
  LocationType,
  LocationTypeIn,
  MaintenanceSelection,
  Member,
  MemberIn,
  ReminderRunResult,
  Task,
  TaskIn,
  TaskPatch,
} from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function formatErrorDetail(detail: string): string {
  try {
    const parsed = JSON.parse(detail) as { detail?: unknown }
    if (typeof parsed.detail === 'string') return parsed.detail
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg)
          }
          return JSON.stringify(item)
        })
        .join('; ')
    }
  } catch {
    /* reponse non JSON (nginx, ingress) */
  }
  return detail
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new ApiError(response.status, formatErrorDetail(detail) || response.statusText)
  }

  return (await response.json()) as T
}

function jsonBody(body: unknown): RequestInit {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  health: () => request<HealthResponse>('health'),
  summary: () => request<HaSummary>('ha/summary'),

  home: () => request<Home>('homes/current'),
  patchHome: (body: {
    name?: string
    due_soon_threshold_days?: number
    ha_calendar_entity_id?: string | null
    ha_calendar_sync_enabled?: boolean
    task_notifications_enabled?: boolean
    reminder_hour?: number
    default_notify_service?: string | null
  }) => request<Home>('homes/current', { method: 'PATCH', ...jsonBody(body) }),

  categories: () => request<Category[]>('categories'),
  createCategory: (body: CategoryIn) =>
    request<Category>('categories', { method: 'POST', ...jsonBody(body) }),

  locationTypes: () => request<LocationType[]>('location-types'),
  createLocationType: (body: LocationTypeIn) =>
    request<LocationType>('location-types', { method: 'POST', ...jsonBody(body) }),
  patchLocationType: (id: number, body: LocationTypeIn) =>
    request<LocationType>(`location-types/${id}`, { method: 'PATCH', ...jsonBody(body) }),
  deleteLocationType: (id: number) =>
    request<{ ok: boolean }>(`location-types/${id}`, { method: 'DELETE' }),

  locations: () => request<Location[]>('locations'),
  createLocation: (body: LocationIn) =>
    request<Location>('locations', { method: 'POST', ...jsonBody(body) }),
  patchLocation: (id: number, body: Partial<LocationIn>) =>
    request<Location>(`locations/${id}`, { method: 'PATCH', ...jsonBody(body) }),
  deleteLocation: (id: number) => request<{ ok: boolean }>(`locations/${id}`, { method: 'DELETE' }),

  assets: (kind?: 'equipment' | 'building_element') =>
    request<AssetListItem[]>(`assets${kind ? `?kind=${kind}` : ''}`),
  asset: (id: number) => request<Asset>(`assets/${id}`),
  createAsset: (body: AssetIn) => request<Asset>('assets', { method: 'POST', ...jsonBody(body) }),
  patchAsset: (id: number, body: AssetPatch) =>
    request<Asset>(`assets/${id}`, { method: 'PATCH', ...jsonBody(body) }),

  createTask: (assetId: number, body: TaskIn) =>
    request<Task>(`assets/${assetId}/tasks`, { method: 'POST', ...jsonBody(body) }),
  patchTask: (taskId: number, body: TaskPatch) =>
    request<Task>(`tasks/${taskId}`, { method: 'PATCH', ...jsonBody(body) }),
  tasks: () => request<Task[]>('tasks'),
  completeTask: (taskId: number, body: CompleteIn) =>
    request<Task>(`tasks/${taskId}/complete`, { method: 'POST', ...jsonBody(body) }),
  taskInterventions: (taskId: number) =>
    request<Intervention[]>(`tasks/${taskId}/interventions`),
  interventions: (params: { limit: number; offset: number; memberId?: number }) =>
    request<HistoryEntry[]>(
      `interventions?limit=${params.limit}&offset=${params.offset}` +
        (params.memberId != null ? `&member_id=${params.memberId}` : ''),
    ),
  deleteTask: (taskId: number) => request<{ ok: boolean }>(`tasks/${taskId}`, { method: 'DELETE' }),
  deleteIntervention: (interventionId: number) =>
    request<{ ok: boolean }>(`interventions/${interventionId}`, { method: 'DELETE' }),
  uploadInterventionDocument: async (interventionId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentMeta>(`interventions/${interventionId}/documents`, {
      method: 'POST',
      body: form,
    })
  },
  documentFileUrl: (documentId: number) => apiUrl(`documents/${documentId}/file`),
  uploadAssetDocument: async (
    assetId: number,
    file: File,
    docType: 'manual' | 'invoice' | 'other' | 'photo' = 'manual',
    name?: string,
  ) => {
    const form = new FormData()
    form.append('file', file)
    form.append('doc_type', docType)
    if (name) form.append('name', name)
    return request<DocumentMeta>(`assets/${assetId}/documents`, { method: 'POST', body: form })
  },
  assetDocuments: (assetId: number) => request<DocumentMeta[]>(`assets/${assetId}/documents`),
  deleteDocument: (documentId: number) =>
    request<{ ok: boolean }>(`documents/${documentId}`, { method: 'DELETE' }),

  haDevices: () => request<HaDevice[]>('ha/devices'),
  putHaLink: (assetId: number, body: HaLinkIn) =>
    request<Asset>(`assets/${assetId}/ha-link`, { method: 'PUT', ...jsonBody(body) }),
  deleteHaLink: (assetId: number) =>
    request<Asset>(`assets/${assetId}/ha-link`, { method: 'DELETE' }),

  haCalendars: () => request<HaCalendarOption[]>('ha/calendars'),
  runCalendarSync: () =>
    request<CalendarSyncResult>('ha/calendar-sync/run', { method: 'POST' }),

  runReminders: () => request<ReminderRunResult>('ha/reminders/run', { method: 'POST' }),

  haPersons: () => request<HaPersonOption[]>('ha/persons'),
  haNotifyServices: () => request<string[]>('ha/notify-services'),

  members: () => request<Member[]>('members'),
  createMember: (body: MemberIn) =>
    request<Member>('members', { method: 'POST', ...jsonBody(body) }),
  patchMember: (memberId: number, body: Partial<MemberIn>) =>
    request<Member>(`members/${memberId}`, { method: 'PATCH', ...jsonBody(body) }),
  deleteMember: (memberId: number) =>
    request<{ ok: boolean }>(`members/${memberId}`, { method: 'DELETE' }),

  catalog: () => request<Catalog>('catalog'),
  applyCatalogRoom: (
    target: { roomKey: string | null; locationId: number | null },
    itemKeys: string[],
    /** Objets absents du catalogue, saisis pendant le tour. Un nom que le
     *  catalogue connait est ramene a sa fiche type cote serveur. */
    customItems: { name: string; kind: AssetKind }[] = [],
  ) =>
    request<ApplyRoomResult>('catalog/rooms', {
      method: 'POST',
      ...jsonBody({
        room_key: target.roomKey,
        location_id: target.locationId,
        item_keys: itemKeys,
        custom_items: customItems,
      }),
    }),
  catalogState: () => request<CatalogRoomState[]>('catalog/state'),
  catalogProposals: () => request<CatalogProposal[]>('catalog/proposals'),
  applyCatalogMaintenances: (selections: MaintenanceSelection[]) =>
    request<{ created: number }>('catalog/maintenances', {
      method: 'POST',
      ...jsonBody({ selections }),
    }),
}
