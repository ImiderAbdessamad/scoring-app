import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  fetchAnalyseState,
  startAnalyseJob,
  streamAnalyseJob,
  type AnalyseJobProgress,
  type AnalyseJobStatus,
} from '@/services/api/analyse'
import type { AnalyseWorkspace } from '@/types/analyse'

export type LiveAnalyseJob = {
  dossierId: string
  jobId: string
  status: AnalyseJobStatus
  progressPct: number
  message: string
  currentStep: string
  currentPage?: number | null
  pagesTotal?: number | null
  error?: string | null
  filename?: string | null
}

type AnalyseJobsContextValue = {
  jobs: Record<string, LiveAnalyseJob>
  workspaces: Record<string, AnalyseWorkspace>
  startJob: (dossierId: string) => Promise<LiveAnalyseJob>
  ensureStream: (dossierId: string, job: AnalyseJobProgress) => void
  isRunning: (dossierId: string) => boolean
}

const AnalyseJobsContext = createContext<AnalyseJobsContextValue | null>(null)

async function waitForAnalyseResult(dossierId: string) {
  let last = await fetchAnalyseState(dossierId)
  for (let remaining = 8; remaining > 0; remaining -= 1) {
    const status = last.job?.status
    const hasCharts = Boolean(last.workspace?.ratios?.items?.length)
    if (status === 'completed' || status === 'failed' || hasCharts || remaining === 1) {
      return last
    }
    await new Promise((resolve) => window.setTimeout(resolve, 350))
    last = await fetchAnalyseState(dossierId)
  }
  return last
}

function fromProgress(dossierId: string, job: AnalyseJobProgress): LiveAnalyseJob {
  return {
    dossierId,
    jobId: job.job_id,
    status: job.status,
    progressPct: job.progress_pct,
    message: job.message,
    currentStep: job.current_step,
    currentPage: job.current_page,
    pagesTotal: job.pages_total,
    error: job.error,
    filename: job.filename,
  }
}

export function AnalyseJobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<string, LiveAnalyseJob>>({})
  const [workspaces, setWorkspaces] = useState<Record<string, AnalyseWorkspace>>({})
  const streams = useRef<Record<string, AbortController>>({})

  const applyEvent = useCallback((dossierId: string, data: Record<string, unknown>) => {
    setJobs((prev) => {
      const current = prev[dossierId]
      if (!current) return prev
      return {
        ...prev,
        [dossierId]: {
          ...current,
          status: (data.status as AnalyseJobStatus) || current.status,
          progressPct: typeof data.progress_pct === 'number' ? data.progress_pct : current.progressPct,
          message: typeof data.message === 'string' ? data.message : current.message,
          currentStep: typeof data.current_step === 'string' ? data.current_step : current.currentStep,
          currentPage: (data.current_page as number | null | undefined) ?? current.currentPage,
          pagesTotal: (data.pages_total as number | null | undefined) ?? current.pagesTotal,
          error: (data.error as string | null | undefined) ?? current.error,
        },
      }
    })
  }, [])

  const ensureStream = useCallback(
    (dossierId: string, job: AnalyseJobProgress) => {
      if (job.status === 'completed' || job.status === 'failed') return
      if (streams.current[job.job_id]) return

      const controller = new AbortController()
      streams.current[job.job_id] = controller
      setJobs((prev) => ({ ...prev, [dossierId]: fromProgress(dossierId, job) }))

      void streamAnalyseJob(
        job.job_id,
        async (event, data) => {
          applyEvent(dossierId, data)
          if (event === 'result_ready' || event === 'job_failed') {
            delete streams.current[job.job_id]
            try {
              const state = await waitForAnalyseResult(dossierId)
              if (state.workspace) {
                setWorkspaces((prev) => ({ ...prev, [dossierId]: state.workspace as AnalyseWorkspace }))
              }
              if (state.job) {
                setJobs((prev) => ({ ...prev, [dossierId]: fromProgress(dossierId, state.job!) }))
              }
            } catch {
              /* l'écran dossier affichera l'erreur au prochain chargement */
            }
          }
        },
        controller.signal,
      ).catch((err: unknown) => {
        if (controller.signal.aborted) return
        delete streams.current[job.job_id]
        setJobs((prev) => ({
          ...prev,
          [dossierId]: {
            ...(prev[dossierId] ?? fromProgress(dossierId, job)),
            status: 'failed',
            error: err instanceof Error ? err.message : 'Flux interrompu',
          },
        }))
      })
    },
    [applyEvent],
  )

  const startJob = useCallback(
    async (dossierId: string) => {
      const created = await startAnalyseJob(dossierId)
      const live: LiveAnalyseJob = {
        dossierId,
        jobId: created.job_id,
        status: created.status,
        progressPct: created.status === 'queued' ? 1 : 5,
        message: 'Analyse lancée — vous pouvez changer de dossier.',
        currentStep: 'queued',
        filename: created.filename,
      }
      setJobs((prev) => ({ ...prev, [dossierId]: live }))
      ensureStream(dossierId, {
        job_id: created.job_id,
        dossier_id: dossierId,
        status: created.status,
        progress_pct: live.progressPct,
        current_step: 'queued',
        pages_financial: 0,
        pages_skipped: 0,
        pages_failed: 0,
        message: live.message,
        filename: created.filename,
      })
      return live
    },
    [ensureStream],
  )

  const isRunning = useCallback(
    (dossierId: string) => {
      const job = jobs[dossierId]
      return Boolean(job && (job.status === 'queued' || job.status === 'processing'))
    },
    [jobs],
  )

  const value = useMemo(
    () => ({ jobs, workspaces, startJob, ensureStream, isRunning }),
    [jobs, workspaces, startJob, ensureStream, isRunning],
  )

  return <AnalyseJobsContext.Provider value={value}>{children}</AnalyseJobsContext.Provider>
}

export function useAnalyseJobs() {
  const context = useContext(AnalyseJobsContext)
  if (!context) throw new Error('useAnalyseJobs doit être utilisé dans AnalyseJobsProvider.')
  return context
}
