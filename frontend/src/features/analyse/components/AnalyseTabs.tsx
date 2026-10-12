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
  // Onglet masqué pour l'instant — réactivable en décommentant (voir aussi AnalysePage.tsx).
  // { id: 'qualite', label: 'Préparation à la décision' },
  { id: 'bien', label: 'Bien financé' },
  { id: 'factorielle', label: 'Tendances' },
  { id: 'comportement', label: 'Comportement bancaire' },
  { id: 'benchmark', label: 'Analyse sectorielle' },
]

type Props = {
  tab: AnalyseTabId
  onChange: (tab: AnalyseTabId) => void
}

export function AnalyseTabs({ tab, onChange }: Props) {
  return (
    <div className="wb-scroll flex gap-1.5 overflow-x-auto px-6 pb-1 pt-4">
      {TABS.map((t) => {
        const active = tab === t.id
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            className={[
              'relative flex-none cursor-pointer whitespace-nowrap rounded-full border-0 px-4 py-2 text-[12.5px] font-semibold transition-colors',
              active ? 'bg-transparent text-white' : 'bg-white text-slate-600 ring-1 ring-wb-line hover:bg-wb-surface',
            ].join(' ')}
          >
            <span className="relative z-10 inline-flex items-center gap-1.5">
              {t.label}
              {t.badge && (
                <span
                  className={[
                    'inline-flex h-[16px] min-w-[16px] items-center justify-center rounded-full px-1 text-[9.5px] font-bold',
                    t.badgeTone === 'ai'
                      ? 'bg-wb-accent text-white'
                      : 'bg-wb-accent text-white',
                  ].join(' ')}
                >
                  {t.badge}
                </span>
              )}
            </span>
            {active && (
              <motion.span
                layoutId="analyse-tab-pill"
                className="absolute inset-0 rounded-full bg-wb-ink"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}
