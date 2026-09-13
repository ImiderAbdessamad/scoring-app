import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, Clock3 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { RatioStatus, RatiosBlock } from '@/types/analyse'

const STATUS_STYLE: Record<RatioStatus, { label: string; color: string; bg: string; bar: string }> = {
  GOOD: { label: 'Conforme', color: '#15803D', bg: '#ECFDF5', bar: '#16A34A' },
  WARN: { label: 'À surveiller', color: '#B45309', bg: '#FFF8EC', bar: '#B45309' },
  BAD: { label: 'Non conforme', color: '#DC2626', bg: '#FEF2F2', bar: '#DC2626' },
}

const FISCAL_TONE: Record<'neutral' | 'warn' | 'ok', string> = {
  neutral: '#111827',
  warn: '#B45309',
  ok: '#15803D',
}

type Props = {
  ratios: RatiosBlock
  openIndex: number | null
  onToggle: (index: number) => void
}

export function RatiosTab({ ratios, openIndex, onToggle }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-[11.5px] text-wb-faint">
            <Clock3 size={13} />
            Calculé en {ratios.calcTime}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-[12.5px] font-semibold text-[#15803D]">
              <span className="h-2 w-2 rounded-full bg-[#16A34A]" />
              {ratios.conformCount} conformes
            </div>
            <div className="flex items-center gap-1.5 text-[12.5px] font-semibold text-[#B45309]">
              <span className="h-2 w-2 rounded-full bg-[#B45309]" />
              {ratios.watchCount} à surveiller
            </div>
          </div>
        </div>

        {ratios.items.length === 0 && ratios.fiscal.length === 0 && (
          <div className="rounded-[10px] border border-dashed border-wb-line px-4 py-6 text-center text-[13px] text-wb-muted">
            Les ratios et graphiques s’affichent après l’extraction de la liasse.
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          {ratios.fiscal.map((f) => (
            <div key={f.label} className="rounded-[10px] border border-wb-line bg-wb-surface/60 p-2.5">
              <div className="truncate text-[10px] uppercase tracking-[0.03em] text-wb-faint">{f.label}</div>
              <div
                className="mt-1 truncate text-[13px] font-extrabold tabular-nums"
                style={{ color: FISCAL_TONE[f.tone] }}
              >
                {f.value}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card delay={0.1} className="overflow-hidden p-0">
        {ratios.items.length === 0 && (
          <div className="px-4 py-8 text-center text-[13px] text-wb-muted">Aucun ratio calculé pour l’instant.</div>
        )}
        {ratios.items.length > 0 && (
          <div className="hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1.6fr)_88px_100px_28px] gap-3 border-b border-[#F1F2F4] bg-[#FAFBFC] px-4 py-2 text-[10.5px] font-bold uppercase tracking-[0.03em] text-wb-faint sm:grid">
            <span>Ratio</span>
            <span>Formule · seuil</span>
            <span className="text-right">Valeur</span>
            <span className="text-right">Statut</span>
            <span />
          </div>
        )}
        {ratios.items.map((ratio, i) => {
          const style = STATUS_STYLE[ratio.status]
          const open = openIndex === i
          return (
            <div key={ratio.label} className="border-b border-[#F1F2F4] last:border-b-0">
              <button
                type="button"
                onClick={() => onToggle(i)}
                className="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-4 py-3 text-left transition-colors hover:bg-wb-surface/60"
              >
                <div className="min-w-0 flex-1 sm:grid sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1.6fr)] sm:items-center sm:gap-3">
                  <div className="text-[13px] font-bold text-slate-800">{ratio.label}</div>
                  <div className="truncate text-[10.5px] text-wb-faint">
                    {ratio.formula}
                    {ratio.threshold ? `  ·  ${ratio.threshold}` : ''}
                  </div>
                </div>
                <div className="hidden w-[120px] flex-none sm:block">
                  <div className="h-1.5 overflow-hidden rounded-full bg-[#EEF0F3]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${ratio.barPct}%` }}
                      transition={{ duration: 0.5, delay: 0.06 * i }}
                      className="h-full rounded-full"
                      style={{ background: style.bar }}
                    />
                  </div>
                </div>
                <span className="w-[64px] flex-none text-right font-mono text-[13.5px] font-extrabold tabular-nums text-slate-900">
                      {ratio.value}
                </span>
                <span
                  className="flex-none whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold"
                  style={{ color: style.color, background: style.bg }}
                >
                  {style.label}
                </span>
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
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="bg-wb-surface/50 px-4 py-3 text-[12.5px] leading-relaxed text-wb-muted">
                      {ratio.interpretation}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </Card>
    </div>
  )
}
