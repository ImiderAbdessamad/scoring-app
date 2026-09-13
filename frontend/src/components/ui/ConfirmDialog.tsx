import { useEffect, useId, useRef, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { createPortal } from 'react-dom'

type Tone = 'neutral' | 'danger'

type Props = {
  open: boolean
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: Tone
  loading?: boolean
  icon?: ReactNode
  onConfirm: () => void
  onCancel: () => void
}

const TONE_ICON_BG: Record<Tone, string> = {
  neutral: 'bg-wb-accent-soft text-wb-accent',
  danger: 'bg-[#FEF2F2] text-[#DC2626]',
}


export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  tone = 'neutral',
  loading = false,
  icon,
  onConfirm,
  onCancel,
}: Props) {
  const titleId = useId()
  const descId = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const t = window.setTimeout(() => cancelRef.current?.focus(), 40)

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !loading) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.clearTimeout(t)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, loading, onCancel])

  if (typeof document === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.button
            type="button"
            aria-label="Fermer"
            disabled={loading}
            className="absolute inset-0 cursor-default border-0 bg-[#15110e]/55 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => {
              if (!loading) onCancel()
            }}
          />

          <motion.div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            className="relative z-10 w-full max-w-[400px] overflow-hidden rounded-[16px] border border-wb-line bg-white shadow-[0_24px_64px_rgba(16,24,40,0.28)]"
          >
            <div className="flex items-start gap-3.5 px-5 pt-5 pb-1">
              {icon && (
                <div
                  className={`flex h-11 w-11 flex-none items-center justify-center rounded-[12px] ${TONE_ICON_BG[tone]}`}
                >
                  {icon}
                </div>
              )}
              <div className="min-w-0 flex-1 pt-0.5">
                <h2 id={titleId} className="m-0 text-[16px] font-extrabold tracking-tight text-slate-900">
                  {title}
                </h2>
                {description && (
                  <div id={descId} className="mt-1.5 text-[13px] leading-relaxed text-wb-muted">
                    {description}
                  </div>
                )}
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={onCancel}
                className="flex h-8 w-8 flex-none cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-wb-faint transition-colors hover:bg-wb-surface hover:text-slate-700 disabled:opacity-40"
                aria-label="Fermer"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex flex-wrap justify-end gap-2 px-5 pt-4 pb-5">
              <Button
                ref={cancelRef}
                variant="secondary"
                disabled={loading}
                onClick={onCancel}
                className="min-w-[96px]"
              >
                {cancelLabel}
              </Button>
              <Button
                variant={tone === 'danger' ? 'danger' : 'primary'}
                disabled={loading}
                onClick={onConfirm}
                className="min-w-[120px]"
              >
                {loading ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Patientez…
                  </>
                ) : (
                  confirmLabel
                )}
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
