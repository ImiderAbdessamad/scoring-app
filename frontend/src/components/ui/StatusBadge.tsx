import { STATUS_META } from '@/lib/format'
import type { DossierStatus } from '@/types/dossier'

export function StatusBadge({ status }: { status: DossierStatus }) {
  const meta = STATUS_META[status]
  return (
    <span
      className="inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-[11.5px] font-semibold"
      style={{ color: meta.color, background: meta.bg }}
    >
      {meta.label}
    </span>
  )
}
