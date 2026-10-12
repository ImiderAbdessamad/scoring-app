import { Package } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { BienBlock } from '@/types/analyse'

type Props = {
  bien: BienBlock
}

/** Bien financé : chiffres clés, puis fiche (unités financées | conditions et échéancier). */
export function BienTab({ bien }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
            <Package size={18} strokeWidth={1.8} />
          </span>
          <div className="min-w-0">
            <div className="truncate text-[16px] font-semibold text-[#1C1B1B]">{bien.title}</div>
            <div className="truncate text-[12.5px] text-wb-muted">{bien.subtitle}</div>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-wb-line pt-5 lg:grid-cols-4">
          <KeyFigure label="Valeur du bien" value={bien.assetValueLabel} />
          <KeyFigure label="Montant financé" value={bien.financedLabel} accent />
          <KeyFigure label="Durée" value={bien.durationLabel} />
          <KeyFigure label="Valeur résiduelle" value={bien.residualLabel ?? 'Non contractuel'} />
        </div>
      </Card>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card delay={0.1} className="overflow-hidden p-0">
            <div className="px-6 py-4 text-[16px] font-semibold text-[#1C1B1B]">Détail des unités financées</div>
            <div className="wb-scroll overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-[13px]">
                <thead className="bg-[#F8FAFC]">
                  <tr className="text-left text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
                    <th className="border-y border-wb-line px-6 py-3">Qté</th>
                    <th className="border-y border-wb-line px-3 py-3">Désignation</th>
                    <th className="border-y border-wb-line px-3 py-3">Marque</th>
                    <th className="border-y border-wb-line px-3 py-3">Modèle</th>
                    <th className="border-y border-wb-line px-3 py-3">Année</th>
                    <th className="border-y border-wb-line px-6 py-3 text-right">Valeur</th>
                  </tr>
                </thead>
                <tbody>
                  {bien.units.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-6 py-6 text-center text-wb-muted">
                        Aucune unité renseignée.
                      </td>
                    </tr>
                  )}
                  {bien.units.map((u, i) => (
                    <tr key={i} className="border-b border-wb-line transition-colors last:border-b-0 hover:bg-wb-accent-soft/40">
                      <td className="px-6 py-3 font-semibold text-slate-700">{u.qty}</td>
                      <td className="px-3 py-3 font-semibold text-[#1C1B1B]">{u.designation}</td>
                      <td className="px-3 py-3 text-wb-muted">{u.marque}</td>
                      <td className="px-3 py-3 text-wb-muted">{u.modele}</td>
                      <td className="px-3 py-3 tabular-nums text-wb-muted">{u.annee}</td>
                      <td className="px-6 py-3 text-right font-bold tabular-nums text-[#1C1B1B]">{u.valeur}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-wb-line bg-[#F8FAFC] px-6 py-3.5">
              <span className="text-[13px] font-semibold text-slate-600">Total TTC</span>
              <span className="text-[15px] font-bold tabular-nums text-[#1C1B1B]">{bien.totalTtcLabel}</span>
            </div>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4">
          <Card delay={0.2} className="p-6">
            <div className="mb-2 text-[16px] font-semibold text-[#1C1B1B]">Conditions du contrat</div>
            <dl className="m-0">
              {bien.specs.map((s) => (
                <div key={s.key} className="flex items-start justify-between gap-4 border-t border-wb-line py-2.5 first:border-t-0">
                  <dt className="text-[12.5px] text-slate-600">{s.key}</dt>
                  <dd className="m-0 text-right text-[13px] font-semibold text-[#1C1B1B]">{s.value}</dd>
                </div>
              ))}
            </dl>
          </Card>

          <Card delay={0.25} className="p-6">
            <div className="mb-3 text-[16px] font-semibold text-[#1C1B1B]">Échéancier</div>
            <div className="flex flex-col gap-2">
              {bien.schedule.map((s) => (
                <div
                  key={s.label}
                  className={[
                    'flex items-center justify-between gap-3 rounded-[14px] px-4 py-2.5',
                    s.highlight ? 'border-l-2 border-wb-accent bg-wb-accent-soft' : 'bg-wb-surface',
                  ].join(' ')}
                >
                  <div className="min-w-0">
                    <div className={`text-[13px] font-semibold ${s.highlight ? 'text-wb-accent-text' : 'text-[#1C1B1B]'}`}>
                      {s.label}
                    </div>
                    <div className="text-[11.5px] text-wb-muted">{s.count} échéance(s)</div>
                  </div>
                  <span className={`flex-none text-[14px] font-bold tabular-nums ${s.highlight ? 'text-wb-accent-text' : 'text-[#1C1B1B]'}`}>
                    {s.amount}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-wb-line pt-3">
              <div className="flex items-center justify-between py-1 text-[12.5px]">
                <span className="text-slate-600">Coût total du crédit</span>
                <span className="font-semibold tabular-nums text-[#1C1B1B]">{bien.creditCostLabel}</span>
              </div>
              <div className="flex items-center justify-between py-1 text-[12.5px]">
                <span className="text-slate-600">Coût total de l’opération</span>
                <span className="font-bold tabular-nums text-[#1C1B1B]">{bien.totalCostLabel}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
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
