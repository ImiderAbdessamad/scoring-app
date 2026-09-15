import type { Urgency } from '@/types/dossier'

export type FinancingNature = 'mobilier' | 'immobilier'
export type BienEtat = 'neuf' | 'occasion'


export interface UploadedFileMeta {
  id: string
  name: string
  size: number
  mimeType: string
  
  file?: File
}

export interface EntrepriseFormData {
  ice: string
  raisonSociale: string
  rc: string
  identifiantFiscal: string
  secteurPreset: string
  secteurAutre: string
  documents: UploadedFileMeta[]
}

export interface FinancementFormData {
  nature: FinancingNature | ''
  montantDemande: string
  valeurBien: string
  dureeMois: string
  apport: string
  urgence: Urgency | ''
}

export interface FournisseurBienFormData {
  fournisseur: string
  proformaReference: string
  proformaFile: UploadedFileMeta | null
  natureBien: string
  etat: BienEtat | ''
  valeurHt: string
  valeurTtc: string
}

export interface CreateDossierFormState {
  entreprise: EntrepriseFormData
  financement: FinancementFormData
  fournisseurBien: FournisseurBienFormData
}


export interface CreateDossierPayload {
  entreprise: {
    ice: string
    raisonSociale: string
    rc: string
    identifiantFiscal: string
    secteur: string
    secteurRaw: string
    documentNames: string[]
  }
  financement: {
    nature: FinancingNature
    montantDemande: number
    valeurBien: number
    dureeMois: number
    apport: number
    urgence: Urgency
  }
  fournisseurBien: {
    fournisseur: string
    proformaReference: string
    proformaFileName: string | null
    natureBien: string
    etat: BienEtat
    valeurHt: number
    valeurTtc: number
  }
}

export interface CreateDossierResponse {
  id: string
  status: string
  message: string
  job_id?: string | null
  stream_url?: string | null
  result_url?: string | null
  synthese_url?: string | null
  filename?: string | null
}

export const SECTEURS = [
  'Transport',
  'Immobilier',
  'BTP',
  'Santé',
  'Industrie',
  'Commerce',
  'Agriculture',
  'Tourisme',
  'Tech & Services',
  'Énergie',
  'Automobile',
  'Éducation',
  'Autre',
] as const
