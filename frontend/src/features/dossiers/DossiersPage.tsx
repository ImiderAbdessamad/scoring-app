import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { GradeBadge, ScorePill } from '@/components/ui/ScorePill'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { USE_MOCK } from '@/config/env'
import { LIST_FILTERS, dateFromDaysAgo, formatAmountMad } from '@/lib/format'
import { displaySector } from '@/lib/sector'
import { useCreateDossier } from '@/features/dossiers/create/CreateDossierProvider'
import { fetchDossiers } from '@/services/api/dossiers'
import { useAnalyseJobs } from '@/features/analyse/AnalyseJobsProvider'
import {
  getDossierStore,
  subscribeDossierStore,
} from '@/services/mocks/dossierStore'
import type { Dossier, DossierStatus } from '@/types/dossier'

const PAGE_SIZE = 8

export function DossiersPage() {
  const { openCreateDossier } = useCreateDossier()
  const { jobs } = useAnalyseJobs()
  const [params, setParams] = useSearchParams()
  const statusParam = (params.get('status') as DossierStatus | 'all' | null) ?? 'all'
  const pageParam = Math.max(1, Number(params.get('page') ?? '1') || 1)

  const [queryInput, setQueryInput] = useState(params.get('q') ?? '')
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [items, setItems] = useState<Dossier[]>([])
  const [allForCounts, setAllForCounts] = useState<Dossier[]>([])
  const [loading, setLoading] = useState(true)
  const [storeTick, setStoreTick] = useState(0)

  useEffect(() => subscribeDossierStore(() => setStoreTick((n) => n + 1)), [])

  useEffect(() => {
    if (USE_MOCK) {
      setAllForCounts(getDossierStore())
      return
    }
    let cancelled = false
    fetchDossiers({ status: 'all' })
      .then((res) => {
        if (!cancelled) setAllForCounts(res.items)
      })
      .catch(() => {
        if (!cancelled) setAllForCounts([])
      })
    return () => {
      cancelled = true
    }
  }, [storeTick])

  const counts = useMemo(() => {
    const all = USE_MOCK ? getDossierStore() : allForCounts
    const map: Record<string, number> = { all: all.length }
    for (const f of LIST_FILTERS) {
      if (f.key === 'all') continue
      map[f.key] = all.filter((d) => d.status === f.key).length
    }
    return map
  }, [storeTick, allForCounts])

  
  useEffect(() => {
    const t = window.setTimeout(() => {
      const nextQ = queryInput.trim()
      setQuery(nextQ)
      const next = new URLSearchParams(params)
      const prevQ = params.get('q') ?? ''
      if (nextQ === prevQ) return
      if (nextQ) next.set('q', nextQ)
      else next.delete('q')
      next.delete('page')
      setParams(next, { replace: true })
    }, 250)
    return () => window.clearTimeout(t)
  }, [queryInput, params, setParams])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const t = window.setTimeout(() => {
      fetchDossiers({ status: statusParam, q: query })
        .then((res) => {
          if (!cancelled) setItems(res.items)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, 120)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
  }, [statusParam, query, storeTick])

  const running = Object.values(jobs).some((j) => j.status === 'queued' || j.status === 'processing')
  useEffect(() => {
    if (USE_MOCK || !running) return
    const t = window.setInterval(() => {
      fetchDossiers({ status: statusParam, q: query })
        .then((res) => setItems(res.items))
        .catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(t)
  }, [running, statusParam, query])

  const decoratedItems = items.map((d) => {
    const job = jobs[d.id]
    if (job && (job.status === 'queued' || job.status === 'processing')) {
      return { ...d, status: 'analyzing' as const, analyseProgressPct: job.progressPct, score: d.score }
    }
    return d
  })

  const totalPages = Math.max(1, Math.ceil(decoratedItems.length / PAGE_SIZE))
  const page = Math.min(pageParam, totalPages)
  const pageItems = decoratedItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const from = decoratedItems.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, decoratedItems.length)

  function setStatus(key: DossierStatus | 'all') {
    const next = new URLSearchParams(params)
    if (key === 'all') next.delete('status')
    else next.set('status', key)
    next.delete('page')
    setParams(next)
  }

  function goToPage(p: number) {
    const next = new URLSearchParams(params)
    if (p <= 1) next.delete('page')
    else next.set('page', String(p))
    setParams(next)
  }

  function clearSearch() {
    setQueryInput('')
    setQuery('')
    const next = new URLSearchParams(params)
    next.delete('q')
    next.delete('page')
    setParams(next, { replace: true })
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-none flex-wrap items-center justify-between gap-4 border-b border-wb-line bg-white px-6 py-[18px]">
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="m-0 text-[20px] font-extrabold tracking-tight text-slate-900">
            Dossiers de crédit-bail
          </h1>
          <p className="m-0 mt-0.5 text-[12px] text-wb-muted">
            {loading
              ? 'Chargement…'
              : items.length === 0
                ? 'Aucun dossier'
                : `${items.length} dossier(s) · affichage ${from}–${to}`}
          </p>
        </motion.div>

        <div className="flex flex-wrap items-center gap-2.5">
          <label className="flex items-center gap-2 rounded-[10px] border border-[#E2E5EA] bg-wb-surface px-3 py-2 focus-within:border-wb-accent focus-within:bg-white focus-within:ring-2 focus-within:ring-wb-accent/15">
            <Search size={14} className="text-wb-faint" />
            <input
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="Réf., entreprise, secteur, analyste…"
              className="w-[240px] border-0 bg-transparent text-[12.5px] text-slate-900 outline-none placeholder:text-wb-faint"
              aria-label="Rechercher un dossier"
            />
            {queryInput && (
              <button
                type="button"
                onClick={clearSearch}
                className="flex cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-wb-faint hover:text-slate-700"
                aria-label="Effacer la recherche"
              >
                <X size={14} />
              </button>
            )}
          </label>
          <Button variant="primary" onClick={openCreateDossier}>
            Nouveau +
          </Button>
        </div>
      </header>

      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-5 pb-10">
        <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
          {LIST_FILTERS.map((f) => {
            const active = statusParam === f.key
            const count = counts[f.key] ?? 0
            const tone =
              f.key === 'approved'
                ? 'text-emerald-700'
                : f.key === 'rejected'
                  ? 'text-red-600'
                  : f.key === 'reserved'
                    ? 'text-amber-700'
                    : ''
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setStatus(f.key)}
                className={[
                  'relative cursor-pointer whitespace-nowrap rounded-full border-0 px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors',
                  active
                    ? 'bg-wb-ink text-white'
                    : ['bg-white ring-1 ring-wb-line hover:bg-wb-surface', tone || 'text-slate-600'].join(
                        ' ',
                      ),
                ].join(' ')}
              >
                <span className="relative z-10">
                  {f.label}
                  {f.key !== 'all' && (
                    <span
                      className={[
                        'ml-1.5 tabular-nums',
                        active ? 'text-wb-rail' : tone ? 'opacity-80' : 'text-wb-faint',
                      ].join(' ')}
                    >
                      ({count})
                    </span>
                  )}
                </span>
                {active && (
                  <motion.span
                    layoutId="filter-pill"
                    className="absolute inset-0 z-0 rounded-full bg-wb-ink"
                    transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  />
                )}
              </button>
            )
          })}
        </div>

        <Card delay={0.1} className="overflow-hidden">
          <div className="wb-scroll overflow-x-auto">
            <div className="min-w-[1080px]">
              <div className="grid grid-cols-[140px_1fr_120px_112px_60px_104px_150px_100px_88px_32px] gap-2 border-b border-wb-line bg-[#FAFBFC] px-4 py-2.5 text-[10.5px] font-bold uppercase tracking-[0.04em] text-wb-faint">
                <div>Référence</div>
                <div>Entreprise</div>
                <div>Secteur</div>
                <div>Montant</div>
                <div>Durée</div>
                <div>Score · Note</div>
                <div>Statut</div>
                <div>Analyste</div>
                <div>Reçu</div>
                <div />
              </div>

              <AnimatePresence mode="popLayout">
                {!loading && items.length === 0 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="px-6 py-12 text-center"
                  >
                    <div className="text-[14px] font-semibold text-slate-700">
                      Aucun dossier trouvé
                    </div>
                    <div className="mt-1 text-[12.5px] text-wb-faint">
                      Modifiez votre recherche ou les filtres.
                    </div>
                  </motion.div>
                )}

                {pageItems.map((d, i) => (
                  <motion.div
                    key={d.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ delay: Math.min(i * 0.03, 0.24), duration: 0.28 }}
                  >
                    <Link
                      to={`/analyse/${d.id}`}
                      className="grid grid-cols-[140px_1fr_120px_112px_60px_104px_150px_100px_88px_32px] items-center gap-2 border-b border-[#F1F2F4] px-4 py-3.5 text-[13px] no-underline transition-colors hover:bg-[#FBFCFD] last:border-b-0"
                    >
                      <div>
                        <div className="font-mono text-[12.5px] font-bold text-wb-accent">
                          {d.id}
                        </div>
                        {d.source === 'pvc' && (
                          <div className="mt-0.5 text-[10px] font-bold uppercase tracking-wide text-wb-faint">
                            PVC{d.noPv ? ` · ${d.noPv}` : ''}
                          </div>
                        )}
                      </div>
                      <div className="truncate font-bold text-slate-800">{d.name}</div>
                      <div className="text-wb-muted">{displaySector(d.sector)}</div>
                      <div className="font-bold tabular-nums text-slate-900">
                        {formatAmountMad(d.amount)}
                      </div>
                      <div className="tabular-nums text-wb-muted">{d.duration}m</div>
                      <div className="flex items-center gap-1.5">
                        <ScorePill score={d.score} classe={d.classe} />
                        <GradeBadge classe={d.classe} />
                      </div>
                      <div>
                        <StatusBadge status={d.status} />
                        {typeof d.analyseProgressPct === 'number' && d.status === 'analyzing' && (
                          <div className="mt-1 text-[10.5px] font-semibold tabular-nums text-blue-700">
                            {d.analyseProgressPct} %
                          </div>
                        )}
                      </div>
                      <div className="text-wb-muted">{d.analyst}</div>
                      <div className="tabular-nums text-wb-faint">
                        {d.date || dateFromDaysAgo(d.receivedDaysAgo)}
                      </div>
                      <div className="flex justify-end text-wb-faint">
                        <ChevronRight size={16} />
                      </div>
                    </Link>
                  </motion.div>
                ))}
              </AnimatePresence>

              {loading && (
                <div className="space-y-0">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-[56px] animate-pulse border-b border-[#F1F2F4] bg-gradient-to-r from-transparent via-slate-50 to-transparent"
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {!loading && items.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-wb-line px-4 py-3">
              <div className="text-[12px] text-wb-muted">
                Page <span className="font-semibold text-slate-800">{page}</span> /{' '}
                {totalPages}
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => goToPage(page - 1)}
                  className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border-0 bg-wb-surface text-slate-600 transition-colors hover:bg-white hover:ring-1 hover:ring-wb-line disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Page précédente"
                >
                  <ChevronLeft size={16} />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => goToPage(p)}
                    className={[
                      'inline-flex h-8 min-w-8 cursor-pointer items-center justify-center rounded-lg border-0 px-2 text-[12.5px] font-semibold transition-colors',
                      p === page
                        ? 'bg-wb-ink text-white'
                        : 'bg-transparent text-slate-600 hover:bg-wb-surface',
                    ].join(' ')}
                  >
                    {p}
                  </button>
                ))}
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => goToPage(page + 1)}
                  className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border-0 bg-wb-surface text-slate-600 transition-colors hover:bg-white hover:ring-1 hover:ring-wb-line disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Page suivante"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
