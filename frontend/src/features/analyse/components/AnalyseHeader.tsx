import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bot,
  Check,
  ChevronRight,
  TriangleAlert,
  X,
} from 'lucide-react'
import { STATUS_META, formatAmountMad } from '@/lib/format'
import { AnalyseTabs } from '@/features/analyse/components/AnalyseTabs'
import type { AnalyseHeader as AnalyseHeaderData, AnalyseTabId, DecisionEligibility, DecisionKind } from '@/types/analyse'

const DECISIONS: Array<{
  kind: DecisionKind
  label: string
  icon: typeof Check
  activeClass: string
  idleClass: string
}> = [
  {
    kind: 'approve',
    label: 'Approuver',
    icon: Check,
    activeClass: 'bg-[#16A34A] text-white',
    idleClass: 'bg-[#ECFDF5] text-[#15803D] hover:bg-[#DCFCE7]',
  },
  {
    kind: 'reserve',
    label: 'Sous réserve',
    icon: TriangleAlert,
    activeClass: 'bg-[#B45309] text-white',
    idleClass: 'bg-[#FFF8EC] text-[#B45309] hover:bg-[#FFEBD7]',
  },
  {
    kind: 'reject',
    label: 'Rejeter',
    icon: X,
    activeClass: 'bg-[#DC2626] text-white',
    idleClass: 'bg-[#FEF2F2] text-[#DC2626] hover:bg-[#FEE2E2]',
  },
]

const DECISION_TOAST: Record<DecisionKind, { text: string; color: string; bg: string; icon: typeof Check }> = {
  approve: { text: 'Dossier approuvé', color: '#15803D', bg: '#ECFDF5', icon: Check },
  reserve: { text: 'Dossier approuvé sous réserve', color: '#B45309', bg: '#FFF8EC', icon: TriangleAlert },
  reject: { text: 'Dossier rejeté', color: '#DC2626', bg: '#FEF2F2', icon: X },
}

type Props = {
  header: AnalyseHeaderData
  score: number
  classe?: string | null
  provisional?: boolean
  scoreStatus?: string
  decisionEligibility?: DecisionEligibility | null
  decisionBlockingReasons?: string[]
  onOpenEligibility?: () => void
  decision: DecisionKind | null
  decisionTime: string
  decisionBusy: boolean
  onDecision: (kind: DecisionKind) => void
  onClearDecision: () => void
  copilotOpen: boolean
  onToggleCopilot: () => void
  tab: AnalyseTabId
  onTabChange: (tab: AnalyseTabId) => void
}

export function AnalyseHeader({
  header,
  score: _score,
  classe: _classe,
  provisional: _provisional,
  scoreStatus: _scoreStatus,
  decisionEligibility,
  decisionBlockingReasons,
  onOpenEligibility,
  decision,
  decisionTime,
  decisionBusy,
  onDecision,
  onClearDecision,
  copilotOpen,
  onToggleCopilot,
  tab,
  onTabChange,
}: Props) {
  const statusMeta = STATUS_META[header.status]

  return (
    <div className="flex-none border-b border-wb-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#F1F2F4] px-6 py-3">
        <div className="flex min-w-0 items-center gap-1.5 text-[12px] text-wb-faint">
          <Link to="/" className="font-semibold text-wb-faint no-underline hover:text-slate-700">
            Tableau de bord
          </Link>
          <ChevronRight size={13} />
          <Link to="/dossiers" className="font-semibold text-wb-faint no-underline hover:text-slate-700">
            Dossiers
          </Link>
          <ChevronRight size={13} />
          <span className="truncate font-bold text-slate-700">{header.id}</span>
          <span
            className="ml-2 inline-flex flex-none whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold"
            style={{ color: statusMeta.color, background: statusMeta.bg }}
          >
            {header.statusLabel}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {DECISIONS.map((d) => {
            const Icon = d.icon
            const active = decision === d.kind
            return (
              <button
                key={d.kind}
                type="button"
                disabled={
                  decisionBusy ||
                  (d.kind === 'approve' && decisionEligibility?.eligible_for_approval === false) ||
                  (d.kind === 'reserve' && decisionEligibility?.eligible_for_reserve === false)
                }
                onClick={() => (active ? onClearDecision() : onDecision(d.kind))}
                className={[
                  'inline-flex cursor-pointer items-center gap-1.5 rounded-[9px] border-0 px-3 py-1.5 text-[12px] font-bold transition-[filter,transform] duration-150 hover:-translate-y-px active:scale-[0.98] disabled:cursor-wait disabled:opacity-60',
                  active ? d.activeClass : d.idleClass,
                ].join(' ')}
              >
                <Icon size={13} strokeWidth={2.4} />
                {d.label}
              </button>
            )
          })}
          <button
            type="button"
            onClick={onToggleCopilot}
            aria-pressed={copilotOpen}
            className={[
              'ml-1 inline-flex cursor-pointer items-center gap-1.5 rounded-[9px] border px-3 py-1.5 text-[12px] font-bold transition-colors',
              copilotOpen
                ? 'border-transparent bg-wb-ink text-white'
                : 'border-[#E2E5EA] bg-white text-slate-600 hover:bg-wb-surface',
            ].join(' ')}
          >
            <Bot size={14} strokeWidth={2} />
            Copilote IA
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-5 px-6 py-3.5">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="flex h-11 w-11 flex-none items-center justify-center rounded-[12px] bg-gradient-to-br from-wb-ink to-wb-ink-soft text-[13px] font-extrabold text-wb-accent ring-1 ring-black/5">
            {header.shortCode}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="m-0 truncate text-[17px] font-extrabold tracking-tight text-slate-900">
                {header.companyName}
              </h1>
              {header.tiers ? (
                <span className="rounded-full bg-[#EEF6FF] px-2 py-0.5 text-[10.5px] font-bold text-[#1D4ED8] ring-1 ring-[#BFDBFE]">
                  Tiers {header.tiers}
                </span>
              ) : null}
              {decisionBlockingReasons && decisionBlockingReasons.length > 0 ? (
                <button type="button" onClick={onOpenEligibility} className="rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-bold text-amber-800">
                  {decisionBlockingReasons.length} vérification(s) manquante(s)
                </button>
              ) : null}
            </div>
            <p className="m-0 mt-0.5 truncate text-[12px] text-wb-muted">{header.subtitle}</p>
          </div>
        </div>

        <div className="flex flex-none flex-wrap items-center gap-5">
          <HeaderStat label="Montant financé" value={formatAmountMad(header.amountFinanced)} />
          <HeaderStat label="Durée" value={`${header.durationMonths} mois`} />
          <HeaderStat label="Apport" value={`${header.apportPct}%`} />
          <HeaderStat label="Analyste" value={header.analyst} />
        </div>
      </div>

      <AnimatePresence>
        {decision && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden px-6"
          >
            <div
              className="mb-3 flex items-center justify-between gap-3 rounded-[10px] px-3.5 py-2.5"
              style={{ background: DECISION_TOAST[decision].bg }}
            >
              <div className="flex items-center gap-2">
                {(() => {
                  const ToastIcon = DECISION_TOAST[decision].icon
                  return <ToastIcon size={15} style={{ color: DECISION_TOAST[decision].color }} />
                })()}
                <span className="text-[12.5px] font-bold" style={{ color: DECISION_TOAST[decision].color }}>
                  {DECISION_TOAST[decision].text}
                </span>
                <span className="text-[11.5px] text-wb-faint">· {decisionTime}</span>
              </div>
              <button
                type="button"
                disabled={decisionBusy}
                onClick={onClearDecision}
                className="cursor-pointer border-0 bg-transparent text-[11.5px] font-semibold text-wb-faint hover:text-slate-700 disabled:cursor-wait disabled:opacity-60"
              >
                Annuler
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnalyseTabs tab={tab} onChange={onTabChange} />
    </div>
  )
}

function HeaderStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-right">
      <div className="text-[13px] font-bold tabular-nums text-slate-800">{value}</div>
      <div className="text-[10.5px] uppercase tracking-[0.04em] text-wb-faint">{label}</div>
    </div>
  )
}
