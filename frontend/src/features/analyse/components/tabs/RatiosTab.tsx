import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { RatioStatus, RatiosBlock } from '@/types/analyse'

const STATUS_STYLE: Record<RatioStatus, { label: string; color: string; bg: string; bar: string }> = {
  GOOD: { label: 'Conforme', color: '#15803D', bg: '#ECFDF5', bar: '#16A34A' },
  WARN: { label: 'À surveiller', color: '#B45309', bg: '#FFF8EC', bar: '#B45309' },
  BAD: { label: 'Non conforme', color: '#B91C1C', bg: '#FEF2F2', bar: '#DB2424' },
}

const FISCAL_TONE: Record<'neutral' | 'warn' | 'ok', string> = {
  neutral: '#1C1B1B',
  warn: '#B45309',
  ok: '#15803D',
}

type Filter = 'ALL' | RatioStatus

const FILTERS: Array<{ key: Filter; label: string }> = [
  { key: 'ALL', label: 'Tous' },
  { key: 'GOOD', label: 'Conformes' },
  { key: 'WARN', label: 'À surveiller' },
  { key: 'BAD', label: 'Non conformes' },
]

/* Colonnes communes à l'en-tête et aux lignes : ratio | jauge | valeur | statut | ▾ */
const ROW_GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_120px_96px_120px_28px] sm:items-center sm:gap-4'

type Props = {
  ratios: RatiosBlock
  openIndex: number | null
  onToggle: (index: number) => void
}

export function RatiosTab({ ratios, openIndex, onToggle }: Props) {
  const [filter, setFilter] = useState<Filter>('ALL')
  const counts: Record<Filter, number> = {
    ALL: ratios.items.length,
    GOOD: ratios.items.filter((r) => r.status === 'GOOD').length,
    WARN: ratios.items.filter((r) => r.status === 'WARN').length,
    BAD: ratios.items.filter((r) => r.status === 'BAD').length,
  }
  // L'index d'origine est conservé : l'ouverture d'un ratio reste pilotée par la page.
  const visible = ratios.items
    .map((ratio, index) => ({ ratio, index }))
    .filter(({ ratio }) => filter === 'ALL' || ratio.status === filter)

  if (ratios.items.length === 0 && ratios.fiscal.length === 0) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Les ratios s’affichent après l’extraction de la liasse.
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-[16px] font-semibold text-[#1C1B1B]">Ratios financiers</div>
          <div className="flex flex-wrap gap-2">
            <CountTag count={counts.GOOD} status="GOOD" />
            <CountTag count={counts.WARN} status="WARN" />
            <CountTag count={counts.BAD} status="BAD" />
          </div>
        </div>

        {ratios.fiscal.length > 0 && (
          <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-wb-line pt-5 sm:grid-cols-3 lg:grid-cols-6">
            {ratios.fiscal.map((f) => (
              <div key={f.label} className="min-w-0">
                <div className="truncate text-[12px] text-wb-muted">{f.label}</div>
                <div
                  className="mt-1 truncate text-[18px] font-bold tabular-nums tracking-[-0.01em]"
                  style={{ color: FISCAL_TONE[f.tone] }}
                >
                  {f.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {ratios.items.length > 0 && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filtrer les ratios">
          {FILTERS.map((item) => {
            const selected = filter === item.key
            return (
              <button
                key={item.key}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setFilter(item.key)}
                className={[
                  'inline-flex cursor-pointer items-center gap-2 rounded-full border-0 px-4 py-2 text-[13px] font-semibold transition-colors',
                  selected ? 'bg-wb-ink text-white' : 'bg-white text-slate-600 ring-1 ring-wb-line hover:bg-wb-surface',
                ].join(' ')}
              >
                {item.label}
                <span
                  className={[
                    'inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-px text-[11px] font-bold tabular-nums',
                    selected ? 'bg-wb-accent text-white' : 'bg-wb-surface text-wb-muted',
                  ].join(' ')}
                >
                  {counts[item.key]}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {ratios.items.length > 0 && (
        <Card delay={0.1} className="overflow-hidden p-0">
          <div className={`hidden border-b border-wb-line bg-[#F8FAFC] px-6 py-3 text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted ${ROW_GRID}`}>
            <span>Ratio · formule · seuil</span>
            <span />
            <span className="text-right">Valeur</span>
            <span>Statut</span>
            <span />
          </div>

          {visible.length === 0 && (
            <div className="px-6 py-8 text-center text-[13px] text-wb-muted">Aucun ratio dans cette catégorie.</div>
          )}

          {visible.map(({ ratio, index }, position) => {
            const style = STATUS_STYLE[ratio.status]
            const open = openIndex === index
            return (
              <div key={ratio.label} className="border-b border-wb-line last:border-b-0">
                <button
                  type="button"
                  onClick={() => onToggle(index)}
                  aria-expanded={open}
                  className={`group flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-6 py-3.5 text-left transition-colors hover:bg-wb-accent-soft/40 ${ROW_GRID}`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[13.5px] font-semibold text-[#1C1B1B]">{ratio.label}</div>
                    <div className="mt-0.5 truncate text-[11px] text-wb-faint">
                      {ratio.formula}
                      {ratio.threshold ? ` · ${ratio.threshold}` : ''}
                    </div>
                  </div>
                  <div className="hidden sm:block">
                    <div className="h-2 overflow-hidden rounded-full bg-[#EEF0F3]">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${ratio.barPct}%` }}
                        transition={{ duration: 0.5, delay: 0.04 * position }}
                        className="h-full rounded-full"
                        style={{ background: style.bar }}
                      />
                    </div>
                  </div>
                  <span className="flex-none text-right font-mono text-[14px] font-bold tabular-nums text-[#1C1B1B]">
                    {ratio.value}
                  </span>
                  <span>
                    <span
                      className="inline-flex whitespace-nowrap rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold"
                      style={{ color: style.color, background: style.bg }}
                    >
                      {style.label}
                    </span>
                  </span>
                  <span
                    className={`flex h-7 w-7 flex-none items-center justify-center rounded-full transition-colors ${
                      open ? 'bg-wb-accent text-white' : 'bg-wb-surface text-wb-muted group-hover:bg-wb-accent group-hover:text-white'
                    }`}
                  >
                    <ChevronDown size={15} strokeWidth={2.2} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {open && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="mx-6 mb-4 rounded-[14px] border-l-2 border-wb-accent bg-wb-surface px-4 py-3 text-[13px] leading-relaxed text-slate-700">
                        {ratio.interpretation}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </Card>
      )}
    </div>
  )
}

function CountTag({ count, status }: { count: number; status: RatioStatus }) {
  const style = STATUS_STYLE[status]
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[12px] font-semibold"
      style={{ color: style.color, background: style.bg }}
    >
      <span className="font-bold tabular-nums">{count}</span>
      {style.label.toLowerCase()}
    </span>
  )
}
