import { API_BASE_URL } from '@/config/env'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
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
    throw new ApiError(res.status, `API ${res.status}: ${path}`)
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
    throw new ApiError(res.status, await readErrorMessage(res, path))
  }

  return res.json() as Promise<T>
}

async function readErrorMessage(res: Response, path: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d) =>
          typeof d === 'object' && d && 'msg' in d
            ? String((d as { msg: unknown }).msg)
            : JSON.stringify(d),
        )
        .join(' · ')
    }
  } catch {
    
  }
  return `API ${res.status}: ${path}`
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: apiHeaders(),
    body: form,
  })

  if (!res.ok) {
    throw new ApiError(res.status, await readErrorMessage(res, path))
  }

  return res.json() as Promise<T>
}
