import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Field, NumericInput, TextInput } from '@/components/ui/FormField'
import { FancySelect } from '@/components/ui/FancySelect'
import { FileDropzone } from '@/components/ui/FileDropzone'
import { extractBilanIdentity } from '@/services/api/dossiers'
import {
  conflictSummary,
  mergeFilesIntoStateSequential,
  stateFromForm,
  stateToFields,
} from '@/lib/extractEntreprise'
import { logPipeline } from '@/lib/extraction/debug'
import { SECTEURS, type EntrepriseFormData, type UploadedFileMeta } from '@/types/create-dossier'
import type { StepErrors } from '@/features/dossiers/create/validation'

const SECTEUR_OPTIONS = SECTEURS.map((s) => ({
  value: s,
  label: s,
  description: s === 'Autre' ? 'Préciser manuellement' : undefined,
}))

type Props = {
  value: EntrepriseFormData
  errors: StepErrors
  onChange: (next: EntrepriseFormData) => void
}

type QueueItem = UploadedFileMeta

export function StepEntreprise({ value, errors, onChange }: Props) {
  const isAutre = value.secteurPreset === 'Autre'
  const [extracting, setExtracting] = useState(false)
  const [extractHint, setExtractHint] = useState<string | null>(null)
  const [progressLabel, setProgressLabel] = useState<string | null>(null)

  const valueRef = useRef(value)
  valueRef.current = value

  const queueRef = useRef<QueueItem[]>([])
  const runningRef = useRef(false)

  function applyFieldsToForm(
    current: EntrepriseFormData,
    fields: Partial<{
      ice: string
      rc: string
      raisonSociale: string
      identifiantFiscal: string
    }>,
  ): EntrepriseFormData {
    const patch: Partial<EntrepriseFormData> = {}
    if (fields.ice && !current.ice.trim()) patch.ice = fields.ice
    if (fields.rc && !current.rc.trim()) patch.rc = fields.rc
    if (fields.raisonSociale && !current.raisonSociale.trim()) {
      patch.raisonSociale = fields.raisonSociale
    }
    if (fields.identifiantFiscal && !current.identifiantFiscal.trim()) {
      patch.identifiantFiscal = fields.identifiantFiscal
    }
    if (Object.keys(patch).length === 0) return current
    return { ...current, ...patch }
  }

  async function extractFromBilan(file: File) {
    const identity = await extractBilanIdentity(file)
    return applyFieldsToForm(valueRef.current, {
      ice: identity.ice || undefined,
      rc: identity.rc || undefined,
      raisonSociale: identity.raison_sociale || undefined,
      identifiantFiscal: identity.identifiant_fiscal || undefined,
    })
  }

  async function drainQueue() {
    if (runningRef.current) return
    runningRef.current = true
    setExtracting(true)

    try {
      while (queueRef.current.length > 0) {
        const batch = queueRef.current.splice(0, queueRef.current.length)
        logPipeline('queue drain', { count: batch.length })

        let state = stateFromForm({
          ice: valueRef.current.ice,
          rc: valueRef.current.rc,
          raisonSociale: valueRef.current.raisonSociale,
        })

        const before = {
          ice: valueRef.current.ice,
          rc: valueRef.current.rc,
          raisonSociale: valueRef.current.raisonSociale,
          identifiantFiscal: valueRef.current.identifiantFiscal,
        }

        const pdfs = batch.filter(
          (item) =>
            item.file &&
            (item.file.type === 'application/pdf' || item.name.toLowerCase().endsWith('.pdf')),
        )
        for (const item of pdfs) {
          if (!item.file) continue
          setProgressLabel(`Lecture du bilan — ${item.name}`)
          try {
            const next = await extractFromBilan(item.file)
            valueRef.current = next
            onChange(next)
          } catch (err) {
            logPipeline('bilan identity api failed, fallback OCR', {
              file: item.name,
              error: err instanceof Error ? err.message : String(err),
            })
          }
        }

        const identityFilled =
          Boolean(valueRef.current.ice.trim()) &&
          Boolean(valueRef.current.raisonSociale.trim())

        if (identityFilled && valueRef.current.rc.trim()) {
          const newlyFilled: string[] = []
          if (valueRef.current.ice && !before.ice.trim()) newlyFilled.push('ICE')
          if (valueRef.current.rc && !before.rc.trim()) newlyFilled.push('RC')
          if (valueRef.current.raisonSociale && !before.raisonSociale.trim()) {
            newlyFilled.push('Raison sociale')
          }
          if (valueRef.current.identifiantFiscal && !before.identifiantFiscal.trim()) {
            newlyFilled.push('Identifiant fiscal')
          }
          setExtractHint(
            newlyFilled.length > 0
              ? `Champs préremplis depuis le bilan : ${newlyFilled.join(', ')}. Vous pouvez les modifier.`
              : 'Identité lue sur le bilan — vous pouvez corriger les champs si besoin.',
          )
          continue
        }

        state = await mergeFilesIntoStateSequential(batch, state, (progress) => {
          setProgressLabel(
            `Extraction ${progress.index}/${progress.total} — ${progress.fileName}`,
          )
          logPipeline('progressive update', {
            file: progress.fileName,
            ice: progress.fields.ice ?? '—',
            rc: progress.fields.rc ?? '—',
            raison: progress.fields.raisonSociale ?? '—',
          })

          const next = applyFieldsToForm(
            { ...valueRef.current, documents: valueRef.current.documents },
            progress.fields,
          )
          valueRef.current = next
          onChange(next)
        })

        const fields = stateToFields(state)
        const next = applyFieldsToForm(valueRef.current, fields)
        valueRef.current = next
        onChange(next)

        const conflictMsg = conflictSummary(state)
        const newlyFilled: string[] = []
        if (valueRef.current.ice && !before.ice.trim()) newlyFilled.push('ICE')
        if (valueRef.current.rc && !before.rc.trim()) newlyFilled.push('RC')
        if (valueRef.current.raisonSociale && !before.raisonSociale.trim()) {
          newlyFilled.push('Raison sociale')
        }
        if (valueRef.current.identifiantFiscal && !before.identifiantFiscal.trim()) {
          newlyFilled.push('Identifiant fiscal')
        }

        if (conflictMsg) {
          setExtractHint(conflictMsg)
        } else if (newlyFilled.length > 0) {
          setExtractHint(
            `Champs préremplis : ${newlyFilled.join(', ')}. Vous pouvez les modifier.`,
          )
        } else if (fields.ice || fields.rc || fields.raisonSociale) {
          setExtractHint(
            'Informations fiables conservées — aucun remplacement par une valeur moins sûre.',
          )
        } else {
          setExtractHint(
            'Aucun ICE / RC / raison sociale détecté avec confiance suffisante — saisie manuelle possible.',
          )
        }
      }
    } catch (err) {
      logPipeline('queue error', {
        error: err instanceof Error ? err.message : String(err),
      })
      setExtractHint(
        err instanceof Error
          ? `Extraction impossible : ${err.message}`
          : 'Extraction impossible — saisie manuelle possible.',
      )
    } finally {
      runningRef.current = false
      setExtracting(false)
      setProgressLabel(null)
      if (queueRef.current.length > 0) {
        void drainQueue()
      }
    }
  }

  function handleDocuments(documents: UploadedFileMeta[]) {
    const prevIds = new Set(valueRef.current.documents.map((d) => d.id))
    const added = documents.filter((d) => !prevIds.has(d.id) && d.file)

    const next: EntrepriseFormData = { ...valueRef.current, documents }
    valueRef.current = next
    onChange(next)

    if (added.length === 0) return

    logPipeline('files queued', {
      count: added.length,
      names: added.map((a) => a.name).join(', '),
    })

    queueRef.current.push(...added)
    setExtractHint(null)
    void drainQueue()
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="m-0 text-[15px] font-bold text-slate-900">Entreprise (client)</h3>
        <p className="m-0 mt-1 text-[12.5px] leading-relaxed text-wb-muted">
          Identifiez le crédit-preneur. Déposez le bilan / la liasse fiscale :
          ICE, RC, IF et raison sociale sont lus sur l’en-tête et remplissent les champs.
        </p>
      </div>

      <FileDropzone
        files={value.documents}
        onChange={handleDocuments}
        error={errors.documents}
        label="Déposez le bilan / la liasse fiscale (PDF)"
      />

      {(extracting || extractHint) && (
        <div
          className={[
            'flex items-start gap-2 rounded-[12px] border px-3 py-2.5 text-[12px] leading-relaxed',
            extracting
              ? 'border-wb-accent-border bg-wb-accent-soft/50 text-slate-700'
              : 'border-wb-line bg-wb-surface text-wb-muted',
          ].join(' ')}
        >
          {extracting && (
            <Loader2 size={14} className="mt-0.5 flex-none animate-spin text-wb-accent" />
          )}
          <span>
            {extracting
              ? progressLabel ??
                'Extraction ICE, RC, IF et raison sociale depuis le bilan…'
              : extractHint}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Field label="ICE" required error={errors.ice} hint="15 chiffres">
          <NumericInput
            value={value.ice}
            error={!!errors.ice}
            placeholder="000000000000000"
            maxLength={15}
            onChange={(e) =>
              onChange({ ...value, ice: e.target.value.slice(0, 15) })
            }
          />
        </Field>

        <Field label="Registre de commerce (RC)" error={errors.rc}>
          <TextInput
            value={value.rc}
            error={!!errors.rc}
            placeholder="Ex. 123456"
            onChange={(e) => onChange({ ...value, rc: e.target.value })}
          />
        </Field>

        <Field label="Identifiant fiscal" hint="Lu sur le bilan">
          <NumericInput
            value={value.identifiantFiscal}
            placeholder="Ex. 52601461"
            maxLength={20}
            onChange={(e) =>
              onChange({ ...value, identifiantFiscal: e.target.value.slice(0, 20) })
            }
          />
        </Field>
      </div>

      <Field label="Raison sociale" required error={errors.raisonSociale}>
        <TextInput
          value={value.raisonSociale}
          error={!!errors.raisonSociale}
          placeholder="Ex. Transport Logistique Atlas SARL"
          onChange={(e) => onChange({ ...value, raisonSociale: e.target.value })}
        />
      </Field>

      <div className="flex flex-col gap-2.5">
        <Field
          label="Secteur d’activité"
          error={errors.secteur}
          hint="RC ou secteur : au moins l’un des deux"
        >
          <FancySelect
            value={value.secteurPreset}
            options={SECTEUR_OPTIONS}
            placeholder="Sélectionner un secteur"
            searchable
            searchPlaceholder="Rechercher un secteur…"
            emptyLabel="Aucun secteur trouvé"
            error={!!errors.secteur || !!errors.secteurAutre}
            onChange={(secteurPreset, meta) =>
              onChange({
                ...value,
                secteurPreset,
                secteurAutre:
                  secteurPreset === 'Autre'
                    ? value.secteurAutre.trim() || meta?.query.trim() || ''
                    : '',
              })
            }
          />
        </Field>

        <AnimatePresence initial={false}>
          {isAutre && (
            <motion.div
              initial={{ opacity: 0, height: 0, y: -6 }}
              animate={{ opacity: 1, height: 'auto', y: 0 }}
              exit={{ opacity: 0, height: 0, y: -6 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <Field
                label="Précisez le secteur"
                required
                error={errors.secteurAutre}
                hint="Ex. Logistique portuaire, Événementiel…"
              >
                <TextInput
                  autoFocus
                  value={value.secteurAutre}
                  error={!!errors.secteurAutre}
                  placeholder="Saisir le secteur d’activité"
                  onChange={(e) =>
                    onChange({ ...value, secteurAutre: e.target.value })
                  }
                />
              </Field>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
