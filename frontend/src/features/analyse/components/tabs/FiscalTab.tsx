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

export function FiscalTab({ fiscal }: { fiscal?: FiscalAnalysis | null }) {
  if (!fiscal?.available) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Analyse fiscale non extraite sur cette liasse.
      </Card>
    )
  }
  const ok = fiscal.validation_status === 'coherent'
  return (
    <div className="flex flex-col gap-3">
      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-[13px] font-bold text-slate-900">Analyse fiscale</div>
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}>
            {ok ? 'Cohérent' : 'À vérifier'}
          </span>
        </div>
        <Row label="Résultat net comptable" value={mad(fiscal.resultat_net_comptable?.value)} />
        <Row label="+ Réintégrations fiscales" value={mad(fiscal.reintegrations?.total ?? null)} />
        {(fiscal.reintegrations?.details || []).map((d) => (
          <Row key={d.label} label={d.label} value={mad(d.amount)} faint />
        ))}
        <Row label="− Déductions fiscales" value={mad(fiscal.deductions?.total ?? null)} />
        {(fiscal.deductions?.details || []).map((d) => (
          <Row key={d.label} label={d.label} value={mad(d.amount)} faint />
        ))}
        <div className="my-2 border-t border-wb-line" />
        <Row label="Résultat brut fiscal" value={mad(fiscal.resultat_brut_fiscal?.value)} bold />
        <Row label="Reports déficitaires" value={mad(fiscal.reports_deficitaires?.value)} />
        <div className="my-2 border-t border-wb-line" />
        <Row label="Résultat net fiscal" value={mad(fiscal.resultat_net_fiscal?.value)} bold />
      </Card>
    </div>
  )
}

function Row({ label, value, faint, bold }: { label: string; value: string; faint?: boolean; bold?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 py-1.5 text-[12.5px] ${faint ? 'pl-4 text-wb-muted' : 'text-slate-800'}`}>
      <span>{label}</span>
      <span className={`tabular-nums ${bold ? 'font-extrabold' : 'font-semibold'}`}>{value}</span>
    </div>
  )
}
