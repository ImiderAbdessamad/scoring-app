import { motion } from 'framer-motion'
import type { AnalyseTabId } from '@/types/analyse'

type TabDef = {
  id: AnalyseTabId
  label: string
  badge?: string
  badgeTone?: 'accent' | 'ai'
}

const TABS: TabDef[] = [
  { id: 'synthese', label: 'Vue générale' },
  { id: 'etats', label: 'États financiers' },
  { id: 'ratios', label: 'Ratios' },
  { id: 'fiscal', label: 'Analyse fiscale' },
  { id: 'capital', label: 'Capital' },
  { id: 'qualite', label: 'Contrôles & qualité' },
  { id: 'bien', label: 'Bien financé' },
  { id: 'factorielle', label: 'Tendances' },
  { id: 'comportement', label: 'Comportement' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'memo', label: 'Mémo', badge: 'IA', badgeTone: 'ai' },
]

type Props = {
  tab: AnalyseTabId
  onChange: (tab: AnalyseTabId) => void
}

export function AnalyseTabs({ tab, onChange }: Props) {
  return (
    <div className="flex gap-1 overflow-x-auto px-6">
      {TABS.map((t) => {
        const active = tab === t.id
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            className={[
              'relative flex-none cursor-pointer whitespace-nowrap border-0 bg-transparent px-3.5 py-2.5 text-[12.5px] font-semibold transition-colors',
              active ? 'text-wb-ink' : 'text-wb-muted hover:text-slate-700',
            ].join(' ')}
          >
            <span className="relative z-10 inline-flex items-center gap-1.5">
              {t.label}
              {t.badge && (
                <span
                  className={[
                    'inline-flex h-[16px] min-w-[16px] items-center justify-center rounded-full px-1 text-[9.5px] font-bold',
                    t.badgeTone === 'ai'
                      ? 'bg-wb-ink text-wb-accent'
                      : 'bg-wb-accent text-white',
                  ].join(' ')}
                >
                  {t.badge}
                </span>
              )}
            </span>
            {active && (
              <motion.span
                layoutId="analyse-tab-underline"
                className="absolute inset-x-2 bottom-0 h-[2.5px] rounded-full bg-wb-accent"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}
