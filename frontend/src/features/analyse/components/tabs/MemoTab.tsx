import { CheckCircle2, Info, PenLine, TriangleAlert } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { MemoBlock } from '@/types/analyse'

type Props = {
  memo: MemoBlock
  memoSigned: boolean
  onToggleSign: () => void
}

export function MemoTab({ memo, memoSigned, onToggleSign }: Props) {
  return (
    <Card delay={0.05} className="overflow-hidden p-0">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-wb-line bg-[#FAFBFC] px-6 py-4">
        <img src="/logo-horizontal.png" alt="Wafabail" className="h-7 w-auto object-contain" />
        <div className="text-right">
          <div className="text-[11px] font-semibold text-wb-faint">{memo.refLine}</div>
        </div>
      </div>

      <div className="px-6 py-5">
        <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-wb-ink px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.04em] text-wb-accent">
          Mémo généré par IA
        </div>
        <h2 className="m-0 mt-2 text-[19px] font-extrabold tracking-tight text-slate-900">{memo.title}</h2>
        <p className="m-0 mt-1 text-[12.5px] text-wb-muted">{memo.subtitle}</p>

        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-[12px] border border-wb-accent-border bg-wb-accent-soft px-4 py-3">
          <span className="text-[13.5px] font-extrabold text-wb-accent">{memo.recommendation}</span>
          <span className="h-1 w-1 rounded-full bg-wb-accent/50" />
          <span className="text-[12.5px] font-semibold text-[#92400E]">{memo.scoreLine}</span>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2.5 sm:grid-cols-3">
          {memo.clientGrid.map((g) => (
            <div key={g.label}>
              <div className="text-[10px] uppercase tracking-[0.03em] text-wb-faint">{g.label}</div>
              <div className="mt-0.5 truncate text-[12.5px] font-bold text-slate-800">{g.value}</div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-col gap-5">
          {memo.sections.map((section) => (
            <div key={section.title} className="border-t border-[#F1F2F4] pt-5">
              <div className="mb-2.5 text-[13px] font-extrabold text-slate-900">{section.title}</div>

              {section.paragraphs?.map((p, i) => (
                <p key={i} className="m-0 mb-2 text-[12.5px] leading-relaxed text-wb-muted last:mb-0">
                  {p}
                </p>
              ))}

              {section.table && (
                <div className="wb-scroll mt-3 overflow-x-auto rounded-[10px] border border-wb-line">
                  <table className="w-full min-w-[440px] border-collapse text-[12.5px]">
                    <thead>
                      <tr className="bg-[#FAFBFC] text-left text-[10.5px] font-bold uppercase tracking-[0.03em] text-wb-faint">
                        {section.table.headers.map((h) => (
                          <th key={h} className="px-4 py-2">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {section.table.rows.map((row, ri) => (
                        <tr key={ri} className="border-t border-[#F1F2F4]">
                          {row.map((cell, ci) => (
                            <td
                              key={ci}
                              className={`px-4 py-2 ${ci === 0 ? 'font-semibold text-slate-800' : 'tabular-nums text-wb-muted'}`}
                            >
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {section.tableNote && (
                <p className="m-0 mt-1.5 text-[11px] text-wb-faint">{section.tableNote}</p>
              )}

              {section.chips && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {section.chips.map((chip) => (
                    <span
                      key={chip.label}
                      className={[
                        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold',
                        chip.ok ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FEF2F2] text-[#DC2626]',
                      ].join(' ')}
                    >
                      {chip.label} · {chip.value}
                    </span>
                  ))}
                </div>
              )}

              {section.risks && (
                <div className="mt-3 flex flex-col gap-2">
                  {section.risks.map((risk, i) => (
                    <div
                      key={i}
                      className={[
                        'flex items-start gap-2 rounded-[9px] px-3 py-2 text-[12px]',
                        risk.tone === 'warn' ? 'bg-[#FFF8EC] text-[#92400E]' : 'bg-[#EFF6FF] text-[#1D4ED8]',
                      ].join(' ')}
                    >
                      {risk.tone === 'warn' ? (
                        <TriangleAlert size={13} className="mt-0.5 flex-none" />
                      ) : (
                        <Info size={13} className="mt-0.5 flex-none" />
                      )}
                      {risk.text}
                    </div>
                  ))}
                </div>
              )}

              {section.conditions && (
                <ul className="m-0 mt-2 flex list-none flex-col gap-1.5 p-0">
                  {section.conditions.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12.5px] text-slate-700">
                      <CheckCircle2 size={14} className="mt-0.5 flex-none text-wb-accent" />
                      {c}
                    </li>
                  ))}
                </ul>
              )}

              {section.conclusionBanner && (
                <div className="mt-2 rounded-[10px] bg-wb-ink px-4 py-3 text-[13px] font-bold text-white">
                  {section.conclusionBanner}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-wb-line bg-[#FAFBFC] px-6 py-4">
        <div>
          <div className="text-[12.5px] font-bold text-slate-800">{memo.signerName}</div>
          <div className="text-[11px] text-wb-faint">{memo.signerRole}</div>
        </div>
        {memoSigned ? (
          <span className="inline-flex items-center gap-1.5 rounded-[9px] bg-[#ECFDF5] px-3 py-2 text-[12.5px] font-bold text-[#15803D]">
            <CheckCircle2 size={15} />
            Mémo signé électroniquement
          </span>
        ) : (
          <button
            type="button"
            onClick={onToggleSign}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-[9px] bg-wb-ink px-3.5 py-2 text-[12.5px] font-bold text-white transition-[filter] hover:brightness-110"
          >
            <PenLine size={14} />
            Signer le mémo
          </button>
        )}
      </div>
    </Card>
  )
}
