import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Landmark, TriangleAlert, X } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { scoreTone } from '@/lib/format'
import type { BehaviourBlock } from '@/types/analyse'

const TONE_COLOR = {
  ok: '#15803D',
  warn: '#B45309',
  neutral: '#1C1B1B',
}

type Props = {
  comportement: BehaviourBlock
}

export function BankingBehaviorTab(props: Props) {
  return <ComportementTab {...props} />
}

/** Comportement bancaire : synthèse et indicateurs, évolution du solde, signaux relevés. */
export function ComportementTab({ comportement }: Props) {
  const available = comportement.available !== false && comportement.score != null
  const tone = scoreTone(typeof comportement.score === 'number' ? comportement.score : undefined)
  const maxMonth = Math.max(...comportement.months.map((m) => m.valueK), 1)
  const lastIndex = comportement.months.length - 1

  return (
    <div className="flex flex-col gap-4">
      <NextPhaseNotice />
      <Card delay={0.05} className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[16px] font-semibold text-[#1C1B1B]">Comportement bancaire</div>
            <div className="mt-0.5 text-[12.5px] text-wb-muted">{comportement.profileLabel}</div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[12px] text-wb-muted">Score comportemental</span>
            <span
              className="flex h-12 w-12 items-center justify-center rounded-full text-[17px] font-bold tabular-nums"
              style={{ color: tone.color, background: tone.bg }}
            >
              {available ? comportement.score : '—'}
            </span>
          </div>
        </div>
        <p className="m-0 mt-4 border-l-2 border-wb-accent pl-3 text-[13px] leading-relaxed text-slate-600">
          {available
            ? comportement.summary
            : 'Analyse comportementale non disponible : aucun relevé bancaire n’a encore été analysé.'}
        </p>

        {comportement.metrics.length > 0 && (
          <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-wb-line pt-5 lg:grid-cols-4">
            {comportement.metrics.map((m) => (
              <div key={m.label} className="min-w-0">
                <div className="truncate text-[12px] text-wb-muted">{m.label}</div>
                <div className="mt-1 truncate text-[20px] font-bold tabular-nums tracking-[-0.01em]" style={{ color: TONE_COLOR[m.tone] }}>
                  {m.value}
                </div>
                <div className="mt-0.5 truncate text-[11.5px] text-wb-faint">{m.sub}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card delay={0.12} className="p-6">
        <div className="mb-4 text-[16px] font-semibold text-[#1C1B1B]">Évolution du solde bancaire (12 mois)</div>
        {comportement.months.length === 0 ? (
          <div className="rounded-[14px] border border-dashed border-wb-line px-4 py-8 text-center text-[13px] text-wb-muted">
            Relevés bancaires non disponibles pour ce dossier.
          </div>
        ) : (
          <div className="flex items-end justify-between gap-2" style={{ height: 160 }}>
            {comportement.months.map((m, i) => (
              <div key={m.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5" title={`${m.label} : ${m.valueK} K`}>
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: `${Math.max(6, (m.valueK / maxMonth) * 100)}%` }}
                  transition={{ delay: 0.02 * i, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                  className={`w-full max-w-[26px] rounded-t-[8px] ${i === lastIndex ? 'bg-wb-accent' : 'bg-wb-ink'}`}
                />
                <span className="text-[10.5px] text-wb-muted">{m.label}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {comportement.signals.length > 0 && (
        <Card delay={0.18} className="p-6">
          <div className="mb-2 text-[16px] font-semibold text-[#1C1B1B]">Signaux relevés</div>
          {comportement.signals.map((s) => (
            <div key={s.title} className="flex items-start gap-3 border-t border-wb-line py-3 first:border-t-0">
              <span
                className={`mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full text-white ${
                  s.tone === 'ok' ? 'bg-[#16A34A]' : 'bg-[#B45309]'
                }`}
              >
                {s.tone === 'ok' ? <Check size={13} strokeWidth={3} /> : <TriangleAlert size={12} strokeWidth={2.4} />}
              </span>
              <div className="min-w-0">
                <div className="text-[13.5px] font-semibold text-[#1C1B1B]">{s.title}</div>
                <div className="mt-0.5 text-[12.5px] leading-relaxed text-wb-muted">{s.detail}</div>
              </div>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}

const NOTICE_DURATION_MS = 7000

/** Message affiché à chaque ouverture de l'onglet : l'intégration des relevés bancaires arrive. */
function NextPhaseNotice() {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), NOTICE_DURATION_MS)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ type: 'spring', stiffness: 380, damping: 30 }}
          className="fixed bottom-6 right-6 z-50 w-[min(360px,calc(100vw-48px))] overflow-hidden rounded-[20px] bg-wb-ink text-white shadow-[0_18px_40px_rgba(13,13,13,0.3)]"
        >
          <div className="flex items-start gap-3 p-4">
            <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
              <Landmark size={16} strokeWidth={1.9} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-semibold">Prochaine phase : relevés bancaires</div>
              <p className="m-0 mt-1 text-[12.5px] leading-relaxed text-white/75">
                L’intégration des relevés bancaires permettra de compléter automatiquement cette section :
                solde mensuel, incidents et signaux de comportement.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setVisible(false)}
              aria-label="Fermer le message"
              className="flex h-7 w-7 flex-none cursor-pointer items-center justify-center rounded-full border-0 bg-white/10 text-white/80 transition-colors hover:bg-white/20 hover:text-white"
            >
              <X size={14} strokeWidth={2.2} />
            </button>
          </div>
          {/* Barre de temps restant avant la fermeture automatique */}
          <motion.div
            initial={{ width: '100%' }}
            animate={{ width: 0 }}
            transition={{ duration: NOTICE_DURATION_MS / 1000, ease: 'linear' }}
            className="h-[3px] bg-wb-accent"
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
