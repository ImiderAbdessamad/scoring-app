import { apiGet, apiPost, apiPut } from '@/services/api/client'
import type { SectorAnalysisData } from '@/types/analyse'

export type SectorRefreshMode = 'auto' | 'false' | 'force'

export type HcpBranch = { code: string; label: string }

export type SectorSourceItem = {
  id: string
  code: string
  label: string
  shortLabel: string
  providerType: string
  description: string
  capabilities: string[]
  supportsVaAnalysis: boolean
  implemented: boolean
  enabled: boolean
  selectable: boolean
  isDefault: boolean
  notes?: string
  branchCatalog?: string
  datasetRoles?: Record<string, string>
  syncStatus?: string | null
  lastSyncAt?: string | null
}

export type SectorSourcesConfig = {
  defaultSourceId: string
  items: SectorSourceItem[]
  updatedAt?: string | null
  updatedBy?: string | null
  rules?: {
    perDossierPin?: boolean
    clearMappingOnSourceChange?: boolean
    codeNamespacesIsolated?: boolean
    globalDefaultNeverOverridesPinned?: boolean
  }
}

export function fetchSectorAnalysis(dossierId: string, refresh: SectorRefreshMode = 'auto') {
  const query = new URLSearchParams({ refresh })
  return apiGet<SectorAnalysisData & { sectorSourceId?: string; defaultSourceId?: string }>(
    `/dossiers/${encodeURIComponent(dossierId)}/sector-analysis?${query}`,
  )
}

export function fetchHcpBranches(sourceId?: string) {
  const query = sourceId ? `?sourceId=${encodeURIComponent(sourceId)}` : ''
  return apiGet<{ items: HcpBranch[]; total: number; sourceId?: string; sourceLabel?: string }>(
    `/sectors/branches${query}`,
  )
}

export function fetchSectorSources() {
  return apiGet<SectorSourcesConfig>('/sectors/sources')
}

export function setDefaultSectorSource(sourceId: string) {
  return apiPut<SectorSourcesConfig>('/sectors/sources/default', { sourceId })
}

export function updateSectorSourceFlags(
  sourceId: string,
  flags: { enabled?: boolean; selectable?: boolean },
) {
  return apiPut<SectorSourcesConfig>(`/sectors/sources/${encodeURIComponent(sourceId)}`, flags)
}

export function refreshSectorData(force = false) {
  return apiPost<{
    status: string
    checked: number
    changed: number
    updatedObservations: number
    sourceId?: string
  }>('/sectors/refresh', { force })
}

export function fetchSectorSourcesStatus() {
  return apiGet<{
    defaultSourceId?: string
    sources: Array<{
      id?: string
      code: string
      status: string
      enabled?: boolean
      selectable?: boolean
      isDefault?: boolean
      supportsVaAnalysis?: boolean
      lastCheckedAt?: string | null
      lastUpdatedAt?: string | null
      datasets?: unknown[]
    }>
  }>('/sectors/sources/status')
}

export type SectorMappingResponse = {
  sector: string
  benchmarkSectorCode: string
  reason: string
  analysis: SectorAnalysisData
  sectorSourceId?: string
  sourceLabel?: string
  finalMapping: {
    sector_code?: string | null
    sector_label?: string | null
    status?: string
    validated?: boolean
  }
  hcpBranches?: Record<string, string>
  branches?: Record<string, string>
}

export function saveSectorMapping(dossierId: string, hcpSectorCode: string, reason?: string) {
  return apiPut<SectorMappingResponse>(`/dossiers/${encodeURIComponent(dossierId)}/sector-mapping`, {
    hcpSectorCode,
    reason: reason || 'Modification manuelle du secteur par l’analyste',
  })
}

export type DossierSectorSourceResponse = {
  dossierId: string
  previousSourceId: string
  sectorSourceId: string
  sourceLabel: string
  mappingCleared: boolean
  reason: string
  analysis: SectorAnalysisData
  message: string
}

export function saveDossierSectorSource(dossierId: string, sourceId: string, reason?: string) {
  return apiPut<DossierSectorSourceResponse>(
    `/dossiers/${encodeURIComponent(dossierId)}/sector-source`,
    {
      sourceId,
      reason: reason || 'Changement de source de données sectorielles par l’analyste',
    },
  )
}
