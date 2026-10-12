import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Card } from '@/components/ui/Card'

type AmountQ = { value?: number | null; status?: string; usable?: boolean }
type FiscalLine = { label: string; amount?: number | null }
type FiscalAnalysis = {
  available?: boolean
  resultat_net_comptable?: AmountQ
  reintegrations?: { total?: number | null; details?: FiscalLine[] }
  deductions?: { total?: number | null; details?: FiscalLine[] }
  resultat_brut_fiscal?: AmountQ
  reports_deficitaires?: AmountQ
  resultat_net_fiscal?: AmountQ
  validation_status?: string | null
  warnings?: string[]
}

function mad(value?: number | null) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('fr-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value) + ' MAD'
}

/** Passage du résultat comptable au résultat fiscal, présenté comme un calcul étape par étape. */
export function FiscalTab({ fiscal }: { fiscal?: FiscalAnalysis | null }) {
  if (!fiscal?.available) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Analyse fiscale non extraite sur cette liasse.
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-6">
        <div className="text-[16px] font-semibold text-[#1C1B1B]">Analyse fiscale</div>
        <div className="mt-5 grid grid-cols-1 gap-x-6 gap-y-4 border-t border-wb-line pt-5 sm:grid-cols-3">
          <KeyFigure label="Résultat net comptable" value={fiscal.resultat_net_comptable?.value} />
          <KeyFigure label="Résultat brut fiscal" value={fiscal.resultat_brut_fiscal?.value} />
          <KeyFigure label="Résultat net fiscal" value={fiscal.resultat_net_fiscal?.value} accent />
        </div>
      </Card>

      <Card delay={0.1} className="overflow-hidden p-0">
        <div className="px-6 py-4 text-[16px] font-semibold text-[#1C1B1B]">Du résultat comptable au résultat fiscal</div>
        <Step operator="=" label="Résultat net comptable" value={fiscal.resultat_net_comptable?.value} />
        <Step
          operator="+"
          label="Réintégrations fiscales"
          value={fiscal.reintegrations?.total ?? null}
          details={fiscal.reintegrations?.details}
        />
        <Step
          operator="−"
          label="Déductions fiscales"
          value={fiscal.deductions?.total ?? null}
          details={fiscal.deductions?.details}
        />
        <Step operator="=" label="Résultat brut fiscal" value={fiscal.resultat_brut_fiscal?.value} total />
        <Step operator="−" label="Reports déficitaires" value={fiscal.reports_deficitaires?.value} />
        <Step operator="=" label="Résultat net fiscal" value={fiscal.resultat_net_fiscal?.value} total final />
      </Card>
    </div>
  )
}

function KeyFigure({ label, value, accent = false }: { label: string; value?: number | null; accent?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] text-wb-muted">{label}</div>
      <div
        className={`mt-1 truncate text-[20px] font-bold tabular-nums tracking-[-0.01em] ${
          accent ? 'text-wb-accent-text' : 'text-[#1C1B1B]'
        }`}
      >
        {mad(value)}
      </div>
    </div>
  )
}

function Step({
  operator,
  label,
  value,
  details,
  total = false,
  final = false,
}: {
  operator: '+' | '−' | '='
  label: string
  value?: number | null
  details?: FiscalLine[]
  total?: boolean
  final?: boolean
}) {
  const [open, setOpen] = useState(false)
  const lines = details || []
  const expandable = lines.length > 0

  const content = (
    <>
      <span
        className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-[14px] font-bold ${
          final ? 'bg-wb-accent text-white' : total ? 'bg-wb-ink text-white' : 'bg-wb-surface text-slate-600'
        }`}
      >
        {operator}
      </span>
      <span className={`min-w-0 flex-1 text-[13.5px] ${total ? 'font-semibold text-[#1C1B1B]' : 'text-slate-700'}`}>
        {label}
        {expandable && <span className="ml-2 text-[11.5px] text-wb-muted">({lines.length} ligne(s))</span>}
      </span>
      <span
        className={`flex-none tabular-nums ${
          final ? 'text-[15px] font-bold text-wb-accent-text' : total ? 'text-[14px] font-bold text-[#1C1B1B]' : 'text-[13.5px] font-semibold text-slate-800'
        }`}
      >
        {mad(value)}
      </span>
      {expandable ? (
        <span
          className={`flex h-7 w-7 flex-none items-center justify-center rounded-full transition-colors ${
            open ? 'bg-wb-accent text-white' : 'bg-wb-surface text-wb-muted'
          }`}
        >
          <ChevronDown size={15} strokeWidth={2.2} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      ) : (
        <span className="w-7 flex-none" />
      )}
    </>
  )

  return (
    <div className={`border-t border-wb-line ${total ? 'bg-[#F8FAFC]' : ''}`}>
      {expandable ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-6 py-3.5 text-left transition-colors hover:bg-wb-accent-soft/40"
        >
          {content}
        </button>
      ) : (
        <div className="flex items-center gap-3 px-6 py-3.5">{content}</div>
      )}
      {expandable && open && (
        <div className="mx-6 mb-4 rounded-[14px] bg-wb-surface px-4 py-1">
          {lines.map((line) => (
            <div key={line.label} className="flex items-start justify-between gap-4 border-t border-wb-line py-2 text-[12.5px] first:border-t-0">
              <span className="text-slate-600">{line.label}</span>
              <span className="flex-none font-semibold tabular-nums text-slate-800">{mad(line.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
