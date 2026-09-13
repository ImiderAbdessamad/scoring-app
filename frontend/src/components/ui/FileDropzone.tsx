import { FileText, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { isAllowedUpload, uploadRejectMessage, UPLOAD_ACCEPT } from '@/lib/uploadTypes'
import type { UploadedFileMeta } from '@/types/create-dossier'

type Props = {
  files: UploadedFileMeta[]
  onChange: (files: UploadedFileMeta[]) => void
  multiple?: boolean
  accept?: string
  label?: string
  error?: string
  maxFiles?: number
}

function toMeta(file: File): UploadedFileMeta {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`,
    name: file.name,
    size: file.size,
    mimeType: file.type || 'application/octet-stream',
    file,
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

export function FileDropzone({
  files,
  onChange,
  multiple = true,
  accept = UPLOAD_ACCEPT,
  label = 'Glissez vos fichiers ici ou cliquez pour parcourir',
  error,
  maxFiles = 8,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [rejectMsg, setRejectMsg] = useState<string | null>(null)

  function addFiles(list: FileList | null) {
    if (!list?.length) return
    const incoming = Array.from(list)
    const allowed = incoming.filter(isAllowedUpload)
    const rejected = incoming.filter((f) => !isAllowedUpload(f))

    if (rejected.length > 0) {
      setRejectMsg(uploadRejectMessage(rejected[0]))
    } else {
      setRejectMsg(null)
    }

    if (allowed.length === 0) return

    const metas = allowed.map(toMeta)
    if (multiple) {
      onChange([...files, ...metas].slice(0, maxFiles))
    } else {
      onChange(metas.slice(0, 1))
    }
  }

  function remove(id: string) {
    setRejectMsg(null)
    onChange(files.filter((f) => f.id !== id))
  }

  const displayError = error || rejectMsg

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          addFiles(e.dataTransfer.files)
        }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[14px] border border-dashed px-4 py-7 transition-colors',
          dragOver
            ? 'border-wb-accent bg-wb-accent-soft'
            : displayError
              ? 'border-red-300 bg-red-50/40'
              : 'border-[#D5DAE2] bg-[#FAFBFC] hover:border-wb-accent-border hover:bg-wb-accent-soft/40',
        ].join(' ')}
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-wb-accent ring-1 ring-wb-accent-border">
          <Upload size={18} strokeWidth={1.8} />
        </div>
        <div className="text-center">
          <div className="text-[13px] font-semibold text-slate-800">{label}</div>
          <div className="mt-1 text-[11.5px] text-wb-faint">
            PDF, PNG, JPG · max {maxFiles} fichier(s)
          </div>
        </div>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple={multiple}
          accept={accept}
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </button>

      {displayError && (
        <span className="text-[11.5px] font-medium text-wb-danger">{displayError}</span>
      )}

      {files.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {files.map((f) => (
            <li
              key={f.id}
              className="flex items-center gap-2.5 rounded-[10px] border border-wb-line bg-white px-3 py-2"
            >
              <FileText size={16} className="flex-none text-wb-accent" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-semibold text-slate-800">
                  {f.name}
                </div>
                <div className="text-[11px] text-wb-faint">{formatSize(f.size)}</div>
              </div>
              <button
                type="button"
                onClick={() => remove(f.id)}
                className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-wb-faint hover:bg-wb-surface hover:text-slate-700"
                aria-label={`Retirer ${f.name}`}
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
