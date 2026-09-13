import { classTone, scoreTone } from '@/lib/format'

export function ScorePill({ score, classe }: { score: number; classe?: string | null }) {
  const tone = scoreTone(score, classe)
  const label = Number.isInteger(score) ? String(score) : score.toFixed(2).replace('.', ',')
  return (
    <span
      className="inline-flex min-w-[36px] items-center justify-center rounded-full px-2.5 py-0.5 font-mono text-[13px] font-extrabold tabular-nums"
      style={{ color: tone.color, background: tone.bg }}
    >
      {label}
    </span>
  )
}

export function GradeBadge({ score: _score, classe }: { score?: number; classe?: string | null }) {
  const g = classTone(classe)
  return (
    <span
      className="inline-flex min-w-[24px] items-center justify-center rounded-md px-1.5 py-0.5 text-[11px] font-extrabold"
      style={{ color: g.color, background: g.bg }}
    >
      {g.letter}
    </span>
  )
}
