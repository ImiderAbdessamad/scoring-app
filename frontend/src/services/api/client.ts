import { API_BASE_URL } from '@/config/env'

export class ApiError extends Error {
  status: number
  code?: string
  detail?: unknown
  payload?: unknown

  constructor(status: number, message: string, extra?: { code?: string; detail?: unknown; payload?: unknown }) {
    super(message)
    this.status = status
    this.code = extra?.code
    this.detail = extra?.detail
    this.payload = extra?.payload
    this.name = 'ApiError'
  }
}

export function apiHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  return headers
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: apiHeaders(),
  })

  if (!res.ok) {
    throw await toApiError(res, path)
  }

  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    throw await toApiError(res, path)
  }

  return res.json() as Promise<T>
}

async function toApiError(res: Response, path: string): Promise<ApiError> {
  let payload: unknown
  try {
    payload = await res.json()
  } catch {
    return new ApiError(res.status, `API ${res.status}: ${path}`)
  }
  const body = payload as { detail?: unknown; code?: string; message?: string }
  const detail = body.detail
  let code: string | undefined = body.code
  let message = `API ${res.status}: ${path}`
  if (typeof detail === 'string') message = detail
  else if (detail && typeof detail === 'object' && detail !== null && 'code' in (detail as object)) {
    const d = detail as { code?: string; message?: string; blocking_reasons?: string[] }
    code = d.code || code
    message = d.message || message
  } else if (Array.isArray(detail)) {
    message = detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d))).join(' · ')
  }
  return new ApiError(res.status, message, { code, detail, payload })
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw await toApiError(res, path)
  }
  return res.json() as Promise<T>
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: apiHeaders(),
    body: form,
  })

  if (!res.ok) {
    throw await toApiError(res, path)
  }

  return res.json() as Promise<T>
}
