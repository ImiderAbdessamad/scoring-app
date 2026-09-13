import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ChevronRight, Layers, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { ScorePill } from '@/components/ui/ScorePill'
import type { BenchmarkBlock } from '@/types/analyse'

type Props = {
  benchmark: BenchmarkBlock
}

export function BenchmarkTab({ benchmark }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-wb-accent-soft text-wb-accent">
              <Layers size={16} strokeWidth={1.8} />
            </span>
            <div>
              <div className="text-[13px] font-bold text-slate-900">
                Secteur {benchmark.sectorLabel} · {benchmark.sampleSize} dossiers
              </div>
              <div className="text-[11.5px] text-wb-faint">{benchmark.caption}</div>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF5] px-3 py-1.5 text-[12px] font-bold text-[#15803D]">
            <TrendingUp size={13} />
            {benchmark.aboveMedianLabel}
          </span>
        </div>
      </Card>

      <Card delay={0.1} className="p-5">
        <div className="mb-4 text-[13px] font-bold text-slate-900">Positionnement vs médiane sectorielle</div>
        <div className="flex flex-col gap-4">
          {benchmark.rows.length === 0 && (
            <div className="rounded-[10px] border border-dashed border-wb-line px-4 py-6 text-center text-[13px] text-wb-muted">
              Le benchmark sectoriel s’affiche après le calcul des ratios.
            </div>
          )}
          {benchmark.rows.map((row, i) => (
            <div key={row.label}>
              <div className="mb-1.5 flex items-center justify-between text-[12.5px]">
                <span className="font-semibold text-slate-700">{row.label}</span>
                <span className="text-wb-faint">{row.percentile}</span>
              </div>
              <div className="relative h-6 overflow-hidden rounded-full bg-[#EEF0F3]">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${row.clientPct}%` }}
                  transition={{ delay: 0.08 * i, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: row.tone === 'ok' ? '#16A34A' : '#DC2626' }}
                />
                <div
                  className="absolute inset-y-0 w-[2px] bg-wb-ink/70"
                  style={{ left: `${row.medianPct}%` }}
                  title="Médiane sectorielle"
                />
                <div className="relative z-10 flex h-full items-center justify-between px-3">
                  <span className="text-[11px] font-bold text-white drop-shadow-sm">{row.client}</span>
                </div>
              </div>
              <div className="mt-1 flex justify-end text-[10.5px] text-wb-faint">
                Médiane secteur : {row.median}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card delay={0.15} className="overflow-hidden p-0">
        <div className="border-b border-wb-line px-5 py-3 text-[13px] font-bold text-slate-900">
          Dossiers comparables
        </div>
        <ul className="m-0 list-none p-2">
          {benchmark.comparables.length === 0 && (
            <li className="px-3 py-6 text-center text-[12.5px] text-wb-muted">
              Pas encore de dossiers comparables dans le portefeuille.
            </li>
          )}
          {benchmark.comparables.map((c) => (
            <li key={c.id}>
              <Link
                to={`/analyse/${c.id}`}
                className="flex items-center gap-3 rounded-[10px] px-3 py-2.5 no-underline transition-colors hover:bg-wb-surface"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] font-bold text-slate-800">{c.name}</div>
                  <div className="mt-0.5 flex gap-2 text-[10.5px] text-wb-faint">
                    <span className="font-mono">{c.id}</span>
                    <span>{c.date}</span>
                  </div>
                </div>
                <ScorePill score={c.score} />
                <span
                  className="whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold"
                  style={{
                    color: c.decisionTone === 'ok' ? '#15803D' : '#B45309',
                    background: c.decisionTone === 'ok' ? '#ECFDF5' : '#FFF8EC',
                  }}
                >
                  {c.decision}
                </span>
                <ChevronRight size={15} className="flex-none text-wb-faint" />
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
