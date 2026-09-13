import { API_BASE_URL } from '@/config/env'
import { ApiError, apiGet, apiHeaders, apiPost } from '@/services/api/client'
import type { AnalyseWorkspace } from '@/types/analyse'

export type AnalyseJobStatus = 'queued' | 'processing' | 'completed' | 'failed'

export type AnalyseJobProgress = {
  job_id: string
  dossier_id?: string | null
  status: AnalyseJobStatus
  progress_pct: number
  current_step: string
  current_page?: number | null
  pages_total?: number | null
  pages_financial: number
  pages_skipped: number
  pages_failed: number
  message: string
  error?: string | null
  stream_url?: string | null
  result_url?: string | null
  filename?: string | null
}

export type AnalyseJobCreateResponse = {
  job_id: string
  dossier_id: string
  status: AnalyseJobStatus
  stream_url: string
  result_url: string
  filename: string
}

export type AnalyseStateResponse = {
  dossier_id: string
  job: AnalyseJobProgress | null
  workspace: AnalyseWorkspace | null
  error: string | null
}

export type DossierSyntheseResponse = {
  dossier_id: string
  status: string
  job_id?: string | null
  points_forts: string[]
  points_vigilance: string[]
  score_final?: string | null
  score?: number | null
  classe?: string | null
  decision?: string | null
  recommandation?: string | null
  message?: string | null
}

export function fetchDossierSynthese(dossierId: string) {
  return apiGet<DossierSyntheseResponse>(`/dossiers/${encodeURIComponent(dossierId)}/synthese`)
}

export function fetchAnalyseState(dossierId: string) {
  return apiGet<AnalyseStateResponse>(`/dossiers/${encodeURIComponent(dossierId)}/analyse`)
}

export async function startAnalyseJob(dossierId: string) {
  const res = await fetch(`${API_BASE_URL}/dossiers/${encodeURIComponent(dossierId)}/analyse/jobs`, {
    method: 'POST',
    headers: apiHeaders({ Accept: 'application/json' }),
  })
  if (!res.ok) {
    let message = `API ${res.status}`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<AnalyseJobCreateResponse>
}

export type SseHandler = (event: string, data: Record<string, unknown>) => void

export async function streamAnalyseJob(
  jobId: string,
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_BASE_URL}/analyse/jobs/${jobId}/stream`, {
    headers: apiHeaders({ Accept: 'text/event-stream' }),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(`Flux SSE indisponible (${res.status})`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const block of chunks) {
      let event = 'message'
      const dataLines: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue
      try {
        const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
        onEvent(event, data)
      } catch {
        /* keepalive / payload partiel */
      }
    }
  }
}

export type CopilotChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

export type CopilotChatResponse = {
  reply: string
  model: string
}

export function askCopilot(
  dossierId: string,
  message: string,
  history: CopilotChatMessage[] = [],
) {
  return apiPost<CopilotChatResponse>(`/dossiers/${encodeURIComponent(dossierId)}/copilot`, {
    message,
    history,
  })
}
