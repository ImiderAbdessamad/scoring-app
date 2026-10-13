import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { PageHero } from '@/components/layout/PageHero'
import { QueueList } from '@/features/dashboard/components/QueueList'
import { DashboardSidePanels } from '@/features/dashboard/components/DashboardSidePanels'
import { formatTodayFr } from '@/lib/format'
import { currentUser } from '@/lib/auth'
import { fetchDashboard } from '@/services/api/dashboard'
import { subscribeDossierStore } from '@/services/mocks/dossierStore'
import { useCreateDossier } from '@/features/dossiers/create/CreateDossierProvider'
import { useAnalyseJobs } from '@/features/analyse/AnalyseJobsProvider'
import { USE_MOCK } from '@/config/env'
import type { DashboardData } from '@/types/dossier'

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [storeTick, setStoreTick] = useState(0)
  const todayLabel = formatTodayFr()
  const { openCreateDossier } = useCreateDossier()
  const { jobs } = useAnalyseJobs()
  const running = Object.values(jobs).some((j) => j.status === 'queued' || j.status === 'processing')

  useEffect(() => subscribeDossierStore(() => setStoreTick((n) => n + 1)), [])

  useEffect(() => {
    let cancelled = false
    fetchDashboard()
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Erreur de chargement')
      })
    return () => {
      cancelled = true
    }
  }, [storeTick])

  // Rafraîchissement pendant une analyse : lancée depuis ce navigateur, ou visible dans la file (import, partenaire).
  const analysing = running || Boolean(data?.queue.some((item) => item.stage === 'analyzing'))
  useEffect(() => {
    if (USE_MOCK || !analysing) return
    const t = window.setInterval(() => {
      fetchDashboard()
        .then(setData)
        .catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(t)
  }, [analysing])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHero
        title="Tableau de bord"
        watermark="Étude de risque"
        subtitle={`${todayLabel} · Bienvenue, ${currentUser().firstName}`}
        actions={
          <>
            <Link to="/dossiers">
              <Button variant="glass">
                Tous les dossiers
              </Button>
            </Link>
            <Button variant="primary" onClick={openCreateDossier}>
              Nouveau dossier +
            </Button>
          </>
        }
      />

      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-6 pb-10">
        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </div>
        )}

        {!data && !error && <DashboardSkeleton />}

        {data && (
          <>
            <div className="grid grid-cols-1 gap-[18px] xl:grid-cols-[1fr_360px]">
              <QueueList items={data.queue} total={data.queueTotal} recent={data.recent ?? []} />
              <DashboardSidePanels
                riskDist={data.riskDist}
                riskActiveTotal={data.riskActiveTotal}
                sectors={data.sectors}
                alerts={data.alerts}
                activity={data.activity}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="grid grid-cols-1 gap-[18px] xl:grid-cols-[1fr_360px]">
        <div className="h-[360px] rounded-[20px] bg-white border border-wb-line" />
        <div className="h-[360px] rounded-[20px] bg-white border border-wb-line" />
      </div>
    </div>
  )
}
