import { apiGet, apiPost, apiPut } from '@/services/api/client'
import type { SectorAnalysisData } from '@/types/analyse'

export type SectorRefreshMode = 'auto' | 'false' | 'force'

export function fetchSectorAnalysis(dossierId: string, refresh: SectorRefreshMode = 'auto') {
  const query = new URLSearchParams({ refresh })
  return apiGet<SectorAnalysisData>(`/dossiers/${encodeURIComponent(dossierId)}/sector-analysis?${query}`)
}

export function refreshSectorData(force = false) {
  return apiPost<{
    status: string
    checked: number
    changed: number
    updatedObservations: number
  }>('/sectors/refresh', { force })
}

export function fetchSectorSourcesStatus() {
  return apiGet<{ sources: Array<{ code: string; status: string; datasets?: unknown[] }> }>('/sectors/sources/status')
}

export function saveSectorMapping(dossierId: string, hcpSectorCode: string, reason: string) {
  return apiPut(`/dossiers/${encodeURIComponent(dossierId)}/sector-mapping`, { hcpSectorCode, reason })
}
