import { motion } from 'framer-motion'
import { CheckCircle2, TriangleAlert } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { scoreTone } from '@/lib/format'
import type { BehaviourBlock } from '@/types/analyse'

const TONE_STYLE = {
  ok: { color: '#15803D', bg: '#ECFDF5' },
  warn: { color: '#B45309', bg: '#FFF8EC' },
  neutral: { color: '#111827', bg: '#F4F5F6' },
}

type Props = {
  comportement: BehaviourBlock
}

export function ComportementTab({ comportement }: Props) {
  const tone = scoreTone(comportement.score)
  const maxMonth = Math.max(...comportement.months.map((m) => m.valueK), 1)

  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[13px] font-bold text-slate-900">Score comportemental</div>
            <div className="mt-0.5 text-[12px] text-wb-muted">{comportement.profileLabel}</div>
          </div>
          <div
            className="flex h-14 w-14 items-center justify-center rounded-full font-mono text-[20px] font-extrabold tabular-nums"
            style={{ color: tone.color, background: tone.bg }}
          >
            {comportement.score}
          </div>
        </div>
        <p className="m-0 mt-3 border-t border-[#F1F2F4] pt-3 text-[12.5px] leading-relaxed text-wb-muted">
          {comportement.summary}
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {comportement.metrics.map((m, i) => {
          const t = TONE_STYLE[m.tone]
          return (
            <Card key={m.label} delay={0.08 + i * 0.04} className="p-4">
              <div className="text-[10.5px] uppercase tracking-[0.03em] text-wb-faint">{m.label}</div>
              <div className="mt-1.5 text-[19px] font-extrabold tabular-nums" style={{ color: t.color }}>
                {m.value}
              </div>
              <div className="mt-1 text-[11px] text-wb-faint">{m.sub}</div>
            </Card>
          )
        })}
      </div>

      <Card delay={0.2} className="p-5">
        <div className="mb-4 text-[13px] font-bold text-slate-900">
          Évolution du solde bancaire (12 mois)
        </div>
        {comportement.months.length === 0 ? (
          <div className="rounded-[10px] border border-dashed border-wb-line px-4 py-8 text-center text-[12.5px] text-wb-muted">
            Relevés bancaires non extraits — l’axe comportemental (15 %) n’entre pas dans la note globale.
          </div>
        ) : (
        <div className="flex items-end justify-between gap-1.5" style={{ height: 140 }}>
          {comportement.months.map((m, i) => (
            <div key={m.label} className="flex flex-1 flex-col items-center gap-1.5">
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(6, (m.valueK / maxMonth) * 100)}%` }}
                transition={{ delay: 0.02 * i, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-[22px] rounded-t-[4px] bg-wb-accent/80"
              />
              <span className="text-[9.5px] text-wb-faint">{m.label}</span>
            </div>
          ))}
        </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {comportement.signals.map((s) => (
          <div
            key={s.title}
            className={[
              'flex items-start gap-2.5 rounded-[12px] border p-3.5',
              s.tone === 'ok' ? 'border-[#BBF7D0] bg-[#ECFDF5]' : 'border-[#F7D9B8] bg-[#FFF8EC]',
            ].join(' ')}
          >
            {s.tone === 'ok' ? (
              <CheckCircle2 size={16} className="mt-0.5 flex-none text-[#15803D]" />
            ) : (
              <TriangleAlert size={16} className="mt-0.5 flex-none text-[#B45309]" />
            )}
            <div className="min-w-0">
              <div
                className="text-[12.5px] font-bold"
                style={{ color: s.tone === 'ok' ? '#15803D' : '#92400E' }}
              >
                {s.title}
              </div>
              <div className="mt-0.5 text-[11.5px] leading-relaxed text-wb-muted">{s.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
