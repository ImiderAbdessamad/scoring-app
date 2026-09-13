import { USE_MOCK } from '@/config/env'
import { computeDashboardKpis, computeRiskDistribution } from '@/lib/dashboardKpis'
import { apiGet } from '@/services/api/client'
import { getMockDashboard } from '@/services/mocks/data'
import { getDossierStore } from '@/services/mocks/dossierStore'
import type { DashboardData } from '@/types/dossier'

function delay(ms = 320) {
  return new Promise((r) => setTimeout(r, ms))
}

export async function fetchDashboard(): Promise<DashboardData> {
  if (USE_MOCK) {
    await delay()
    const dossiers = getDossierStore()
    const base = getMockDashboard()
    return {
      ...base,
      kpis: computeDashboardKpis(dossiers),
      sectors: computeRiskDistribution(dossiers).sectors,
      unreadAlertCount: (base.alerts || []).filter((a) => !a.read).length,
    }
  }
  return apiGet<DashboardData>('/dashboard')
}
