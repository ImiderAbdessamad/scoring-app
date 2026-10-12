import { motion } from 'framer-motion'
import { Card } from '@/components/ui/Card'

type Associate = {
  name?: string | null
  identifier?: string | null
  identifier_type?: string | null
  titres_previous?: number | null
  titres_current?: number | null
  nominal_value?: number | null
  capital_souscrit?: number | null
  capital_appele?: number | null
  capital_libere?: number | null
  status?: string
}

type CapitalAnalysis = {
  available?: boolean
  capital_social?: { value?: number | null; status?: string }
  validation_status?: string | null
  associates?: Associate[]
}

function num(value?: number | null) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('fr-MA', { maximumFractionDigits: 2 }).format(value)
}

function mad(value?: number | null) {
  return value === null || value === undefined ? '—' : `${num(value)} MAD`
}

function sum(values: Array<number | null | undefined>): number | null {
  const known = values.filter((v): v is number => typeof v === 'number')
  return known.length ? known.reduce((a, b) => a + b, 0) : null
}

function pct(part?: number | null, total?: number | null): number | null {
  if (part == null || !total) return null
  return (part / total) * 100
}

function formatPct(value: number | null) {
  return value == null ? '—' : `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
}

/** Capital et actionnariat : chiffres clés, répartition du capital et détail par associé. */
export function CapitalTab({ capital }: { capital?: CapitalAnalysis | null }) {
  if (!capital?.available) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Répartition du capital non extraite sur cette liasse.
      </Card>
    )
  }

  const associates = capital.associates || []
  const totalTitres = sum(associates.map((a) => a.titres_current))
  const totalLibere = sum(associates.map((a) => a.capital_libere))
  const shares = associates
    .map((a, i) => ({ key: `${a.name || 'associe'}-${i}`, name: a.name || 'Associé non nommé', share: pct(a.titres_current, totalTitres) }))
    .sort((a, b) => (b.share ?? -1) - (a.share ?? -1))

  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-6">
        <div className="text-[16px] font-semibold text-[#1C1B1B]">Capital & actionnariat</div>
        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-wb-line pt-5 lg:grid-cols-4">
          <KeyFigure label="Capital social" value={mad(capital.capital_social?.value)} accent />
          <KeyFigure label="Associés" value={String(associates.length)} />
          <KeyFigure label="Titres (N)" value={num(totalTitres)} />
          <KeyFigure label="Capital libéré" value={mad(totalLibere)} />
        </div>
      </Card>

      {shares.some((s) => s.share != null) && (
        <Card delay={0.1} className="p-6">
          <div className="mb-4 text-[16px] font-semibold text-[#1C1B1B]">Répartition du capital</div>
          <div className="flex flex-col gap-3">
            {shares.map((item, i) => (
              <div key={item.key} className="flex items-center gap-3">
                <div className="w-[34%] min-w-0 truncate text-[13px] text-slate-700" title={item.name}>
                  {item.name}
                </div>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[#EEF0F3]">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${item.share ?? 0}%` }}
                    transition={{ delay: 0.15 + i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className={`h-full rounded-full ${i === 0 ? 'bg-wb-accent' : 'bg-wb-ink'}`}
                  />
                </div>
                <div className="w-[64px] flex-none text-right text-[13px] font-bold tabular-nums text-[#1C1B1B]">
                  {formatPct(item.share)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card delay={0.15} className="overflow-hidden p-0">
        <div className="px-6 py-4 text-[16px] font-semibold text-[#1C1B1B]">Détail des associés</div>
        <div className="wb-scroll overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-[13px]">
            <thead className="bg-[#F8FAFC]">
              <tr className="text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
                <th className="border-y border-wb-line px-6 py-3 text-left">Associé</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">% du capital</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Titres N-1</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Titres N</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Nominal</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Souscrit</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Appelé</th>
                <th className="border-y border-wb-line px-6 py-3 text-right">Libéré</th>
              </tr>
            </thead>
            <tbody>
              {associates.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-6 py-6 text-center text-wb-muted">
                    Aucun associé extrait.
                  </td>
                </tr>
              )}
              {associates.map((row, i) => (
                <tr key={i} className="border-b border-wb-line transition-colors last:border-b-0 hover:bg-wb-accent-soft/40">
                  <td className="px-6 py-3">
                    <div className="font-semibold text-[#1C1B1B]">{row.name || '—'}</div>
                    {(row.identifier_type || row.identifier) && (
                      <div className="mt-0.5 text-[11px] text-wb-faint">
                        {row.identifier_type ? `${row.identifier_type} ${row.identifier || ''}` : row.identifier}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right font-bold tabular-nums text-[#1C1B1B]">
                    {formatPct(pct(row.titres_current, totalTitres))}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-wb-muted">{num(row.titres_previous)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{num(row.titres_current)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{num(row.nominal_value)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{num(row.capital_souscrit)}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{num(row.capital_appele)}</td>
                  <td className="px-6 py-3 text-right tabular-nums">{num(row.capital_libere)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function KeyFigure({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] text-wb-muted">{label}</div>
      <div
        className={`mt-1 truncate text-[20px] font-bold tabular-nums tracking-[-0.01em] ${
          accent ? 'text-wb-accent-text' : 'text-[#1C1B1B]'
        }`}
      >
        {value}
      </div>
    </div>
  )
}
