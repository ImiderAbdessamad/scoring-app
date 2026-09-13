import { ChoiceCard, Field, NumericInput } from '@/components/ui/FormField'
import { FancySelect } from '@/components/ui/FancySelect'
import {
  dureeOptionsForNature,
  minMontantForNature,
  parseAmount,
  type StepErrors,
} from '@/features/dossiers/create/validation'
import type { FinancementFormData } from '@/types/create-dossier'

type Props = {
  value: FinancementFormData
  errors: StepErrors
  onChange: (next: FinancementFormData) => void
}

export function StepFinancement({ value, errors, onChange }: Props) {
  const valeur = parseAmount(value.valeurBien)
  const apportPct = parseAmount(value.apport)
  const apportMad =
    Number.isFinite(valeur) && valeur > 0 && Number.isFinite(apportPct)
      ? Math.round((valeur * apportPct) / 100)
      : null
  const minMontant = minMontantForNature(value.nature)
  const montantHint =
    minMontant > 0
      ? `Minimum ${minMontant.toLocaleString('fr-MA')} MAD`
      : undefined
  const dureeOptions = dureeOptionsForNature(value.nature)
  const dureeHint =
    value.nature === 'mobilier'
      ? '36, 48 ou 60 mois'
      : value.nature === 'immobilier'
        ? '120 mois (immobilier)'
        : 'Choisissez d’abord la nature'

  function setNature(nature: FinancementFormData['nature']) {
    const options = dureeOptionsForNature(nature)
    const keep =
      options.some((o) => o.value === value.dureeMois) ? value.dureeMois : options[0]?.value ?? ''
    onChange({ ...value, nature, dureeMois: keep })
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="m-0 text-[15px] font-bold text-slate-900">Financement</h3>
        <p className="m-0 mt-1 text-[12.5px] leading-relaxed text-wb-muted">
          Conditions de la demande de crédit-bail (CDC §7.1).
        </p>
      </div>

      <div>
        <div className="mb-2 text-[12px] font-semibold text-slate-700">
          Nature du financement <span className="text-wb-accent">*</span>
        </div>
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <ChoiceCard
            label="Mobilier"
            description="Équipements, véhicules, matériel · min. 50 000 MAD"
            selected={value.nature === 'mobilier'}
            error={!!errors.nature}
            onSelect={() => setNature('mobilier')}
          />
          <ChoiceCard
            label="Immobilier"
            description="Locaux, entrepôts, bureaux · min. 200 000 MAD"
            selected={value.nature === 'immobilier'}
            error={!!errors.nature}
            onSelect={() => setNature('immobilier')}
          />
        </div>
        {errors.nature && (
          <div className="mt-1.5 text-[11.5px] font-medium text-wb-danger">{errors.nature}</div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Field
          label="Montant demandé (MAD)"
          required
          error={errors.montantDemande}
          hint={montantHint}
        >
          <NumericInput
            value={value.montantDemande}
            error={!!errors.montantDemande}
            placeholder={
              minMontant > 0
                ? `Ex. ${minMontant.toLocaleString('fr-MA')}`
                : 'Ex. 4800000'
            }
            decimal
            onChange={(e) => onChange({ ...value, montantDemande: e.target.value })}
          />
        </Field>
        <Field label="Valeur du bien (MAD)" required error={errors.valeurBien}>
          <NumericInput
            value={value.valeurBien}
            error={!!errors.valeurBien}
            placeholder="Ex. 5200000"
            decimal
            onChange={(e) => onChange({ ...value, valeurBien: e.target.value })}
          />
        </Field>
        <Field label="Durée (mois)" required error={errors.dureeMois} hint={dureeHint}>
          <FancySelect
            value={value.dureeMois}
            options={dureeOptions}
            placeholder={
              value.nature ? 'Sélectionner la durée' : 'Choisir d’abord mobilier / immobilier'
            }
            error={!!errors.dureeMois}
            disabled={!value.nature || dureeOptions.length === 0}
            onChange={(dureeMois) => onChange({ ...value, dureeMois })}
          />
        </Field>
        <Field
          label="Apport initial (%)"
          required
          error={errors.apport}
          hint={
            apportMad != null
              ? `Soit ${apportMad.toLocaleString('fr-MA')} MAD (0–100 %)`
              : 'Saisir un pourcentage entre 0 et 30'
          }
        >
          <NumericInput
            value={value.apport}
            error={!!errors.apport}
            placeholder="Ex. 20"
            decimal
            onChange={(e) => onChange({ ...value, apport: e.target.value })}
          />
        </Field>
      </div>

      <div>
        <div className="mb-2 text-[12px] font-semibold text-slate-700">
          Urgence <span className="text-wb-accent">*</span>
        </div>
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <ChoiceCard
            label="Haute"
            description="Priorité file d’attente"
            selected={value.urgence === 'haute'}
            error={!!errors.urgence}
            onSelect={() => onChange({ ...value, urgence: 'haute' })}
          />
          <ChoiceCard
            label="Normale"
            description="Traitement standard"
            selected={value.urgence === 'normale'}
            error={!!errors.urgence}
            onSelect={() => onChange({ ...value, urgence: 'normale' })}
          />
        </div>
        {errors.urgence && (
          <div className="mt-1.5 text-[11.5px] font-medium text-wb-danger">{errors.urgence}</div>
        )}
      </div>
    </div>
  )
}
