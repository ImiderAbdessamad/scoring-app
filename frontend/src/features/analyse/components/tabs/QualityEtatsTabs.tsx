import { useState } from 'react'
import { Card } from '@/components/ui/Card'
import type { DecisionEligibility } from '@/types/analyse'

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

/** Préparation à la décision : état des éléments nécessaires avant de statuer sur le dossier. */
export function QualityTab({ eligibility }: { eligibility?: DecisionEligibility | null }) {
  if (!eligibility) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        La préparation à la décision s’affiche après l’analyse du dossier.
      </Card>
    )
  }

  const rows: Array<{ label: string; value: string; ok: boolean | null }> = [
    { label: 'Analyse financière', value: eligibility.financial_analysis_ready ? 'Prête' : 'À revoir', ok: eligibility.financial_analysis_ready },
    { label: 'Comportement bancaire', value: eligibility.behavioral_analysis_ready ? 'Disponible' : 'Manquant', ok: eligibility.behavioral_analysis_ready },
    { label: 'Analyse sectorielle', value: eligibility.sector_analysis_ready ? 'Disponible' : 'Manquant', ok: eligibility.sector_analysis_ready },
    {
      label: 'Cotation BAM',
      value: eligibility.bam_clear === false ? 'Bloquante' : eligibility.bam_checked ? 'Vérifiée' : 'Non vérifiée',
      ok: eligibility.bam_clear === false ? false : eligibility.bam_checked ? true : null,
    },
    {
      label: 'Incidents bancaires',
      value: eligibility.incidents_clear === false ? 'Présents' : eligibility.incidents_checked ? 'Aucun' : 'Non vérifiés',
      ok: eligibility.incidents_clear === false ? false : eligibility.incidents_checked ? true : null,
    },
    { label: 'Documents obligatoires', value: eligibility.mandatory_documents_ready ? 'Complets' : 'Incomplets', ok: eligibility.mandatory_documents_ready },
    { label: 'Analyse', value: eligibility.analysis_stale ? 'Obsolète' : 'À jour', ok: !eligibility.analysis_stale },
  ]

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-[16px] font-semibold text-[#1C1B1B]">Préparation à la décision</div>
        <span
          className={`rounded-[8px] px-2 py-1 text-[11.5px] font-semibold ${
            eligibility.eligible_for_approval ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FFF8EC] text-[#B45309]'
          }`}
        >
          {eligibility.eligible_for_approval ? 'Dossier éligible à la décision' : 'Dossier non éligible pour l’instant'}
        </span>
      </div>
      <div className="mt-4">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3 border-t border-wb-line py-3 text-[13px]">
            <span className="text-slate-700">{row.label}</span>
            <span
              className={`rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold ${
                row.ok === true
                  ? 'bg-[#ECFDF5] text-[#15803D]'
                  : row.ok === false
                    ? 'bg-[#FFF8EC] text-[#B45309]'
                    : 'bg-wb-surface text-slate-600'
              }`}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

type StatementKey = 'synthese' | 'actif' | 'passif' | 'cpc' | 'esg'

const STATEMENTS: Array<{ key: StatementKey; label: string; title: string }> = [
  { key: 'synthese', label: 'Synthèse', title: 'Synthèse des états financiers' },
  { key: 'actif', label: 'Actif', title: 'Bilan — Actif' },
  { key: 'passif', label: 'Passif', title: 'Bilan — Passif' },
  { key: 'cpc', label: 'CPC', title: 'Compte de produits et charges' },
  { key: 'esg', label: 'ESG', title: 'État des soldes de gestion' },
]

/** États financiers : un état à la fois, choisi par des pilules. */
export function EtatsTab({
  statements,
  yearLabels,
}: {
  statements?: Partial<Record<StatementKey, StatementRow[]>> | null
  yearLabels?: string[]
}) {
  const [active, setActive] = useState<StatementKey>('synthese')

  if (!statements) {
    return <Card className="p-6 text-center text-[13px] text-wb-muted">États financiers disponibles après analyse.</Card>
  }
  const n1 = yearLabels?.[1] || 'N-1'
  const n = yearLabels?.[2] || 'N'
  const current = STATEMENTS.find((item) => item.key === active) ?? STATEMENTS[0]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="État financier">
        {STATEMENTS.map((item) => {
          const selected = item.key === active
          const count = statements[item.key]?.length ?? 0
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setActive(item.key)}
              className={[
                'inline-flex cursor-pointer items-center gap-2 rounded-full border-0 px-4 py-2 text-[13px] font-semibold transition-colors',
                selected ? 'bg-wb-ink text-white' : 'bg-white text-slate-600 ring-1 ring-wb-line hover:bg-wb-surface',
              ].join(' ')}
            >
              {item.label}
              <span
                className={[
                  'inline-flex min-w-[20px] items-center justify-center rounded-full px-1.5 py-px text-[11px] font-bold tabular-nums',
                  selected ? 'bg-wb-accent text-white' : 'bg-wb-surface text-wb-muted',
                ].join(' ')}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      <StatementTable title={current.title} rows={statements[current.key]} n1={n1} n={n} />
    </div>
  )
}

function variation(n?: number | null, n1?: number | null): number | null {
  if (n == null || n1 == null || n1 === 0) return null
  return (n - n1) / Math.abs(n1)
}

function StatementTable({ title, rows, n1, n }: { title: string; rows?: StatementRow[]; n1: string; n: string }) {
  const list = rows || []
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between gap-3 px-6 py-4">
        <div className="text-[16px] font-semibold text-[#1C1B1B]">{title}</div>
        <span className="text-[12px] text-wb-muted">{list.length} poste(s) · montants en MAD</span>
      </div>
      <div className="wb-scroll max-h-[640px] overflow-auto">
        <table className="w-full min-w-[640px] border-collapse text-[13px]">
          <thead className="sticky top-0 z-10 bg-[#F8FAFC]">
            <tr className="text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
              <th className="border-y border-wb-line px-6 py-3 text-left">Poste</th>
              <th className="border-y border-wb-line px-4 py-3 text-right">{n1}</th>
              <th className="border-y border-wb-line px-4 py-3 text-right">{n}</th>
              <th className="border-y border-wb-line px-6 py-3 text-right">Variation</th>
            </tr>
          </thead>
          <tbody>
            {list.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-6 text-center text-wb-muted">
                  Aucune ligne.
                </td>
              </tr>
            )}
            {list.map((row) => {
              const delta = variation(row.n, row.n1)
              return (
                <tr key={row.label} className="border-b border-wb-line transition-colors last:border-b-0 hover:bg-wb-accent-soft/40">
                  <td className="px-6 py-3">
                    <div className="font-semibold text-[#1C1B1B]">{row.label}</div>
                    <div className="mt-0.5 text-[10.5px] text-wb-faint">
                      {row.source}
                      {row.page ? ` · p. ${row.page}` : ''}
                      {row.nStatus ? ` · ${row.nStatus}` : ''}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-wb-muted">{mad(row.n1)}</td>
                  <td className="px-4 py-3 text-right font-bold tabular-nums text-[#1C1B1B]">{mad(row.n)}</td>
                  <td className="px-6 py-3 text-right">
                    {delta == null ? (
                      <span className="text-wb-faint">—</span>
                    ) : (
                      <span
                        className={`rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums ${
                          delta >= 0 ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FEF2F2] text-[#B91C1C]'
                        }`}
                      >
                        {delta > 0 ? '+' : delta < 0 ? '−' : ''}
                        {Math.abs(delta * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
