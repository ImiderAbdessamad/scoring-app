import { Card } from '@/components/ui/Card'
import type { DecisionEligibility } from '@/types/analyse'

type Quality = {
  observed_current_count?: number
  usable_current_count?: number
  observed_previous_count?: number
  usable_previous_count?: number
  suspect_count?: number
  conflict_count?: number
  cross_checked_count?: number
  passed_checks?: number
  failed_checks?: number
  not_evaluable_checks?: number
  presence_completeness_pct?: number
  usable_completeness_pct?: number
  scoring_input_completeness_pct?: number
}

type Readiness = {
  ready_for_automatic_scoring?: boolean
  status?: string
  blocking_reasons?: string[]
  scoring_inputs_usable?: number
  scoring_inputs_required?: number
}

type Control = {
  code: string
  label: string
  period?: string | null
  period_label?: string | null
  status: string
  message?: string
}

type StatementRow = {
  label: string
  n?: number | null
  n1?: number | null
  nStatus?: string
  n1Status?: string
  source?: string
  page?: number | null
  confidence?: number | null
}

function mad(value?: number | null) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('fr-MA', { maximumFractionDigits: 2 }).format(value)
}

export function QualityTab({
  quality,
  readiness,
  controls,
  eligibility,
}: {
  quality?: Quality | null
  readiness?: Readiness | null
  controls?: Control[] | null
  eligibility?: DecisionEligibility | null
}) {
  const ready = Boolean(readiness?.ready_for_automatic_scoring)
  const row = (label: string, value: string) => (
    <div className="flex items-center justify-between border-t border-[#F1F2F4] py-1.5 text-[12.5px]">
      <span className="text-wb-muted">{label}</span>
      <span className="font-semibold text-slate-800">{value}</span>
    </div>
  )
  return (
    <div className="flex flex-col gap-3">
      <Card className="p-5">
        <div className="mb-2 text-[13px] font-bold text-slate-900">Qualité des données</div>
        <div className="grid grid-cols-2 gap-2 text-[12.5px] sm:grid-cols-3">
          <Stat label="Observées N" value={quality?.observed_current_count ?? 0} />
          <Stat label="Utilisables N" value={quality?.usable_current_count ?? 0} />
          <Stat label="Cross-checkées" value={quality?.cross_checked_count ?? 0} />
          <Stat label="Suspectes" value={quality?.suspect_count ?? 0} />
          <Stat label="Conflits" value={quality?.conflict_count ?? 0} />
          <Stat label="Contrôles OK" value={quality?.passed_checks ?? 0} />
        </div>
        <div className="mt-3 text-[12.5px] text-wb-muted">
          Complétude observée {quality?.presence_completeness_pct ?? 0} % · utilisable{' '}
          {quality?.usable_completeness_pct ?? 0} % · inputs scoring {readiness?.scoring_inputs_usable ?? 0}/
          {readiness?.scoring_inputs_required ?? 0}
        </div>
        <div className={`mt-3 rounded-[10px] px-3 py-2 text-[12.5px] font-semibold ${ready ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>
          {ready ? 'Prêt pour scoring' : 'Revue manuelle requise'}
        </div>
        {(readiness?.blocking_reasons || []).map((reason) => (
          <div key={reason} className="mt-1 text-[12px] text-wb-muted">
            {reason}
          </div>
        ))}
      </Card>
      {eligibility ? (
        <Card className="p-5">
          <div className="mb-2 text-[13px] font-bold text-slate-900">Préparation à la décision</div>
          {row('Analyse financière', eligibility.financial_analysis_ready ? 'Prête' : 'À revoir')}
          {row('Comportement bancaire', eligibility.behavioral_analysis_ready ? 'Disponible' : 'Manquant')}
          {row('Analyse sectorielle', eligibility.sector_analysis_ready ? 'Disponible' : 'Manquant')}
          {row(
            'BAM',
            eligibility.bam_clear === false ? 'Bloquante' : eligibility.bam_checked ? 'Vérifiée' : 'Non vérifiée',
          )}
          {row(
            'Incidents',
            eligibility.incidents_clear === false ? 'Présents' : eligibility.incidents_checked ? 'Clear' : 'Non vérifiés',
          )}
          {row('Documents', eligibility.mandatory_documents_ready ? 'Complets' : 'Incomplets')}
          {row('Analyse', eligibility.analysis_stale ? 'Obsolète' : 'À jour')}
          {row('Décision', eligibility.eligible_for_approval ? 'Éligible' : 'Non éligible')}
        </Card>
      ) : null}
      <Card className="overflow-hidden p-0">
        <div className="border-b border-wb-line px-5 py-3 text-[13px] font-bold">Contrôles N / N-1</div>
        {(controls || []).length === 0 && (
          <div className="px-5 py-6 text-[13px] text-wb-muted">Aucun contrôle évalué.</div>
        )}
        {(controls || []).map((c) => (
          <div key={c.code} className="flex items-start justify-between gap-3 border-t border-[#F1F2F4] px-5 py-2.5 text-[12.5px]">
            <div>
              <div className="font-semibold text-slate-800">{c.label}</div>
              <div className="text-[11px] text-wb-faint">{c.message}</div>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${c.status === 'passed' ? 'bg-emerald-50 text-emerald-700' : c.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'}`}>
              {c.status}
            </span>
          </div>
        ))}
      </Card>
    </div>
  )
}

export function EtatsTab({
  statements,
  yearLabels,
}: {
  statements?: { actif?: StatementRow[]; passif?: StatementRow[]; cpc?: StatementRow[]; esg?: StatementRow[]; synthese?: StatementRow[] } | null
  yearLabels?: string[]
}) {
  if (!statements) {
    return <Card className="p-6 text-center text-[13px] text-wb-muted">États financiers disponibles après analyse.</Card>
  }
  const n1 = yearLabels?.[1] || 'N-1'
  const n = yearLabels?.[2] || 'N'
  return (
    <div className="flex flex-col gap-3">
      <Table title="Synthèse" rows={statements.synthese} n1={n1} n={n} />
      <Table title="Actif" rows={statements.actif} n1={n1} n={n} />
      <Table title="Passif" rows={statements.passif} n1={n1} n={n} />
      <Table title="CPC" rows={statements.cpc} n1={n1} n={n} />
      <Table title="ESG" rows={statements.esg} n1={n1} n={n} />
    </div>
  )
}

function Table({ title, rows, n1, n }: { title: string; rows?: StatementRow[]; n1: string; n: string }) {
  const list = rows || []
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-wb-line px-5 py-3 text-[13px] font-bold">{title}</div>
      <div className="grid grid-cols-[1.4fr_1fr_1fr] gap-2 border-b border-[#F1F2F4] px-5 py-2 text-[10.5px] font-bold uppercase text-wb-faint">
        <div>Poste</div>
        <div className="text-right">{n1}</div>
        <div className="text-right">{n}</div>
      </div>
      {list.length === 0 && <div className="px-5 py-5 text-[13px] text-wb-muted">Aucune ligne.</div>}
      {list.map((row) => (
        <div key={row.label} className="grid grid-cols-[1.4fr_1fr_1fr] gap-2 border-t border-[#F1F2F4] px-5 py-2 text-[12px]">
          <div>
            <div className="font-semibold text-slate-800">{row.label}</div>
            <div className="text-[10.5px] text-wb-faint">
              {row.source}
              {row.page ? ` · p. ${row.page}` : ''}
              {row.nStatus ? ` · ${row.nStatus}` : ''}
            </div>
          </div>
          <div className="text-right tabular-nums text-wb-muted">{mad(row.n1)}</div>
          <div className="text-right font-bold tabular-nums">{mad(row.n)}</div>
        </div>
      ))}
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[10px] border border-wb-line px-3 py-2">
      <div className="text-[10.5px] uppercase text-wb-faint">{label}</div>
      <div className="text-[16px] font-extrabold tabular-nums">{value}</div>
    </div>
  )
}
