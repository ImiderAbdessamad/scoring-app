import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { FactorAxis, RatioStatus } from '@/types/analyse'

const STATUS_STYLE: Record<RatioStatus, { color: string; bg: string }> = {
  GOOD: { color: '#15803D', bg: '#ECFDF5' },
  WARN: { color: '#B45309', bg: '#FFF8EC' },
  BAD: { color: '#DC2626', bg: '#FEF2F2' },
}

const VARIATION_STYLE = {
  up: { color: '#15803D', icon: TrendingUp },
  flat: { color: '#B45309', icon: Minus },
  down: { color: '#DC2626', icon: TrendingDown },
}

type Props = {
  axes: FactorAxis[]
  openAxis: number
  onToggle: (index: number) => void
}

export function FactorielleTab({ axes, openAxis, onToggle }: Props) {
  if (!axes.length) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Les axes factoriels apparaissent après l’extraction de la liasse.
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      {axes.map((axis, i) => {
        const open = openAxis === i
        return (
          <Card key={axis.num} delay={0.04 * i} className="overflow-hidden p-0">
            <button
              type="button"
              onClick={() => onToggle(i)}
              className="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-5 py-3.5 text-left transition-colors hover:bg-wb-surface/60"
            >
              <span className="flex h-8 w-8 flex-none items-center justify-center rounded-[9px] bg-wb-ink text-[11px] font-extrabold text-wb-accent">
                {axis.num}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-bold text-slate-900">{axis.title}</div>
                <div className="text-[10.5px] text-wb-faint">Unité : {axis.unit}</div>
              </div>
              <div className="hidden items-center gap-1.5 sm:flex">
                {axis.ratios.map((r) => (
                  <span
                    key={r.label}
                    className="rounded-full px-2 py-1 text-[10.5px] font-bold"
                    style={{ color: STATUS_STYLE[r.status].color, background: STATUS_STYLE[r.status].bg }}
                  >
                    {r.value}
                  </span>
                ))}
              </div>
              <ChevronDown
                size={16}
                className={`flex-none text-wb-faint transition-transform ${open ? 'rotate-180' : ''}`}
              />
            </button>

            <AnimatePresence initial={false}>
              {open && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22 }}
                  className="overflow-hidden border-t border-[#F1F2F4]"
                >
                  <div className="wb-scroll overflow-x-auto">
                    <table className="w-full min-w-[480px] border-collapse text-[12.5px]">
                      <thead>
                        <tr className="bg-[#FAFBFC] text-left text-[10.5px] font-bold uppercase tracking-[0.03em] text-wb-faint">
                          <th className="px-5 py-2.5">Indicateur</th>
                          {(axis.yearLabels ?? ['—', 'N-1', 'N']).map((label, idx) => (
                            <th key={`${label}-${idx}`} className="px-3 py-2.5 text-right">
                              {label}
                            </th>
                          ))}
                          <th className="px-5 py-2.5 text-right">Variation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {axis.rows.map((row) => {
                          const v = VARIATION_STYLE[row.variationTone]
                          const VIcon = v.icon
                          return (
                            <tr key={row.label} className="border-t border-[#F1F2F4]">
                              <td className="px-5 py-2.5 font-semibold text-slate-800">{row.label}</td>
                              <td className="px-3 py-2.5 text-right tabular-nums text-wb-muted">{row.y1}</td>
                              <td className="px-3 py-2.5 text-right tabular-nums text-wb-muted">{row.y2}</td>
                              <td className="px-3 py-2.5 text-right font-bold tabular-nums text-slate-900">{row.y3}</td>
                              <td className="px-5 py-2.5 text-right">
                                <span
                                  className="inline-flex items-center gap-1 font-bold tabular-nums"
                                  style={{ color: v.color }}
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
                  <div className="flex flex-wrap gap-2 px-5 py-3.5">
                    {axis.ratios.map((r) => (
                      <span
                        key={r.label}
                        title={[r.formula, r.threshold].filter(Boolean).join(' · ')}
                        className="inline-flex max-w-full flex-col items-start gap-0.5 rounded-[10px] px-2.5 py-1.5 text-[11.5px] font-semibold"
                        style={{ color: STATUS_STYLE[r.status].color, background: STATUS_STYLE[r.status].bg }}
                      >
                        <span>
                          {r.label} · {r.value}
                        </span>
                        {r.threshold ? (
                          <span className="text-[10px] font-medium opacity-80">Seuil {r.threshold}</span>
                        ) : null}
                      </span>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        )
      })}
    </div>
  )
}
