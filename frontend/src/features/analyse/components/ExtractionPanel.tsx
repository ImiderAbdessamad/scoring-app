import { Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { DocumentExtraction, DocumentItem } from '@/types/analyse'

type Props = {
  extraction: DocumentExtraction | undefined
  document: DocumentItem | undefined
}

/** Données extraites du document, en liste « libellé → valeur » (colonne droite de la Vue générale). */
export function ExtractionPanel({ extraction, document }: Props) {
  return (
    <Card delay={0.1} className="overflow-hidden p-0">
      <div className="flex items-start gap-3 px-5 pb-3 pt-5">
        <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
          <Sparkles size={14} strokeWidth={1.9} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[16px] font-semibold text-[#1C1B1B]">Données extraites</div>
          <div className="truncate text-[11.5px] text-wb-muted" title={extraction?.title ?? document?.name}>
            {extraction?.title ?? document?.name ?? 'Document'}
          </div>
          {extraction && (
            <span className="mt-2 inline-flex rounded-[8px] bg-wb-surface px-2 py-0.5 text-[11px] font-semibold text-wb-muted">
              {extraction.flag}
            </span>
          )}
        </div>
      </div>

      {extraction ? (
        <dl className="wb-scroll m-0 max-h-[520px] overflow-y-auto px-5 pb-3">
          {extraction.fields.map((field) => (
            <div key={field.label} className="flex items-start justify-between gap-4 border-t border-wb-line py-2.5">
              <dt className="min-w-0">
                <div className="text-[12.5px] text-slate-600">{field.label}</div>
                <div className="mt-0.5 truncate text-[10.5px] text-wb-faint" title={field.source}>
                  {field.source}
                  {field.confidence == null ? '' : ` · ${field.confidence} %`}
                </div>
              </dt>
              <dd className="m-0 max-w-[55%] break-words text-right text-[13px] font-semibold text-[#1C1B1B]">
                {field.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="mx-5 mb-5 rounded-[14px] border border-dashed border-wb-line px-4 py-6 text-center text-[12.5px] text-wb-faint">
          Aucune extraction disponible pour ce document.
        </div>
      )}
    </Card>
  )
}
