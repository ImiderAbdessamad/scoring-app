import { ChoiceCard, Field, NumericInput, TextInput } from '@/components/ui/FormField'
import { FileDropzone } from '@/components/ui/FileDropzone'
import type { StepErrors } from '@/features/dossiers/create/validation'
import type { FournisseurBienFormData } from '@/types/create-dossier'

type Props = {
  value: FournisseurBienFormData
  errors: StepErrors
  onChange: (next: FournisseurBienFormData) => void
}

export function StepFournisseur({ value, errors, onChange }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="m-0 text-[15px] font-bold text-slate-900">Fournisseur &amp; bien</h3>
        <p className="m-0 mt-1 text-[12.5px] leading-relaxed text-wb-muted">
          Informations proforma et caractéristiques du bien financé.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Field label="Fournisseur" required error={errors.fournisseur}>
          <TextInput
            value={value.fournisseur}
            error={!!errors.fournisseur}
            placeholder="Ex. Volvo Trucks Maroc"
            onChange={(e) => onChange({ ...value, fournisseur: e.target.value })}
          />
        </Field>
        <Field label="Référence proforma" required error={errors.proformaReference}>
          <TextInput
            value={value.proformaReference}
            error={!!errors.proformaReference}
            placeholder="Ex. PRO-2026-88421"
            onChange={(e) => onChange({ ...value, proformaReference: e.target.value })}
          />
        </Field>
      </div>

      <div>
        <div className="mb-1.5 text-[12px] font-semibold text-slate-700">
          Pièce proforma <span className="text-wb-accent">*</span>
        </div>
        <FileDropzone
          files={value.proformaFile ? [value.proformaFile] : []}
          multiple={false}
          maxFiles={1}
          error={errors.proformaFile}
          label="Joindre la proforma (PDF)"
          onChange={(files) =>
            onChange({ ...value, proformaFile: files[0] ?? null })
          }
        />
      </div>

      <Field label="Nature du bien" required error={errors.natureBien}>
        <TextInput
          value={value.natureBien}
          error={!!errors.natureBien}
          placeholder="Ex. Tracteur routier FH16"
          onChange={(e) => onChange({ ...value, natureBien: e.target.value })}
        />
      </Field>

      <div>
        <div className="mb-2 text-[12px] font-semibold text-slate-700">
          État <span className="text-wb-accent">*</span>
        </div>
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <ChoiceCard
            label="Neuf"
            selected={value.etat === 'neuf'}
            error={!!errors.etat}
            onSelect={() => onChange({ ...value, etat: 'neuf' })}
          />
          <ChoiceCard
            label="Occasion"
            selected={value.etat === 'occasion'}
            error={!!errors.etat}
            onSelect={() => onChange({ ...value, etat: 'occasion' })}
          />
        </div>
        {errors.etat && (
          <div className="mt-1.5 text-[11.5px] font-medium text-wb-danger">{errors.etat}</div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Field label="Valeur HT (MAD)" required error={errors.valeurHt}>
          <NumericInput
            value={value.valeurHt}
            error={!!errors.valeurHt}
            placeholder="Ex. 4500000"
            decimal
            onChange={(e) => onChange({ ...value, valeurHt: e.target.value })}
          />
        </Field>
        <Field label="Valeur TTC (MAD)" required error={errors.valeurTtc}>
          <NumericInput
            value={value.valeurTtc}
            error={!!errors.valeurTtc}
            placeholder="Ex. 5400000"
            decimal
            onChange={(e) => onChange({ ...value, valeurTtc: e.target.value })}
          />
        </Field>
      </div>
    </div>
  )
}
