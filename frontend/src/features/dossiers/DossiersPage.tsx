import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { PageHero } from '@/components/layout/PageHero'
import { Card } from '@/components/ui/Card'
import { USE_MOCK } from '@/config/env'
import { dateFromDaysAgo, formatAmountMad } from '@/lib/format'
import { displaySector } from '@/lib/sector'
import { useCreateDossier } from '@/features/dossiers/create/CreateDossierProvider'
import { fetchDossiers } from '@/services/api/dossiers'
import { useAnalyseJobs } from '@/features/analyse/AnalyseJobsProvider'
import {
  subscribeDossierStore,
} from '@/services/mocks/dossierStore'
import type { Dossier } from '@/types/dossier'

const PAGE_SIZE = 8

export function DossiersPage() {
  const { openCreateDossier } = useCreateDossier()
  const { jobs } = useAnalyseJobs()
  const [params, setParams] = useSearchParams()
  const statusParam = 'all' as const
  const pageParam = Math.max(1, Number(params.get('page') ?? '1') || 1)

  const [queryInput, setQueryInput] = useState(params.get('q') ?? '')
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [items, setItems] = useState<Dossier[]>([])
  const [loading, setLoading] = useState(true)
  const [storeTick, setStoreTick] = useState(0)

  useEffect(() => subscribeDossierStore(() => setStoreTick((n) => n + 1)), [])


  
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
      <PageHero
        title="Dossiers de crédit-bail"
        watermark="Dossiers"
        subtitle={
          loading
            ? 'Chargement…'
            : items.length === 0
              ? 'Aucun dossier'
              : `${items.length} dossier(s) · affichage ${from}–${to}`
        }
        actions={
          <>
            <label className="flex items-center gap-2 rounded-full border border-white/30 bg-white/10 px-4 py-2 backdrop-blur-[2px] focus-within:border-white/60 focus-within:bg-white/15">
              <Search size={14} className="text-white/70" />
              <input
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Réf., entreprise, secteur, analyste…"
                className="w-[240px] border-0 bg-transparent text-[12.5px] text-white outline-none placeholder:text-white/60"
                aria-label="Rechercher un dossier"
              />
              {queryInput && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="flex cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-white/70 hover:text-white"
                  aria-label="Effacer la recherche"
                >
                  <X size={14} />
                </button>
              )}
            </label>
            <Button variant="primary" onClick={openCreateDossier}>
              Nouveau dossier +
            </Button>
          </>
        }
      />

      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-6 pb-10">
        <Card delay={0.1} className="overflow-hidden">
          <div className="wb-scroll overflow-x-auto">
            <div className="min-w-[960px]">
              <div className="grid grid-cols-[140px_1fr_140px_120px_70px_120px_96px_40px] gap-2 border-b border-wb-line bg-[#F8FAFC] px-5 py-3 text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
                <div>Référence</div>
                <div>Entreprise</div>
                <div>Secteur</div>
                <div>Montant</div>
                <div>Durée</div>
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
                      className="grid grid-cols-[140px_1fr_140px_120px_70px_120px_96px_40px] group items-center gap-2 border-b border-wb-line px-5 py-4 text-[13px] no-underline transition-colors hover:bg-wb-accent-soft/40 last:border-b-0"
                    >
                      <div>
                        <div className="font-mono text-[12.5px] font-bold text-wb-accent-text">
                          {d.id}
                        </div>
                        {d.source === 'pvc' && (
                          <span className="mt-1 inline-flex rounded-[8px] bg-wb-surface px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-wb-muted">
                            PVC{d.noPv ? ` · ${d.noPv}` : ''}
                          </span>
                        )}
                      </div>
                      <div className="truncate text-[14px] font-bold text-[#1C1B1B]">{d.name}</div>
                      <div className="text-wb-muted">{displaySector(d.sector)}</div>
                      <div className="font-bold tabular-nums text-slate-900">
                        {formatAmountMad(d.amount)}
                      </div>
                      <div className="tabular-nums text-wb-muted">{d.duration}m</div>
                      <div className="text-wb-muted">{d.analyst}</div>
                      <div className="tabular-nums text-wb-faint">
                        {d.date || dateFromDaysAgo(d.receivedDaysAgo)}
                      </div>
                      <div className="flex justify-end">
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-wb-surface text-wb-muted transition-colors group-hover:bg-wb-accent group-hover:text-white">
                          <ChevronRight size={15} strokeWidth={2.2} />
                        </span>
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
                      className="h-[60px] animate-pulse border-b border-wb-line bg-gradient-to-r from-transparent via-slate-50 to-transparent"
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {!loading && items.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-wb-line px-5 py-3.5">
              <div className="text-[12px] text-wb-muted">
                Page <span className="font-semibold text-slate-800">{page}</span> /{' '}
                {totalPages}
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => goToPage(page - 1)}
                  className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-wb-line bg-white text-slate-600 transition-colors hover:border-wb-accent hover:text-wb-accent-text disabled:cursor-not-allowed disabled:opacity-40"
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
                      'inline-flex h-8 min-w-8 cursor-pointer items-center justify-center rounded-full border-0 px-2.5 text-[12.5px] font-semibold transition-colors',
                      p === page
                        ? 'bg-wb-accent text-white'
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
                  className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-wb-line bg-white text-slate-600 transition-colors hover:border-wb-accent hover:text-wb-accent-text disabled:cursor-not-allowed disabled:opacity-40"
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
