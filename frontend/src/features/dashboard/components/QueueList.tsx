import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { STAGE_META } from '@/lib/format'
import type { QueueItem } from '@/types/dossier'

type Props = {
  items: QueueItem[]
  total: number
}

export function QueueList({ items, total }: Props) {
  return (
    <Card delay={0.28} className="p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-[18px] font-semibold text-[#1C1B1B]">
            File d&apos;attente · À analyser et en cours
          </div>
          <div className="mt-1 text-[12.5px] text-wb-muted">
            {total === 0
              ? 'Tous les dossiers sont analysés'
              : `${total} dossier(s) · analyses en cours d’abord, puis par urgence`}
          </div>
        </div>
        <Link
          to="/dossiers"
          className="flex flex-none items-center gap-1.5 text-[13px] font-semibold text-wb-accent-text no-underline hover:underline"
        >
          Voir tous <ChevronRight size={15} strokeWidth={2.2} />
        </Link>
      </div>

      <ul className="m-0 list-none p-0">
        {items.length === 0 && (
          <li className="px-1 py-8 text-center text-[13px] text-wb-muted">
            Aucun dossier à analyser ni en cours d’analyse.
          </li>
        )}
        {items.map((qi, i) => (
          <motion.li
            key={qi.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.32 + i * 0.05, duration: 0.3 }}
            className="group flex items-center gap-3.5 border-b border-wb-line py-3.5 last:border-b-0"
          >
            <span
              className="h-2 w-2 flex-none rounded-full"
              style={{
                background: qi.urgency === 'haute' ? '#FF9B26' : '#94A3B8',
              }}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[14px] font-bold text-[#1C1B1B]">
                {qi.name}
              </div>
              <div className="mt-0.5 flex flex-wrap gap-2 text-[10.5px] text-wb-faint">
                <span className="font-mono">{qi.id}</span>
                <span>{qi.sector}</span>
                <span>{qi.received}</span>
              </div>
            </div>
            <StageTag stage={qi.stage ?? 'todo'} progressPct={qi.progressPct} />
            <div className="font-sans text-[13px] font-bold tabular-nums text-slate-700">
              {qi.amountShort}
            </div>
            <Link to={`/analyse/${qi.id}`}>
              <Button variant="soft" className="pr-1.5 group-hover:border-wb-accent">
                Analyser
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-wb-accent text-white">
                  <ChevronRight size={14} strokeWidth={2.4} />
                </span>
              </Button>
            </Link>
          </motion.li>
        ))}
      </ul>
    </Card>
  )
}

function StageTag({ stage, progressPct }: { stage: 'todo' | 'analyzing'; progressPct?: number | null }) {
  const meta = STAGE_META[stage]
  return (
    <span
      className="hidden flex-none whitespace-nowrap rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums sm:inline-flex"
      style={{ color: meta.color, background: meta.bg }}
    >
      {meta.label}
      {stage === 'analyzing' && typeof progressPct === 'number' ? ` · ${progressPct} %` : ''}
    </span>
  )
}
