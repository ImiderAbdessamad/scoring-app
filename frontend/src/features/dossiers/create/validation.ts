import type { CreateDossierFormState } from '@/types/create-dossier'
import { isAllowedUpload, uploadRejectMessage } from '@/lib/uploadTypes'

export const INITIAL_CREATE_FORM: CreateDossierFormState = {
  entreprise: {
    ice: '',
    raisonSociale: '',
    rc: '',
    identifiantFiscal: '',
    secteurPreset: '',
    secteurAutre: '',
    documents: [],
  },
  financement: {
    nature: '',
    montantDemande: '',
    valeurBien: '',
    dureeMois: '',
    apport: '',
    urgence: '',
  },
  fournisseurBien: {
    fournisseur: '',
    proformaReference: '',
    proformaFile: null,
    natureBien: '',
    etat: '',
    valeurHt: '',
    valeurTtc: '',
  },
}

export function parseAmount(raw: string): number {
  const cleaned = raw.replace(/\s/g, '').replace(',', '.')
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : NaN
}

export type StepErrors = Record<string, string>

export function resolveSecteur(
  data: CreateDossierFormState['entreprise'],
): string {
  if (data.secteurPreset === 'Autre') return 'Autre'
  return data.secteurPreset.trim()
}

export function dureeOptionsForNature(
  nature: CreateDossierFormState['financement']['nature'],
): { value: string; label: string }[] {
  if (nature === 'mobilier') {
    return [
      { value: '36', label: '36 mois' },
      { value: '48', label: '48 mois' },
      { value: '60', label: '60 mois' },
    ]
  }
  if (nature === 'immobilier') {
    return [{ value: '120', label: '120 mois' }]
  }
  return []
}

export function validateEntreprise(
  data: CreateDossierFormState['entreprise'],
): StepErrors {
  const e: StepErrors = {}
  const ice = data.ice.replace(/\s/g, '')
  if (!ice) e.ice = 'ICE obligatoire'
  else if (!/^\d{15}$/.test(ice)) e.ice = 'ICE invalide (15 chiffres)'

  if (!data.raisonSociale.trim()) e.raisonSociale = 'Raison sociale obligatoire'

  const secteur = resolveSecteur(data)

  if (data.secteurPreset === 'Autre' && !data.secteurAutre.trim()) {
    e.secteurAutre = 'Précisez le secteur'
  }

  if (!data.rc.trim() && !secteur) {
    e.rc = 'RC ou secteur requis'
    e.secteur = 'RC ou secteur requis'
  }

  if (data.documents.length === 0) {
    e.documents = 'Ajoutez le bilan / la liasse fiscale (PDF)'
  } else {
    const invalid = data.documents.find((d) => d.file && !isAllowedUpload(d.file))
    if (invalid?.file) {
      e.documents = uploadRejectMessage(invalid.file)
    }
  }
  return e
}

export function minMontantForNature(
  nature: CreateDossierFormState['financement']['nature'],
): number {
  if (nature === 'mobilier') return 50_000
  if (nature === 'immobilier') return 200_000
  return 0
}

export function validateFinancement(
  data: CreateDossierFormState['financement'],
): StepErrors {
  const e: StepErrors = {}
  if (!data.nature) e.nature = 'Choisissez la nature du financement'

  const minMontant = minMontantForNature(data.nature)
  const montant = parseAmount(data.montantDemande)
  if (!data.montantDemande.trim()) e.montantDemande = 'Montant demandé obligatoire'
  else if (!(montant > 0)) e.montantDemande = 'Montant invalide'
  else if (minMontant > 0 && montant < minMontant) {
    e.montantDemande = `Minimum ${minMontant.toLocaleString('fr-MA')} MAD (${data.nature})`
  }

  const valeur = parseAmount(data.valeurBien)
  if (!data.valeurBien.trim()) e.valeurBien = 'Valeur du bien obligatoire'
  else if (!(valeur > 0)) e.valeurBien = 'Valeur invalide'

  const allowed = dureeOptionsForNature(data.nature).map((o) => o.value)
  if (!data.nature) {
    e.dureeMois = 'Choisissez d’abord la nature du financement'
  } else if (!data.dureeMois.trim()) {
    e.dureeMois = 'Durée obligatoire'
  } else if (!allowed.includes(data.dureeMois)) {
    e.dureeMois =
      data.nature === 'immobilier'
        ? 'Durée immobilière : 120 mois'
        : 'Durée mobilier : 36, 48 ou 60 mois'
  }

  const apportPct = parseAmount(data.apport)
  if (!data.apport.trim()) e.apport = 'Apport initial obligatoire'
  else if (!(apportPct >= 0)) e.apport = 'Apport invalide'
  else if (apportPct > 100) {
    e.apport = 'Apport initial entre 0 % et 100 %'
  }

  if (!data.urgence) e.urgence = 'Urgence obligatoire'
  return e
}

export function validateFournisseur(
  data: CreateDossierFormState['fournisseurBien'],
): StepErrors {
  const e: StepErrors = {}
  if (!data.fournisseur.trim()) e.fournisseur = 'Fournisseur obligatoire'
  if (!data.proformaReference.trim()) {
    e.proformaReference = 'Référence proforma obligatoire'
  }
  if (!data.proformaFile) e.proformaFile = 'Joignez la pièce proforma'
  else if (data.proformaFile.file && !isAllowedUpload(data.proformaFile.file)) {
    e.proformaFile = uploadRejectMessage(data.proformaFile.file)
  }
  if (!data.natureBien.trim()) e.natureBien = 'Nature du bien obligatoire'
  if (!data.etat) e.etat = 'État du bien obligatoire'

  const ht = parseAmount(data.valeurHt)
  if (!data.valeurHt.trim()) e.valeurHt = 'Valeur HT obligatoire'
  else if (!(ht > 0)) e.valeurHt = 'Valeur HT invalide'

  const ttc = parseAmount(data.valeurTtc)
  if (!data.valeurTtc.trim()) e.valeurTtc = 'Valeur TTC obligatoire'
  else if (!(ttc > 0)) e.valeurTtc = 'Valeur TTC invalide'
  else if (Number.isFinite(ht) && ttc < ht) {
    e.valeurTtc = 'TTC doit être ≥ HT'
  }
  return e
}
