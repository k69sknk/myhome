import { apiUrl } from '../base-path'
import type { HealthResponse } from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: { Accept: 'application/json', ...init?.headers },
    ...init,
  })

  if (!response.ok) {
    // FastAPI renvoie {"detail": ...} sur erreur, mais un echec en amont
    // (nginx, ingress) renvoie du HTML : on ne suppose donc pas du JSON.
    const detail = await response.text().catch(() => '')
    throw new ApiError(response.status, detail || response.statusText)
  }

  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthResponse>('health'),
}
