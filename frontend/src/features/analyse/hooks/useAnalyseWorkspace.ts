import { useCallback, useEffect, useRef, useState } from 'react'
import { USE_MOCK } from '@/config/env'
import { fetchAnalyseState, askCopilot } from '@/services/api/analyse'
import {
  approveDossier,
  cancelDossierDecision,
  fetchDossierById,
  fetchDossierDetail,
  rejectDossier,
  replaceDossierDocument,
  reserveDossier,
} from '@/services/api/dossiers'
import { buildAnalyseWorkspace, getMockAnalyseWorkspace } from '@/services/mocks/analyseData'
import { useAnalyseJobs } from '@/features/analyse/AnalyseJobsProvider'
import { STATUS_META } from '@/lib/format'
import type {
  AnalyseWorkspace,
  AnalyseTabId,
  CopilotQa,
  DecisionKind,
  PipelineTraceLine,
} from '@/types/analyse'
import type { DossierStatus } from '@/types/dossier'

type ChatMessage = { role: 'ai' | 'user'; text: string }

type PipelineState = {
  running: boolean
  step: number
  trace: PipelineTraceLine[]
  scoreShown: number
}

const TRACE_TICK_MS = 420

const DECISION_FROM_STATUS: Partial<Record<DossierStatus, DecisionKind>> = {
  approved: 'approve',
  rejected: 'reject',
  reserved: 'reserve',
  review: 'reserve',
}

function nowTime(): string {
  return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function withHeaderStatus(workspace: AnalyseWorkspace, status: DossierStatus): AnalyseWorkspace {
  return {
    ...workspace,
    header: {
      ...workspace.header,
      status,
      statusLabel: STATUS_META[status].label,
    },
  }
}

export function useAnalyseWorkspace(id: string | undefined) {
  const { jobs, workspaces, startJob, ensureStream, isRunning } = useAnalyseJobs()
  const liveJob = id ? jobs[id] : undefined
  const liveWorkspace = id ? workspaces[id] : undefined
  const [data, setData] = useState<AnalyseWorkspace | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [tab, setTab] = useState<AnalyseTabId>('synthese')
  const [selectedDocId, setSelectedDocId] = useState('')
  const [openKpi, setOpenKpi] = useState<number | null>(null)
  const [openAxis, setOpenAxis] = useState(0)
  const [decision, setDecisionKind] = useState<DecisionKind | null>(null)
  const [decisionTime, setDecisionTime] = useState('')
  const [decisionBusy, setDecisionBusy] = useState(false)
  const [memoSigned, setMemoSigned] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(true)

  const [pipeline, setPipeline] = useState<PipelineState>({
    running: false,
    step: 0,
    trace: [],
    scoreShown: 0,
  })

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [uploadingDocId, setUploadingDocId] = useState<string | null>(null)

  const timerRef = useRef<number | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)

    if (!id) {
      setLoading(false)
      return
    }

    const load = async () => {
      if (USE_MOCK) {
        const [dossier, detail] = await Promise.all([
          fetchDossierById(id).catch(() => null),
          fetchDossierDetail(id).catch(() => null),
        ])
        const res = dossier
          ? buildAnalyseWorkspace(dossier, detail)
          : getMockAnalyseWorkspace(id)
        if (!res) {
          setError(`Dossier ${id} introuvable`)
          return
        }
        return res
      }

      const state = await fetchAnalyseState(id)
      if (!state.workspace) {
        setError(`Dossier ${id} introuvable`)
        return null
      }
      if (state.job) ensureStream(id, state.job)
      return state.workspace
    }

    load()
      .then((res) => {
        if (cancelled || !res) return
        setData(res)
        setSelectedDocId(res.documents.defaultDocId)
        setPipeline({
          running: false,
          step: res.pipeline.initialStep,
          trace: res.pipeline.fullTrace,
          scoreShown: res.pipeline.initialScore,
        })
        setMessages([{ role: 'ai', text: res.copilot.welcomeMessage }])
        setTab('synthese')
        setOpenKpi(null)
        setOpenAxis(0)
        setDecisionKind(DECISION_FROM_STATUS[res.header.status] ?? null)
        setDecisionTime(DECISION_FROM_STATUS[res.header.status] ? nowTime() : '')
        setDecisionBusy(false)
        setMemoSigned(false)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Erreur de chargement')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      clearTimer()
    }
  }, [id, clearTimer, ensureStream])

  useEffect(() => {
    if (!id || !liveWorkspace) return
    setData(liveWorkspace)
    setPipeline({
      running: false,
      step: liveWorkspace.pipeline.steps.length,
      trace: liveWorkspace.pipeline.fullTrace,
      scoreShown: liveWorkspace.pipeline.initialScore,
    })
    setSelectedDocId((prev) => prev || liveWorkspace.documents.defaultDocId)
  }, [id, liveWorkspace])

  useEffect(() => {
    if (!liveJob || !data) return
    if (liveJob.status !== 'queued' && liveJob.status !== 'processing') return
    const pct = Math.max(1, liveJob.progressPct)
    const step = Math.min(
      data.pipeline.steps.length,
      Math.max(1, Math.round((pct / 100) * data.pipeline.steps.length)),
    )
    setPipeline({
      running: true,
      step,
      trace: [
        ...data.pipeline.fullTrace,
        {
          type: 'in',
          text: liveJob.message || `Analyse en cours (${pct} %)`,
          step,
        },
      ],
      scoreShown: 0,
    })
  }, [liveJob, data])

  const selectDoc = useCallback((docId: string) => setSelectedDocId(docId), [])

  const uploadDocument = useCallback(
    async (docId: string, file: File) => {
      if (!id || !data) return
      const doc = data.documents.items.find((d) => d.id === docId)
      const missing = data.documents.missing.find((m) => m.id === docId)
      const uploadName =
        docId === '__add__' ? file.name : (doc?.uploadName ?? doc?.name ?? missing?.name ?? file.name)
      if (!uploadName) return

      setUploadingDocId(docId)
      setError(null)
      try {
        await replaceDossierDocument(id, uploadName, file)

        if (USE_MOCK) {
          const [dossier, detail] = await Promise.all([
            fetchDossierById(id).catch(() => null),
            fetchDossierDetail(id),
          ])
          if (!dossier || !detail) return
          const refreshed = buildAnalyseWorkspace(dossier, detail)
          setData(refreshed)
          const added = refreshed.documents.items.find((item) => item.name === uploadName)
          setSelectedDocId(added?.id ?? refreshed.documents.defaultDocId)
          return
        }

        const state = await fetchAnalyseState(id)
        if (state.workspace) {
          setData(state.workspace)
          const added = state.workspace.documents.items.find((item) => item.name === uploadName)
          setSelectedDocId(added?.id ?? state.workspace.documents.defaultDocId)
        }
        if (!isRunning(id)) {
          await startJob(id)
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Impossible d'ajouter le document")
      } finally {
        setUploadingDocId(null)
      }
    },
    [id, data, isRunning, startJob],
  )

  const toggleKpi = useCallback((index: number) => {
    setOpenKpi((prev) => (prev === index ? null : index))
  }, [])

  const toggleAxis = useCallback((index: number) => {
    setOpenAxis((prev) => (prev === index ? -1 : index))
  }, [])

  const setDecision = useCallback(
    async (kind: DecisionKind) => {
      if (!id || decisionBusy) return
      setDecisionBusy(true)
      try {
        const dossier =
          kind === 'approve'
            ? await approveDossier(id)
            : kind === 'reject'
              ? await rejectDossier(id)
              : await reserveDossier(id)
        setData((prev) => (prev ? withHeaderStatus(prev, dossier.status) : prev))
        setDecisionKind(kind)
        setDecisionTime(nowTime())
      } catch {
        return
      } finally {
        setDecisionBusy(false)
      }
    },
    [id, decisionBusy],
  )

  const clearDecision = useCallback(async () => {
    if (!id || decisionBusy) return
    setDecisionBusy(true)
    try {
      const dossier = await cancelDossierDecision(id)
      setData((prev) => (prev ? withHeaderStatus(prev, dossier.status) : prev))
      setDecisionKind(null)
      setDecisionTime('')
    } catch {
      return
    } finally {
      setDecisionBusy(false)
    }
  }, [id, decisionBusy])

  const toggleMemoSign = useCallback(() => setMemoSigned((v) => !v), [])
  const toggleCopilot = useCallback(() => setCopilotOpen((v) => !v), [])

  const runPipeline = useCallback(() => {
    if (!id || !data) return
    if (USE_MOCK) {
      clearTimer()
      const trace = data.pipeline.fullTrace
      const finalScore = data.pipeline.initialScore
      let i = 0
      setPipeline({ running: true, step: 0, trace: [], scoreShown: 0 })
      timerRef.current = window.setInterval(() => {
        i += 1
        const revealed = trace.slice(0, i)
        const lastStep = revealed.length ? revealed[revealed.length - 1].step : 0
        const done = i >= trace.length
        setPipeline({
          running: !done,
          step: done ? data.pipeline.steps.length : lastStep,
          trace: revealed,
          scoreShown: done ? finalScore : Math.round((finalScore * i) / trace.length),
        })
        if (done) clearTimer()
      }, TRACE_TICK_MS)
      return
    }
    if (isRunning(id)) return
    void startJob(id).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Impossible de lancer l'analyse")
    })
  }, [id, data, clearTimer, isRunning, startJob])

  useEffect(() => clearTimer, [clearTimer])

  const sendCopilotMessage = useCallback(
    (text?: string, _intent?: keyof Omit<CopilotQa, 'fallback'>) => {
      const content = (text ?? input).trim()
      if (!content || !id || thinking) return

      const history = messages
        .filter((m) => m.text.trim())
        .slice(-8)
        .map((m) => ({
          role: (m.role === 'ai' ? 'assistant' : 'user') as 'assistant' | 'user',
          content: m.text,
        }))

      setMessages((prev) => [...prev, { role: 'user', text: content }])
      setInput('')
      setThinking(true)

      if (USE_MOCK && data) {
        const qa = data.copilot.qa
        const answer = _intent ? qa[_intent] : qa.fallback
        window.setTimeout(() => {
          setMessages((prev) => [...prev, { role: 'ai', text: answer }])
          setThinking(false)
        }, 500)
        return
      }

      void askCopilot(id, content, history)
        .then((res) => {
          setMessages((prev) => [...prev, { role: 'ai', text: res.reply }])
        })
        .catch((e: unknown) => {
          const message =
            e instanceof Error ? e.message : 'Le copilote Qwen est indisponible pour le moment.'
          setMessages((prev) => [
            ...prev,
            { role: 'ai', text: `Je n’ai pas pu répondre : ${message}` },
          ])
        })
        .finally(() => setThinking(false))
    },
    [id, input, messages, thinking, data],
  )

  return {
    data,
    loading,
    error,
    tab,
    selectedDocId,
    openKpi,
    openAxis,
    decision,
    decisionTime,
    decisionBusy,
    memoSigned,
    copilotOpen,
    pipeline,
    messages,
    input,
    thinking,
    uploadingDocId,
    setTab,
    selectDoc,
    uploadDocument,
    toggleKpi,
    toggleAxis,
    setDecision,
    clearDecision,
    toggleMemoSign,
    toggleCopilot,
    runPipeline,
    sendCopilotMessage,
    setInput,
    liveJob,
  }
}

export type UseAnalyseWorkspaceReturn = ReturnType<typeof useAnalyseWorkspace>
