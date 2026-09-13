import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { StepEntreprise } from '@/features/dossiers/create/steps/StepEntreprise'
import { StepFinancement } from '@/features/dossiers/create/steps/StepFinancement'
import { StepFournisseur } from '@/features/dossiers/create/steps/StepFournisseur'
import {
  INITIAL_CREATE_FORM,
  validateEntreprise,
  validateFinancement,
  validateFournisseur,
  type StepErrors,
} from '@/features/dossiers/create/validation'
import { createDossier } from '@/services/api/dossiers'
import type { CreateDossierFormState } from '@/types/create-dossier'

const STEPS = [
  { id: 1, label: 'Entreprise' },
  { id: 2, label: 'Financement' },
  { id: 3, label: 'Bien' },
] as const

type Props = {
  open: boolean
  onClose: () => void
}

export function CreateDossierWizard({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<CreateDossierFormState>(INITIAL_CREATE_FORM)
  const [errors, setErrors] = useState<StepErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [successId, setSuccessId] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setStep(1)
    setForm(structuredClone(INITIAL_CREATE_FORM))
    setErrors({})
    setSubmitting(false)
    setSubmitError(null)
    setSuccessId(null)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose, submitting])

  function validateCurrent(): boolean {
    const errs =
      step === 1
        ? validateEntreprise(form.entreprise)
        : step === 2
          ? validateFinancement(form.financement)
          : validateFournisseur(form.fournisseurBien)
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  function next() {
    if (!validateCurrent()) return
    setStep((s) => Math.min(3, s + 1))
  }

  function back() {
    setErrors({})
    setStep((s) => Math.max(1, s - 1))
  }

  async function submit() {
    if (!validateCurrent()) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const res = await createDossier(form)
      setSuccessId(res.id)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Échec de la création')
    } finally {
      setSubmitting(false)
    }
  }

  function finish() {
    onClose()
    if (successId) {
      navigate(`/analyse/${successId}`)
      return
    }
    navigate('/dossiers')
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[80] flex items-end justify-center sm:items-center sm:p-6">
          <motion.button
            type="button"
            aria-label="Fermer"
            className="absolute inset-0 border-0 bg-wb-ink/45 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !submitting && onClose()}
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-dossier-title"
            initial={{ opacity: 0, y: 28, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            className="relative z-10 flex max-h-[min(920px,100dvh)] w-full max-w-[640px] flex-col overflow-hidden rounded-t-2xl border border-wb-line bg-white shadow-[0_24px_80px_rgba(16,24,40,0.28)] sm:rounded-2xl"
          >
            <header className="flex flex-none items-start justify-between gap-3 border-b border-wb-line px-5 py-4 sm:px-6">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-wb-accent">
                  F-DOS-001
                </div>
                <h2
                  id="create-dossier-title"
                  className="m-0 mt-0.5 text-[18px] font-extrabold tracking-tight text-slate-900"
                >
                  Nouveau dossier
                </h2>
                <p className="m-0 mt-0.5 text-[12px] text-wb-muted">
                  Création guidée en 3 étapes
                </p>
              </div>
              <button
                type="button"
                onClick={() => !submitting && onClose()}
                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border-0 bg-wb-surface text-wb-muted hover:text-slate-800"
                aria-label="Fermer"
              >
                <X size={16} />
              </button>
            </header>

            {!successId && (
              <div className="flex flex-none items-center gap-2 border-b border-wb-line px-5 py-3.5 sm:px-6">
                {STEPS.map((s, i) => {
                  const done = step > s.id
                  const active = step === s.id
                  return (
                    <div key={s.id} className="flex min-w-0 flex-1 items-center gap-2">
                      <div
                        className={[
                          'flex h-7 w-7 flex-none items-center justify-center rounded-full text-[11px] font-bold transition-colors',
                          done || active
                            ? 'bg-wb-accent text-white'
                            : 'bg-wb-surface text-wb-faint',
                        ].join(' ')}
                      >
                        {done ? <Check size={14} strokeWidth={2.4} /> : s.id}
                      </div>
                      <div className="min-w-0">
                        <div
                          className={[
                            'truncate text-[12px] font-semibold',
                            active ? 'text-slate-900' : 'text-wb-faint',
                          ].join(' ')}
                        >
                          {s.label}
                        </div>
                      </div>
                      {i < STEPS.length - 1 && (
                        <div
                          className={[
                            'mx-1 hidden h-px flex-1 sm:block',
                            done ? 'bg-wb-accent' : 'bg-wb-line',
                          ].join(' ')}
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            <div className="wb-scroll min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
              {successId ? (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center py-10 text-center"
                >
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-wb-success">
                    <Check size={28} strokeWidth={2.2} />
                  </div>
                  <h3 className="mt-4 text-[17px] font-extrabold text-slate-900">
                    Dossier créé
                  </h3>
                  <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-wb-muted">
                    Référence{' '}
                    <span className="font-mono font-bold text-wb-accent">{successId}</span>
                    . L’analyse est lancée automatiquement ; les dossiers suivants passent à tour de rôle.
                  </p>
                  <div className="mt-6 flex gap-2">
                    <Button variant="secondary" onClick={onClose}>
                      Fermer
                    </Button>
                    <Button variant="primary" onClick={finish}>
                      Suivre l’analyse
                    </Button>
                  </div>
                </motion.div>
              ) : (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={step}
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -12 }}
                    transition={{ duration: 0.2 }}
                  >
                    {step === 1 && (
                      <StepEntreprise
                        value={form.entreprise}
                        errors={errors}
                        onChange={(entreprise) =>
                          setForm((f) => ({ ...f, entreprise }))
                        }
                      />
                    )}
                    {step === 2 && (
                      <StepFinancement
                        value={form.financement}
                        errors={errors}
                        onChange={(financement) =>
                          setForm((f) => ({ ...f, financement }))
                        }
                      />
                    )}
                    {step === 3 && (
                      <StepFournisseur
                        value={form.fournisseurBien}
                        errors={errors}
                        onChange={(fournisseurBien) =>
                          setForm((f) => ({ ...f, fournisseurBien }))
                        }
                      />
                    )}
                  </motion.div>
                </AnimatePresence>
              )}

              {submitError && (
                <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-[12.5px] text-red-700">
                  {submitError}
                </div>
              )}
            </div>

            {!successId && (
              <footer className="flex flex-none items-center justify-between gap-3 border-t border-wb-line px-5 py-3.5 sm:px-6">
                <Button
                  variant="ghost"
                  onClick={step === 1 ? onClose : back}
                  disabled={submitting}
                >
                  {step === 1 ? 'Annuler' : 'Retour'}
                </Button>
                <div className="flex items-center gap-2">
                  <span className="hidden text-[11.5px] text-wb-faint sm:inline">
                    Étape {step} / 3
                  </span>
                  {step < 3 ? (
                    <Button variant="primary" onClick={next}>
                      Continuer
                    </Button>
                  ) : (
                    <Button variant="primary" onClick={submit} disabled={submitting}>
                      {submitting ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          Création…
                        </>
                      ) : (
                        'Créer le dossier'
                      )}
                    </Button>
                  )}
                </div>
              </footer>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
