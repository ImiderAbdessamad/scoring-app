import { useState } from 'react'
import { motion } from 'framer-motion'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
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
}

const EMPTY_ATTENTION: ScoringAttention = {
  pointsForts: [],
  pointsVigilance: [],
  scoreFinal: '',
}

export function SyntheseTab({ scoring }: Props) {
  const tone = scoreTone(scoring.score, scoring.classe)
  const grade = classTone(scoring.classe)
  const ringStyle = {
    background: `conic-gradient(${tone.color} ${scoring.score * 3.6}deg, #EEF0F3 0deg)`,
  }

  return (
    <div className="flex flex-col gap-4">
      <AttentionCard attention={scoring.attention ?? EMPTY_ATTENTION} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
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

          <div className="mt-4 w-full border-t border-[#F1F2F4] pt-3.5">
            <GradeScale score={scoring.score} classe={scoring.classe} />
          </div>

          <div className="mt-4 grid w-full grid-cols-2 gap-2 border-t border-[#F1F2F4] pt-3.5 text-center">
            <MiniStat value={`${scoring.ratiosOk}/${scoring.ratiosTotal}`} label="Ratios conformes" />
            <MiniStat value={`${scoring.dossierCompletenessPct}%`} label="Postes extraits" />
          </div>
        </Card>

        <Card delay={0.1} className="p-5">
          <div className="mb-1 text-[13px] font-bold text-slate-900">Synthèse de l’analyse</div>
          <p className="m-0 mb-4 text-[12.5px] leading-relaxed text-wb-muted">{scoring.summary}</p>

          <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.04em] text-wb-faint">
            Facteurs déterminants du score
          </div>
          <div className="flex flex-col gap-2.5">
            {scoring.factors.map((factor, i) => {
              const positive = factor.impact >= 0
              const width = Math.min(100, Math.max(8, Math.abs(factor.impact) * 3.2))
              return (
                <div key={factor.label} className="flex items-center gap-3">
                  <div className="w-[190px] flex-none truncate text-[12px] text-slate-700">{factor.label}</div>
                  <div className="relative h-2 flex-1 overflow-hidden rounded-md bg-[#EEF0F3]">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${width}%` }}
                      transition={{ delay: 0.15 + i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                      className="h-full rounded-md"
                      style={{ background: positive ? '#16A34A' : '#DC2626' }}
                    />
                  </div>
                  <div
                    className="w-[52px] flex-none text-right text-[12px] font-bold tabular-nums"
                    style={{ color: positive ? '#15803D' : '#DC2626' }}
                  >
                    {formatImpactPct(factor.impact)}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <Card delay={0.15} className="p-5">
        <div className="mb-0.5 text-[13px] font-bold text-slate-900">Évolution financière</div>
        <p className="m-0 mb-4 text-[11.5px] text-wb-faint">{scoring.trendCaption}</p>

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
                  color="#15110E"
                  delay={0.2 + i * 0.1}
                />
                <TrendBar
                  label={year.rnLabel ?? '—'}
                  pct={year.rnHeightPct}
                  color="#E85D0C"
                  delay={0.26 + i * 0.1}
                />
              </div>
              <span className="text-[12px] font-bold text-slate-700">{year.year}</span>
            </div>
          ))}
        </div>

        <div className="mt-2 flex justify-center gap-5 border-t border-[#F1F2F4] pt-3">
          <Legend color="#15110E" label="Chiffre d’affaires" />
          <Legend color="#E85D0C" label="Résultat net (KDH)" />
        </div>
      </Card>
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
        className="w-7 rounded-t-md"
        style={{ background: missing ? '#E2E8F0' : color }}
      />
    </div>
  )
}

function GradeScale({ score, classe }: { score: number; classe?: string }) {
  const grade = classTone(classe)
  return (
    <div className="flex w-full flex-col gap-1.5">
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-gradient-to-r from-[#DC2626] via-[#B45309] to-[#15803D]">
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

function formatImpactPct(value: number): string {
  const abs = Math.abs(value)
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(1).replace('.', ',')
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${body} %`
}

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
    <div className="flex items-center gap-1.5 text-[11px] text-wb-muted">
      <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
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
        className="flex w-full cursor-pointer items-center gap-2.5 border-0 bg-transparent px-5 py-3.5 text-left"
      >
        <span className="h-4 w-[3px] flex-none rounded-full bg-wb-accent" />
        <span className="flex-1 text-[13.5px] font-bold text-slate-900">
          Synthèse et points d&apos;attention
        </span>
        {open ? (
          <ChevronUp size={16} className="text-wb-faint" />
        ) : (
          <ChevronDown size={16} className="text-wb-faint" />
        )}
      </button>

      {open && (
        <div className="border-t border-[#F1F2F4] px-5 pb-4">
          <AttentionSection title="POINTS FORTS" items={attention.pointsForts} />
          <AttentionSection title="POINTS DE VIGILANCE" items={attention.pointsVigilance} />
          <div className="border-t border-[#F1F2F4] py-3.5">
            <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-wb-faint">
              Score final
            </div>
            <p className="m-0 text-[12.5px] leading-relaxed text-slate-700">
              {attention.scoreFinal || '—'}
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}

function AttentionSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="border-t border-[#F1F2F4] py-3.5 first:border-t-0">
      <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-wb-faint">
        {title}
      </div>
      {items.length === 0 ? (
        <p className="m-0 text-[12.5px] text-slate-500">—</p>
      ) : (
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-4 text-[12.5px] leading-relaxed text-slate-700">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
