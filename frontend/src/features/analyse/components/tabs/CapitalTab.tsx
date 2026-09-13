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

export function CapitalTab({ capital }: { capital?: CapitalAnalysis | null }) {
  if (!capital?.available) {
    return (
      <Card className="p-6 text-center text-[13px] text-wb-muted">
        Répartition du capital non extraite sur cette liasse.
      </Card>
    )
  }
  const ok = capital.validation_status === 'valide'
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-wb-line px-5 py-3">
        <div>
          <div className="text-[13px] font-bold text-slate-900">Capital & actionnariat</div>
          <div className="text-[12px] text-wb-muted">
            Capital social : {num(capital.capital_social?.value)} MAD
          </div>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}>
          {ok ? 'Validé' : 'À vérifier'}
        </span>
      </div>
      <div className="wb-scroll overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-[12px]">
          <thead>
            <tr className="bg-[#FAFBFC] text-left text-[10.5px] font-bold uppercase text-wb-faint">
              <th className="px-4 py-2">Associé</th>
              <th className="px-3 py-2">Identifiant</th>
              <th className="px-3 py-2 text-right">Titres N-1</th>
              <th className="px-3 py-2 text-right">Titres N</th>
              <th className="px-3 py-2 text-right">Nominal</th>
              <th className="px-3 py-2 text-right">Souscrit</th>
              <th className="px-3 py-2 text-right">Appelé</th>
              <th className="px-3 py-2 text-right">Libéré</th>
              <th className="px-4 py-2">Statut</th>
            </tr>
          </thead>
          <tbody>
            {(capital.associates || []).map((row, i) => (
              <tr key={i} className="border-t border-[#F1F2F4]">
                <td className="px-4 py-2 font-semibold">{row.name || '—'}</td>
                <td className="px-3 py-2">{row.identifier_type ? `${row.identifier_type} ${row.identifier || ''}` : row.identifier || '—'}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.titres_previous)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.titres_current)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.nominal_value)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.capital_souscrit)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.capital_appele)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{num(row.capital_libere)}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${row.status === 'suspect' ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-700'}`}>
                    {row.status === 'suspect' ? 'À vérifier' : 'OK'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
