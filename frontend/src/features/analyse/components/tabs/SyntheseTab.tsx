import { useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, ChevronDown, TriangleAlert } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { SHOW_SCORE } from '@/config/env'
import { classTone, scoreTone } from '@/lib/format'
import type { ScoringAttention, ScoringBlock } from '@/types/analyse'

const TREND_TRACK = 140

const GRADE_SCALE = [
  { letter: 'D/F' },
  { letter: 'C' },
  { letter: 'B/B-' },
  { letter: 'A/B+' },
  { letter: 'A+' },
]

type Props = {
  scoring: ScoringBlock
  /** Contenu placé en tête de la colonne de droite (données extraites). */
  aside?: ReactNode
}

const EMPTY_ATTENTION: ScoringAttention = {
  pointsForts: [],
  pointsVigilance: [],
  scoreFinal: '',
}

export function SyntheseTab({ scoring, aside }: Props) {
  const tone = scoreTone(scoring.score, scoring.classe)
  const grade = classTone(scoring.classe)
  const ringStyle = {
    background: `conic-gradient(${tone.color} ${scoring.score * 3.6}deg, #EEF0F3 0deg)`,
  }

  return (
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
      <AttentionCard attention={scoring.attention ?? EMPTY_ATTENTION} />

        {SHOW_SCORE && (
        <Card delay={0.05} className="flex flex-col items-center p-5 text-center">
          <div className="relative flex h-[148px] w-[148px] items-center justify-center rounded-full" style={ringStyle}>
            <div className="flex h-[118px] w-[118px] flex-col items-center justify-center rounded-full bg-white">
              <span className="font-mono text-[36px] font-extrabold leading-none tabular-nums" style={{ color: tone.color }}>
                {(scoring.scoreRaw ?? scoring.score).toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
              </span>
              <span className="mt-1 text-[10.5px] font-semibold uppercase tracking-[0.04em] text-wb-faint">
                / 100
              </span>
            </div>
          </div>

          <span
            className="mt-3.5 inline-flex items-center justify-center rounded-full px-3 py-1 text-[13px] font-extrabold"
            style={{ color: grade.color, background: grade.bg }}
          >
            Note {scoring.classe || grade.letter} · {scoring.provisional ? 'Provisoire' : 'Final'}
          </span>

          <div className="mt-3 text-[13px] font-bold text-slate-900">{scoring.recommendation}</div>
          <div className="mt-1 text-[12px] text-wb-muted">{scoring.riskLabel}</div>

          <div className="mt-4 w-full border-t border-wb-line pt-3.5">
            <GradeScale score={scoring.score} classe={scoring.classe} />
          </div>

          <div className="mt-4 grid w-full grid-cols-2 gap-2 border-t border-wb-line pt-3.5 text-center">
            <MiniStat value={`${scoring.ratiosOk}/${scoring.ratiosTotal}`} label="Ratios conformes" />
            <MiniStat value={`${scoring.dossierCompletenessPct}%`} label="Postes extraits" />
          </div>
        </Card>
        )}

        {/* Masqué à la demande du métier — réactivable en décommentant (et formatImpactPct plus bas).
        <Card delay={0.1} className="p-6">
          <div className="mb-1.5 text-[16px] font-semibold text-[#1C1B1B]">Synthèse de l’analyse</div>
          <p className="m-0 mb-5 text-[13px] leading-relaxed text-[rgba(23,23,23,0.6)]">{scoring.summary}</p>

          {!SHOW_SCORE && (
            <div className="mb-4 grid max-w-[320px] grid-cols-2 gap-2 border-y border-wb-line py-3 text-center">
              <MiniStat value={`${scoring.ratiosOk}/${scoring.ratiosTotal}`} label="Ratios conformes" />
              <MiniStat value={`${scoring.dossierCompletenessPct}%`} label="Postes extraits" />
            </div>
          )}

          <div className="mb-3 text-[13.5px] font-semibold text-[#1C1B1B]">
            Facteurs déterminants du score
          </div>
          <div className="flex flex-col gap-2.5">
            {scoring.factors.map((factor, i) => {
              const positive = factor.impact >= 0
              const width = Math.min(100, Math.max(8, Math.abs(factor.impact) * 3.2))
              return (
                <div key={factor.label} className="flex items-center gap-3">
                  <div className="w-[190px] flex-none truncate text-[12.5px] text-slate-700">{factor.label}</div>
                  <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-[#EEF0F3]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${width}%` }}
                      transition={{ delay: 0.15 + i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                      className="h-full rounded-full"
                      style={{ background: positive ? '#16A34A' : '#DB2424' }}
                    />
                  </div>
                  <div
                    className="w-[52px] flex-none text-right text-[12px] font-bold tabular-nums"
                    style={{ color: positive ? '#15803D' : '#DB2424' }}
                  >
                    {formatImpactPct(factor.impact)}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
        */}

      <Card delay={0.15} className="p-6">
        <div className="mb-1 text-[16px] font-semibold text-[#1C1B1B]">Évolution financière</div>
        <p className="m-0 mb-4 text-[12px] text-wb-muted">{scoring.trendCaption}</p>

        <div className="flex items-end justify-around gap-6 px-4 pb-1 pt-2">
          {scoring.trend.length === 0 && (
            <div className="flex h-[168px] w-full items-center justify-center text-[12.5px] text-wb-muted">
              Les barres CA / résultat net s’affichent après l’extraction.
            </div>
          )}
          {scoring.trend.map((year, i) => (
            <div key={`${year.year}-${i}`} className="flex min-w-[96px] flex-1 flex-col items-center gap-2">
              <div className="flex items-end justify-center gap-2" style={{ height: TREND_TRACK }}>
                <TrendBar
                  label={year.caLabel}
                  pct={year.caHeightPct}
                  color="#0D0D0D"
                  delay={0.2 + i * 0.1}
                />
                <TrendBar
                  label={year.rnLabel ?? '—'}
                  pct={year.rnHeightPct}
                  color="#FF9B26"
                  delay={0.26 + i * 0.1}
                />
              </div>
              <span className="text-[12px] font-bold text-slate-700">{year.year}</span>
            </div>
          ))}
        </div>

        <div className="mt-2 flex flex-wrap justify-center gap-x-5 gap-y-1 border-t border-wb-line pt-3">
          <Legend color="#0D0D0D" label="Chiffre d’affaires" />
          <Legend color="#FF9B26" label="Résultat net (KDH)" />
        </div>
      </Card>
      </div>

      <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4">
      {aside}

      </div>
    </div>
  )
}

function TrendBar({
  label,
  pct,
  color,
  delay,
}: {
  label: string
  pct: number
  color: string
  delay: number
}) {
  const missing = !label || label === '—'
  const labelSpace = 22
  const maxBar = TREND_TRACK - labelSpace
  const height = missing ? 4 : Math.max(8, Math.round((Math.min(100, Math.max(0, pct)) / 100) * maxBar))
  return (
    <div className="flex w-10 flex-col items-center justify-end" style={{ height: TREND_TRACK }}>
      <span
        className="mb-1 max-w-[76px] truncate text-center text-[10.5px] font-bold tabular-nums"
        style={{ color: missing ? '#94A3B8' : color }}
        title={label}
      >
        {label}
      </span>
      <motion.div
        initial={{ height: 0 }}
        animate={{ height }}
        transition={{ delay, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        className="w-7 rounded-t-[8px]"
        style={{ background: missing ? '#E2E8F0' : color }}
      />
    </div>
  )
}

function GradeScale({ score, classe }: { score: number; classe?: string }) {
  const grade = classTone(classe)
  return (
    <div className="flex w-full flex-col gap-1.5">
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-gradient-to-r from-[#DB2424] via-[#B45309] to-[#15803D]">
        <motion.div
          initial={{ left: 0 }}
          animate={{ left: `${Math.min(97, Math.max(1, score))}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-white bg-wb-ink shadow"
        />
      </div>
      <div className="flex justify-between">
        {GRADE_SCALE.map((g) => (
          <span
            key={g.letter}
            className="text-[9.5px] font-bold"
            style={{ color: g.letter === grade.letter ? grade.color : '#CBD3DC' }}
          >
            {g.letter}
          </span>
        ))}
      </div>
    </div>
  )
}

/* Utilisé par le bloc « Synthèse de l’analyse » (masqué).
function formatImpactPct(value: number): string {
  const abs = Math.abs(value)
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(1).replace('.', ',')
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${body} %`
}
*/

function MiniStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-[15px] font-extrabold tabular-nums text-slate-800">{value}</div>
      <div className="mt-0.5 text-[9.5px] uppercase tracking-[0.03em] text-wb-faint">{label}</div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[12px] text-wb-muted">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </div>
  )
}

function AttentionCard({ attention }: { attention: ScoringAttention }) {
  const [open, setOpen] = useState(true)

  return (
    <Card delay={0.02} className="overflow-hidden p-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-6 py-4 text-left"
      >
        <span className="h-5 w-[3px] flex-none rounded-full bg-wb-accent" />
        <span className="flex-1 text-[16px] font-semibold text-[#1C1B1B]">
          Synthèse et points d&apos;attention
        </span>
        <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
          <ChevronDown size={15} strokeWidth={2.4} className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {open && (
        <div className="border-t border-wb-line px-6 pb-5">
          <div className="grid grid-cols-1 gap-x-8 xl:grid-cols-2">
            <AttentionSection tone="ok" title="Points forts" items={attention.pointsForts} />
            <AttentionSection tone="warn" title="Points de vigilance" items={attention.pointsVigilance} />
          </div>
          {SHOW_SCORE && (
            <div className="border-t border-wb-line py-4">
              <span className="mb-2 inline-flex rounded-[8px] bg-wb-surface px-2 py-1 text-[11px] font-semibold text-slate-600">
                Score final
              </span>
              <p className="m-0 text-[12.5px] leading-relaxed text-slate-700">
                {attention.scoreFinal || '—'}
              </p>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

const ATTENTION_TONE = {
  ok: { tag: 'bg-[#ECFDF5] text-[#15803D]', icon: CheckCircle2, iconClass: 'text-[#16A34A]' },
  warn: { tag: 'bg-[#FFF8EC] text-[#B45309]', icon: TriangleAlert, iconClass: 'text-[#B45309]' },
} as const

function AttentionSection({
  tone,
  title,
  items,
}: {
  tone: keyof typeof ATTENTION_TONE
  title: string
  items: string[]
}) {
  const style = ATTENTION_TONE[tone]
  const Icon = style.icon
  return (
    <div className="min-w-0 pt-4">
      <span className={`mb-2.5 inline-flex rounded-[8px] px-2 py-1 text-[11px] font-semibold ${style.tag}`}>
        {title}
      </span>
      {items.length === 0 ? (
        <p className="m-0 text-[13px] text-slate-500">—</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-[13px] leading-relaxed text-slate-700">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <Icon size={15} strokeWidth={2} className={`mt-[3px] flex-none ${style.iconClass}`} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
