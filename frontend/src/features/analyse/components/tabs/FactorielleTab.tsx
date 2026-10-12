import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { FactorAxis, RatioStatus } from '@/types/analyse'

const STATUS_STYLE: Record<RatioStatus, { label: string; color: string; bg: string }> = {
  GOOD: { label: 'Conforme', color: '#15803D', bg: '#ECFDF5' },
  WARN: { label: 'À surveiller', color: '#B45309', bg: '#FFF8EC' },
  BAD: { label: 'Non conforme', color: '#B91C1C', bg: '#FEF2F2' },
}

const VARIATION_STYLE = {
  up: { color: '#15803D', bg: '#ECFDF5', icon: TrendingUp },
  flat: { color: '#B45309', bg: '#FFF8EC', icon: Minus },
  down: { color: '#B91C1C', bg: '#FEF2F2', icon: TrendingDown },
}

type Props = {
  axes: FactorAxis[]
  openAxis: number
  onToggle: (index: number) => void
}

/** Tendances : un accordéon par axe d'analyse (évolution sur les exercices + ratios de l'axe). */
export function FactorielleTab({ axes, openAxis, onToggle }: Props) {
  if (!axes.length) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Les tendances apparaissent après l’extraction de la liasse.
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      {axes.map((axis, i) => {
        const open = openAxis === i
        return (
          <Card key={axis.num} delay={0.04 * i} className="overflow-hidden p-0">
            <button
              type="button"
              onClick={() => onToggle(i)}
              aria-expanded={open}
              className="group flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-6 py-4 text-left transition-colors hover:bg-wb-accent-soft/40"
            >
              <span
                className={`flex h-9 w-9 flex-none items-center justify-center rounded-full text-[12px] font-bold ${
                  open ? 'bg-wb-accent text-white' : 'bg-wb-ink text-white'
                }`}
              >
                {axis.num}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[16px] font-semibold text-[#1C1B1B]">{axis.title}</div>
                <div className="text-[11.5px] text-wb-muted">Unité : {axis.unit}</div>
              </div>
              <div className="hidden flex-wrap items-center justify-end gap-1.5 md:flex">
                {axis.ratios.map((r) => (
                  <span
                    key={r.label}
                    title={r.label}
                    className="rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums"
                    style={{ color: STATUS_STYLE[r.status].color, background: STATUS_STYLE[r.status].bg }}
                  >
                    {r.value}
                  </span>
                ))}
              </div>
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
                  transition={{ duration: 0.22 }}
                  className="overflow-hidden"
                >
                  <div className="wb-scroll overflow-x-auto">
                    <table className="w-full min-w-[520px] border-collapse text-[13px]">
                      <thead className="bg-[#F8FAFC]">
                        <tr className="text-left text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
                          <th className="border-y border-wb-line px-6 py-3">Indicateur</th>
                          {(axis.yearLabels ?? ['—', 'N-1', 'N']).map((label, idx) => (
                            <th key={`${label}-${idx}`} className="border-y border-wb-line px-3 py-3 text-right">
                              {label}
                            </th>
                          ))}
                          <th className="border-y border-wb-line px-6 py-3 text-right">Variation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {axis.rows.map((row) => {
                          const v = VARIATION_STYLE[row.variationTone]
                          const VIcon = v.icon
                          return (
                            <tr key={row.label} className="border-b border-wb-line transition-colors hover:bg-wb-accent-soft/40">
                              <td className="px-6 py-3 font-semibold text-[#1C1B1B]">{row.label}</td>
                              <td className="px-3 py-3 text-right tabular-nums text-wb-muted">{row.y1}</td>
                              <td className="px-3 py-3 text-right tabular-nums text-wb-muted">{row.y2}</td>
                              <td className="px-3 py-3 text-right font-bold tabular-nums text-[#1C1B1B]">{row.y3}</td>
                              <td className="px-6 py-3 text-right">
                                <span
                                  className="inline-flex items-center gap-1 rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums"
                                  style={{ color: v.color, background: v.bg }}
                                >
                                  <VIcon size={12} />
                                  {row.variation}
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {axis.ratios.length > 0 && (
                    <div className="px-6 py-4">
                      <div className="mb-1 text-[13.5px] font-semibold text-[#1C1B1B]">Ratios de l’axe</div>
                      {axis.ratios.map((r) => (
                        <div key={r.label} className="flex items-center justify-between gap-4 border-t border-wb-line py-2.5 first:border-t-0">
                          <div className="min-w-0">
                            <div className="text-[13px] text-slate-700">{r.label}</div>
                            {(r.formula || r.threshold) && (
                              <div className="mt-0.5 truncate text-[11px] text-wb-faint">
                                {[r.formula, r.threshold ? `Seuil ${r.threshold}` : null].filter(Boolean).join(' · ')}
                              </div>
                            )}
                          </div>
                          <div className="flex flex-none items-center gap-3">
                            <span className="font-mono text-[13.5px] font-bold tabular-nums text-[#1C1B1B]">{r.value}</span>
                            <span
                              className="rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold"
                              style={{ color: STATUS_STYLE[r.status].color, background: STATUS_STYLE[r.status].bg }}
                            >
                              {STATUS_STYLE[r.status].label}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        )
      })}
    </div>
  )
}
