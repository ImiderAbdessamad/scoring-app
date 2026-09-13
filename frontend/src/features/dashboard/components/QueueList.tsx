import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ScorePill } from '@/components/ui/ScorePill'
import type { QueueItem } from '@/types/dossier'

type Props = {
  items: QueueItem[]
  total: number
}

export function QueueList({ items, total }: Props) {
  return (
    <Card delay={0.28} className="p-[18px]">
      <div className="mb-3.5 flex items-center justify-between gap-3">
        <div>
          <div className="text-[14px] font-bold text-slate-900">
            File d&apos;attente · Prêts à analyser
          </div>
          <div className="mt-0.5 text-[11.5px] text-wb-muted">
            {total === 0
              ? 'Aucun dossier en file pour le moment'
              : `${total} dossier(s) en attente, triés par urgence`}
          </div>
        </div>
        <Link
          to="/dossiers?status=pending"
          className="text-[12px] font-semibold text-wb-accent no-underline hover:underline"
        >
          Voir tous →
        </Link>
      </div>

      <ul className="m-0 list-none p-0">
        {items.length === 0 && (
          <li className="px-1 py-8 text-center text-[13px] text-wb-muted">
            Créez un dossier pour le voir apparaître ici.
          </li>
        )}
        {items.map((qi, i) => (
          <motion.li
            key={qi.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.32 + i * 0.05, duration: 0.3 }}
            className="group flex items-center gap-3.5 border-b border-[#F1F2F4] py-3 last:border-b-0"
          >
            <span
              className="h-2 w-2 flex-none rounded-full"
              style={{
                background: qi.urgency === 'haute' ? '#E85D0C' : '#94A3B8',
              }}
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-bold text-slate-800">
                {qi.name}
              </div>
              <div className="mt-0.5 flex flex-wrap gap-2 text-[10.5px] text-wb-faint">
                <span className="font-mono">{qi.id}</span>
                <span>{qi.sector}</span>
                <span>{qi.received}</span>
              </div>
            </div>
            <div className="font-sans text-[13px] font-bold tabular-nums text-slate-700">
              {qi.amountShort}
            </div>
            <ScorePill score={qi.score} />
            <Link to={`/analyse/${qi.id}`}>
              <Button variant="soft" className="opacity-90 group-hover:opacity-100">
                Analyser →
              </Button>
            </Link>
          </motion.li>
        ))}
      </ul>
    </Card>
  )
}
