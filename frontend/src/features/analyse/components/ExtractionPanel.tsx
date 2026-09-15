import { Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { DocumentExtraction, DocumentItem } from '@/types/analyse'

type Props = {
  extraction: DocumentExtraction | undefined
  document: DocumentItem | undefined
}

export function ExtractionPanel({ extraction, document }: Props) {
  return (
    <Card delay={0.1} className="p-4">
      <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-wb-accent-soft text-wb-accent">
            <Sparkles size={14} strokeWidth={1.9} />
          </span>
          <div>
            <div className="text-[13px] font-bold text-slate-900">
              {extraction?.title ?? document?.name ?? 'Extraction IA'}
            </div>
            <div className="text-[10.5px] text-wb-faint">Champs extraits automatiquement</div>
          </div>
        </div>
        {extraction && (
          <span className="rounded-full bg-wb-surface px-2.5 py-1 text-[11px] font-semibold text-wb-muted">
            {extraction.flag}
          </span>
        )}
      </div>

      {extraction ? (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {extraction.fields.map((field) => (
            <div key={field.label} className="rounded-[10px] border border-wb-line bg-wb-surface/60 p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10.5px] font-bold uppercase tracking-[0.03em] text-wb-faint">
                  {field.label}
                </span>
                <span className="text-[10px] font-bold tabular-nums text-wb-faint">
                  {field.confidence == null ? '—' : `${field.confidence}%`}
                </span>
              </div>
              <div className="mt-1 break-words text-[13.5px] font-bold text-slate-900">{field.value}</div>
              <div className="mt-0.5 break-words text-[10.5px] text-wb-faint">{field.source}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-[10px] border border-dashed border-wb-line px-4 py-6 text-center text-[12.5px] text-wb-faint">
          Aucune extraction disponible pour ce document.
        </div>
      )}
    </Card>
  )
}
