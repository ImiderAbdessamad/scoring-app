import { Link } from 'react-router-dom'
import { Bot, ChevronRight } from 'lucide-react'
import { formatAmountMad } from '@/lib/format'
import { AnalyseTabs } from '@/features/analyse/components/AnalyseTabs'
import { HERO_BACKGROUND } from '@/components/layout/heroBackground'
import type {
  AnalyseHeader as AnalyseHeaderData,
  AnalyseTabId,
  ClientLookup,
  DecisionEligibility,
  IaClientMatch,
  DecisionKind,
} from '@/types/analyse'

/** Statut de la recherche dans le référentiel clients, en étiquette claire sur le bandeau. */
const LOOKUP_STATUS: Record<ClientLookup['status'], { label: string; className: string }> = {
  MATCHED: { label: 'Client trouvé', className: 'bg-[#ECFDF5] text-[#15803D]' },
  MULTIPLE: { label: 'Plusieurs correspondances', className: 'bg-[#FFF8EC] text-[#B45309]' },
  NOT_FOUND: { label: 'Aucun client', className: 'bg-[rgba(250,250,250,0.95)] text-slate-700' },
  SKIPPED: { label: 'Non recherché', className: 'bg-[rgba(250,250,250,0.95)] text-slate-500' },
  ERROR: { label: 'API indisponible', className: 'bg-[#FEF2F2] text-[#B91C1C]' },
}

type Props = {
  header: AnalyseHeaderData
  clientLookup?: ClientLookup | null
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
  clientLookup,
  score: _score,
  classe: _classe,
  provisional: _provisional,
  scoreStatus: _scoreStatus,
  decisionEligibility: _decisionEligibility,
  decisionBlockingReasons,
  onOpenEligibility,
  decision: _decision,
  decisionTime: _decisionTime,
  decisionBusy: _decisionBusy,
  onDecision: _onDecision,
  onClearDecision: _onClearDecision,
  copilotOpen,
  onToggleCopilot,
  tab,
  onTabChange,
}: Props) {
  const subtitleItems = identityTags(header, clientLookup)
  const lookupStatus = clientLookup ? LOOKUP_STATUS[clientLookup.status] || LOOKUP_STATUS.SKIPPED : null
  const otherMatches = clientLookup ? clientLookup.matches.slice(1) : []
  const lookupQuery = Object.entries(clientLookup?.query || {})
    .map(([key, value]) => `${key}=${value}`)
    .join(' · ')

  return (
    <div className="flex-none">
      <div className="relative mx-3 mt-3 overflow-hidden rounded-[24px] text-white" style={HERO_BACKGROUND}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-7 pt-5">
        <div className="flex min-w-0 items-center gap-1.5 text-[12px] text-white/60">
          <Link to="/" className="font-medium text-white/60 no-underline hover:text-white">
            Tableau de bord
          </Link>
          <ChevronRight size={13} />
          <Link to="/dossiers" className="font-medium text-white/60 no-underline hover:text-white">
            Dossiers
          </Link>
          <ChevronRight size={13} />
          <span className="truncate font-semibold text-white">{header.id}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onToggleCopilot}
            aria-pressed={copilotOpen}
            className={[
              'inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-[12px] font-bold backdrop-blur-[2px] transition-colors',
              copilotOpen
                ? 'border-wb-accent bg-wb-accent text-white'
                : 'border-white/30 bg-white/10 text-white hover:bg-white/20',
            ].join(' ')}
          >
            <Bot size={14} strokeWidth={2} />
            Copilote IA
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-5 px-7 pb-5 pt-4">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <span className="flex h-12 w-12 flex-none items-center justify-center rounded-full bg-wb-accent text-[13px] font-extrabold text-white">
            {header.shortCode}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="m-0 truncate text-[26px] font-medium leading-tight tracking-[0.01em] text-white">
                {header.companyName}
              </h1>
              {lookupStatus && (
                <span
                  className={`rounded-[8px] px-2 py-0.5 text-[11px] font-semibold ${lookupStatus.className}`}
                  title={lookupQuery ? `Référentiel clients · requête : ${lookupQuery}` : 'Référentiel clients'}
                >
                  {lookupStatus.label}
                </span>
              )}
              {otherMatches.length > 0 && (
                <span
                  className="rounded-[8px] bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white ring-1 ring-white/20"
                  title={otherMatches
                    .slice(0, 5)
                    .map((m) => `${m.tiers || '—'} · ${m.raison_sociale || 'Sans raison sociale'}${m.ice ? ` · ICE ${m.ice}` : ''}`)
                    .join('\n')}
                >
                  +{otherMatches.length} autre(s) correspondance(s)
                </span>
              )}
              {decisionBlockingReasons && decisionBlockingReasons.length > 0 ? (
                onOpenEligibility ? (
                  <button type="button" onClick={onOpenEligibility} className="cursor-pointer rounded-[8px] border-0 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-800">
                    {decisionBlockingReasons.length} vérification(s) manquante(s)
                  </button>
                ) : (
                  <span className="rounded-[8px] bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-800">
                    {decisionBlockingReasons.length} vérification(s) manquante(s)
                  </span>
                )
              ) : null}
            </div>
            {subtitleItems.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {subtitleItems.map((item) => (
                  <span
                    key={item}
                    className="rounded-[8px] bg-[rgba(250,250,250,0.95)] px-2 py-0.5 text-[11.5px] font-medium text-[#171717]"
                  >
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-none flex-wrap items-center gap-6">
          <HeaderStat label="Montant financé" value={formatAmountMad(header.amountFinanced)} />
          <HeaderStat label="Durée" value={`${header.durationMonths} mois`} />
          <HeaderStat label="Apport" value={`${header.apportPct}%`} />
          <HeaderStat label="Analyste" value={header.analyst} />
        </div>
      </div>

      </div>

      <AnalyseTabs tab={tab} onChange={onTabChange} />
    </div>
  )
}

/* Identifiants du client sous le nom : N° tiers d'abord, puis ICE, IF, RC, puis le reste
   de la ligne du backend (secteur, activité, n° PVC). Les identifiants absents de cette
   ligne sont complétés par le client retenu dans le référentiel ; inconnus, ils affichent « — ». */
const IDENTIFIERS: Array<{ prefix: string; label: string; fromLookup: (m: IaClientMatch) => string | null | undefined }> = [
  { prefix: 'Tiers', label: 'N° tiers', fromLookup: (m) => m.tiers },
  { prefix: 'ICE', label: 'ICE', fromLookup: (m) => m.ice },
  { prefix: 'IF', label: 'IF', fromLookup: (m) => m.identifiant_fiscal },
  { prefix: 'RC', label: 'RC', fromLookup: (m) => m.rc },
]

function identityTags(header: AnalyseHeaderData, lookup?: ClientLookup | null): string[] {
  const bits = (header.subtitle || '')
    .split(' · ')
    .map((item) => item.trim())
    .filter((item) => item && item !== '—')
  const primary = lookup?.primary
  const identifiers = IDENTIFIERS.map(({ prefix, label, fromLookup }) => {
    const fromLine = bits.find((bit) => bit.startsWith(`${prefix} `))?.slice(prefix.length + 1)
    const fallback = prefix === 'Tiers' ? header.tiers : null
    return `${label} ${fromLine || (primary && fromLookup(primary)) || fallback || '—'}`
  })
  const rest = bits.filter((bit) => !IDENTIFIERS.some(({ prefix }) => bit.startsWith(`${prefix} `)))
  return [...identifiers, ...rest]
}

function HeaderStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-right">
      <div className="text-[15px] font-bold tabular-nums text-white">{value}</div>
      <div className="mt-0.5 text-[11px] text-white/60">{label}</div>
    </div>
  )
}
