import { Check, Package, ShieldCheck, X } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { BienBlock } from '@/types/analyse'

type Props = {
  bien: BienBlock
}

export function BienTab({ bien }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Card delay={0.05} className="p-5">
        <div className="mb-4 flex items-center gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-[10px] bg-wb-accent-soft text-wb-accent">
            <Package size={17} strokeWidth={1.8} />
          </span>
          <div>
            <div className="text-[14px] font-bold text-slate-900">{bien.title}</div>
            <div className="text-[12px] text-wb-muted">{bien.subtitle}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SpecCard label="Valeur du bien" value={bien.assetValueLabel} />
          <SpecCard label="Montant financé" value={bien.financedLabel} accent />
          <SpecCard label="Durée" value={bien.durationLabel} />
          <SpecCard label="Valeur résiduelle" value={bien.residualLabel ?? 'Non contractuel'} />
        </div>
      </Card>

      <Card delay={0.1} className="overflow-hidden p-0">
        <div className="border-b border-wb-line px-5 py-3 text-[13px] font-bold text-slate-900">
          Détail des unités financées
        </div>
        <div className="wb-scroll overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[12.5px]">
            <thead>
              <tr className="bg-[#FAFBFC] text-left text-[10.5px] font-bold uppercase tracking-[0.03em] text-wb-faint">
                <th className="px-5 py-2.5">Qté</th>
                <th className="px-3 py-2.5">Désignation</th>
                <th className="px-3 py-2.5">Marque</th>
                <th className="px-3 py-2.5">Modèle</th>
                <th className="px-3 py-2.5">Année</th>
                <th className="px-5 py-2.5 text-right">Valeur</th>
              </tr>
            </thead>
            <tbody>
              {bien.units.map((u, i) => (
                <tr key={i} className="border-t border-[#F1F2F4]">
                  <td className="px-5 py-2.5 font-semibold text-slate-700">{u.qty}</td>
                  <td className="px-3 py-2.5 font-semibold text-slate-800">{u.designation}</td>
                  <td className="px-3 py-2.5 text-wb-muted">{u.marque}</td>
                  <td className="px-3 py-2.5 text-wb-muted">{u.modele}</td>
                  <td className="px-3 py-2.5 tabular-nums text-wb-muted">{u.annee}</td>
                  <td className="px-5 py-2.5 text-right font-bold tabular-nums text-slate-900">{u.valeur}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-wb-line bg-[#FAFBFC] px-5 py-3">
          <span className="text-[12px] font-semibold text-wb-muted">Total TTC</span>
          <span className="text-[14px] font-extrabold text-slate-900">{bien.totalTtcLabel}</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card delay={0.15} className="p-5">
          <div className="mb-3 text-[13px] font-bold text-slate-900">Conditions du contrat</div>
          <div className="flex flex-col gap-2">
            {bien.specs.map((s) => (
              <div key={s.key} className="flex items-center justify-between border-b border-[#F5F6F7] py-1.5 last:border-b-0">
                <span className="text-[12px] text-wb-muted">{s.key}</span>
                <span className="text-[12.5px] font-bold text-slate-800">{s.value}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card delay={0.2} className="p-5">
          <div className="mb-3 text-[13px] font-bold text-slate-900">Échéancier</div>
          <div className="flex flex-col gap-2">
            {bien.schedule.map((s) => (
              <div
                key={s.label}
                className={[
                  'flex items-center justify-between rounded-[9px] px-3 py-2',
                  s.highlight ? 'bg-wb-accent-soft' : 'bg-wb-surface/60',
                ].join(' ')}
              >
                <div>
                  <div className={`text-[12.5px] font-bold ${s.highlight ? 'text-wb-accent' : 'text-slate-800'}`}>
                    {s.label}
                  </div>
                  <div className="text-[10.5px] text-wb-faint">{s.count} échéance(s)</div>
                </div>
                <span className={`text-[13px] font-extrabold tabular-nums ${s.highlight ? 'text-wb-accent' : 'text-slate-900'}`}>
                  {s.amount}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#F1F2F4] pt-3 text-[12px]">
            <span className="text-wb-muted">Coût total du crédit</span>
            <span className="font-bold text-slate-800">{bien.creditCostLabel}</span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[12px]">
            <span className="text-wb-muted">Coût total de l’opération</span>
            <span className="font-bold text-slate-800">{bien.totalCostLabel}</span>
          </div>
        </Card>
      </div>

      <Card delay={0.25} className="p-5">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck size={15} className="text-wb-accent" />
          <span className="text-[13px] font-bold text-slate-900">Garanties</span>
        </div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {bien.guarantees.map((g) => (
            <div key={g.title} className="flex items-start gap-2.5 rounded-[10px] border border-wb-line p-3">
              <span
                className={[
                  'mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full',
                  g.ok ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FEF2F2] text-[#DC2626]',
                ].join(' ')}
              >
                {g.ok ? <Check size={12} strokeWidth={3} /> : <X size={12} strokeWidth={3} />}
              </span>
              <div className="min-w-0">
                <div className="text-[12.5px] font-bold text-slate-800">{g.title}</div>
                <div className="text-[11px] text-wb-faint">{g.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function SpecCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-[10px] border border-wb-line bg-wb-surface/60 p-3">
      <div className="text-[10.5px] uppercase tracking-[0.03em] text-wb-faint">{label}</div>
      <div className={`mt-1 text-[15px] font-extrabold tabular-nums ${accent ? 'text-wb-accent' : 'text-slate-900'}`}>
        {value}
      </div>
    </div>
  )
}
