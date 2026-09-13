import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/Button'
import { KpiGrid } from '@/features/dashboard/components/KpiGrid'
import { QueueList } from '@/features/dashboard/components/QueueList'
import { DashboardSidePanels } from '@/features/dashboard/components/DashboardSidePanels'
import { formatTodayFr } from '@/lib/format'
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

  useEffect(() => {
    if (USE_MOCK || !running) return
    const t = window.setInterval(() => {
      fetchDashboard()
        .then(setData)
        .catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(t)
  }, [running])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-none items-center justify-between gap-4 border-b border-wb-line bg-white px-6 py-[18px]">
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <h1 className="m-0 text-[20px] font-extrabold tracking-tight text-slate-900">
            Tableau de bord
          </h1>
          <p className="m-0 mt-0.5 text-[12px] text-wb-muted">
            {data ? `${todayLabel} · ${data.greeting}` : 'Chargement…'}
          </p>
        </motion.div>
        <div className="flex flex-wrap justify-end gap-2">
          <Link to="/dossiers">
            <Button variant="secondary">Tous les dossiers</Button>
          </Link>
          <Button variant="primary" onClick={openCreateDossier}>
            Nouveau dossier +
          </Button>
        </div>
      </header>

      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-5 pb-10">
        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </div>
        )}

        {!data && !error && <DashboardSkeleton />}

        {data && (
          <>
            <KpiGrid kpis={data.kpis} />
            <div className="grid grid-cols-1 gap-[18px] xl:grid-cols-[1fr_360px]">
              <QueueList items={data.queue} total={data.queueTotal} />
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
      <div className="grid grid-cols-2 gap-3.5 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-[118px] rounded-[14px] bg-white border border-wb-line" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-[18px] xl:grid-cols-[1fr_360px]">
        <div className="h-[360px] rounded-[14px] bg-white border border-wb-line" />
        <div className="h-[360px] rounded-[14px] bg-white border border-wb-line" />
      </div>
    </div>
  )
}
