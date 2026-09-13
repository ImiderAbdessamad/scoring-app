import { useRef } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, FileCheck2, FileText, Upload } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { DocumentsBlock } from '@/types/analyse'

type Props = {
  documents: DocumentsBlock
  selectedDocId: string
  onSelect: (id: string) => void
  uploadable?: boolean
  uploadingDocId?: string | null
  onUpload?: (docId: string, file: File) => void
}

export function DocumentsPanel({
  documents,
  selectedDocId,
  onSelect,
  uploadable = false,
  uploadingDocId = null,
  onUpload,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const pendingDocIdRef = useRef<string | null>(null)

  const barColor =
    documents.completenessPct >= 85 ? '#16A34A' : documents.completenessPct >= 60 ? '#B45309' : '#DC2626'

  function openUpload(docId: string) {
    if (!uploadable || !onUpload) return
    pendingDocIdRef.current = docId
    inputRef.current?.click()
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    const docId = pendingDocIdRef.current
    e.target.value = ''
    pendingDocIdRef.current = null
    if (file && docId && onUpload) {
      onUpload(docId, file)
    }
  }

  return (
    <Card delay={0.05} className="p-4">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="mb-3 flex items-center justify-between">
        <div className="text-[13px] font-bold text-slate-900">
          Documents · {documents.present}/{documents.total}
        </div>
        <span className="text-[12px] font-bold tabular-nums" style={{ color: barColor }}>
          {documents.completenessPct}%
        </span>
      </div>

      {documents.required && documents.required.length > 0 && (
        <ul className="mb-3 m-0 flex list-none flex-col gap-1 p-0 text-[12px]">
          {documents.required.map((item) => (
            <li key={item.id} className="flex items-center gap-2 text-slate-700">
              <span className={item.ok ? 'text-emerald-700' : 'text-wb-faint'}>{item.ok ? 'OK' : 'Manquant'}</span>
              {item.name}
            </li>
          ))}
        </ul>
      )}

      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-[#EEF0F3]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${documents.completenessPct}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="h-full rounded-full"
          style={{ background: barColor }}
        />
      </div>

      {uploadable && (
        <p className="mb-3 text-[11px] text-wb-muted">
          Ajoutez une liasse ou une pièce : l’analyse se relance automatiquement (file d’attente).
        </p>
      )}
      {uploadable && onUpload && (
        <button
          type="button"
          onClick={() => openUpload('__add__')}
          disabled={uploadingDocId === '__add__'}
          className="mb-3 inline-flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-[10px] border border-dashed border-wb-line bg-white px-3 py-2 text-[12px] font-semibold text-slate-700 hover:bg-wb-surface disabled:opacity-60"
        >
          <Upload size={14} strokeWidth={1.9} />
          {uploadingDocId === '__add__' ? 'Ajout et analyse…' : 'Ajouter un document et analyser'}
        </button>
      )}

      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {documents.items.length === 0 && (
          <li className="rounded-[10px] bg-wb-surface px-3 py-4 text-center text-[12px] text-wb-muted">
            Aucun document déposé pour ce dossier.
          </li>
        )}
        {documents.items.map((doc) => {
          const active = doc.id === selectedDocId
          const uploading = uploadingDocId === doc.id
          return (
            <li key={doc.id}>
              <button
                type="button"
                onClick={() => onSelect(doc.id)}
                disabled={uploading}
                className={[
                  'flex w-full cursor-pointer items-center gap-2.5 rounded-[10px] border-0 px-2.5 py-2 text-left transition-colors',
                  active ? 'bg-wb-accent-soft' : 'hover:bg-wb-surface',
                  uploading ? 'opacity-60' : '',
                ].join(' ')}
              >
                <span
                  className={[
                    'flex h-8 w-8 flex-none items-center justify-center rounded-[8px]',
                    active ? 'bg-white text-wb-accent' : 'bg-wb-surface text-wb-muted',
                  ].join(' ')}
                >
                  <FileText size={14} strokeWidth={1.9} />
                </span>
                <div className="min-w-0 flex-1">
                  <div
                    className={[
                      'truncate text-[12.5px] font-semibold',
                      active ? 'text-wb-accent' : 'text-slate-800',
                    ].join(' ')}
                  >
                    {doc.name}
                  </div>
                  <div className="truncate text-[10.5px] text-wb-faint">
                    {uploading ? 'Envoi en cours…' : doc.meta}
                  </div>
                </div>
                {!uploadable && doc.confidence > 0 && (
                  <span className="flex-none text-[10.5px] font-bold tabular-nums text-wb-faint">
                    {doc.confidence}%
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>

      {documents.missing.length > 0 && (
        <div className="mt-3.5 border-t border-[#F1F2F4] pt-3.5">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.04em] text-wb-faint">
            <AlertTriangle size={12} className="text-[#B45309]" />
            Pièces manquantes
          </div>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {documents.missing.map((m) => {
              const uploading = uploadingDocId === m.id
              return (
                <li key={m.id}>
                  {uploadable ? (
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(m.id)
                        openUpload(m.id)
                      }}
                      disabled={uploading}
                      className={[
                        'flex w-full cursor-pointer items-start gap-2 rounded-[10px] border-0 bg-[#FFF8EC] px-2.5 py-2 text-left transition-colors hover:bg-[#FFEBD7]',
                        uploading ? 'opacity-60' : '',
                      ].join(' ')}
                    >
                      <Upload size={14} className="mt-0.5 flex-none text-[#B45309]" strokeWidth={1.9} />
                      <div className="min-w-0">
                        <div className="truncate text-[12px] font-semibold text-[#92400E]">{m.name}</div>
                        <div className="truncate text-[10.5px] text-[#B45309]/80">
                          {uploading ? 'Envoi en cours…' : m.meta}
                        </div>
                      </div>
                    </button>
                  ) : (
                    <div className="flex items-start gap-2 rounded-[10px] bg-[#FFF8EC] px-2.5 py-2">
                      <FileCheck2 size={14} className="mt-0.5 flex-none text-[#B45309]" strokeWidth={1.9} />
                      <div className="min-w-0">
                        <div className="truncate text-[12px] font-semibold text-[#92400E]">{m.name}</div>
                        <div className="truncate text-[10.5px] text-[#B45309]/80">{m.meta}</div>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </Card>
  )
}
