import { USE_MOCK } from '@/config/env'
import { ApiError, apiGet, apiPost, apiPostForm } from '@/services/api/client'
import { formatDateShort } from '@/lib/format'
import { isAllowedUpload, uploadRejectMessage } from '@/lib/uploadTypes'
import {
  getDossierStore,
  notifyDossierStore,
  prependDossier,
  updateDossierStatus,
} from '@/services/mocks/dossierStore'
import { MAX_DOSSIER_DOCUMENTS } from '@/lib/documentSlots'
import { parseAmount, resolveSecteur } from '@/features/dossiers/create/validation'
import type {
  CreateDossierFormState,
  CreateDossierPayload,
  CreateDossierResponse,
} from '@/types/create-dossier'
import type { Dossier, DossierDetail, DossierListResponse, DossierStatus } from '@/types/dossier'

export type DossierQuery = {
  status?: DossierStatus | 'all'
  q?: string
}

function delay(ms = 280) {
  return new Promise((r) => setTimeout(r, ms))
}

function makeReference(raisonSociale: string): string {
  const letters = raisonSociale
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z]/g, '')
    .toUpperCase()
    .slice(0, 3)
    .padEnd(3, 'X')
  const year = new Date().getFullYear()
  const seq = String(Math.floor(1000 + Math.random() * 9000))
  return `${letters}-${year}-${seq}`
}

export function toCreatePayload(form: CreateDossierFormState): CreateDossierPayload {
  return {
    entreprise: {
      ice: form.entreprise.ice.replace(/\s/g, ''),
      raisonSociale: form.entreprise.raisonSociale.trim(),
      rc: form.entreprise.rc.trim(),
      identifiantFiscal: form.entreprise.identifiantFiscal.trim(),
      secteur: resolveSecteur(form.entreprise),
      secteurRaw: resolveSecteur(form.entreprise),
      documentNames: form.entreprise.documents.map((d) => d.name),
    },
    financement: {
      nature: form.financement.nature as CreateDossierPayload['financement']['nature'],
      montantDemande: parseAmount(form.financement.montantDemande),
      valeurBien: parseAmount(form.financement.valeurBien),
      dureeMois: Number(form.financement.dureeMois),
      apport: parseAmount(form.financement.apport),
      urgence: form.financement.urgence as CreateDossierPayload['financement']['urgence'],
    },
    fournisseurBien: {
      fournisseur: form.fournisseurBien.fournisseur.trim(),
      proformaReference: form.fournisseurBien.proformaReference.trim(),
      proformaFileName: form.fournisseurBien.proformaFile?.name ?? null,
      natureBien: form.fournisseurBien.natureBien.trim(),
      etat: form.fournisseurBien.etat as CreateDossierPayload['fournisseurBien']['etat'],
      valeurHt: parseAmount(form.fournisseurBien.valeurHt),
      valeurTtc: parseAmount(form.fournisseurBien.valeurTtc),
    },
  }
}

function buildCreateFormData(form: CreateDossierFormState): FormData {
  const payload = toCreatePayload(form)
  const body = new FormData()
  body.append('data', JSON.stringify(payload))

  for (const doc of form.entreprise.documents) {
    if (!doc.file) {
      throw new Error(`Fichier manquant : ${doc.name}`)
    }
    if (!isAllowedUpload(doc.file)) {
      throw new Error(uploadRejectMessage(doc.file))
    }
    body.append('documents', doc.file, doc.name)
  }

  const proforma = form.fournisseurBien.proformaFile
  if (!proforma?.file) {
    throw new Error('Pièce proforma manquante')
  }
  if (!isAllowedUpload(proforma.file)) {
    throw new Error(uploadRejectMessage(proforma.file))
  }
  body.append('proforma', proforma.file, proforma.name)

  return body
}

export async function createDossier(
  form: CreateDossierFormState,
): Promise<CreateDossierResponse> {
  const payload = toCreatePayload(form)

  if (USE_MOCK) {
    await delay(520)
    const id = makeReference(payload.entreprise.raisonSociale)
    const dossier: Dossier = {
      id,
      name: payload.entreprise.raisonSociale,
      sector: payload.entreprise.secteur || 'Autre',
      amount: payload.financement.montantDemande,
      duration: payload.financement.dureeMois,
      score: 0,
      status: 'pending',
      analyst: 'K. Benali',
      receivedDaysAgo: 0,
      date: formatDateShort(),
      urgency: payload.financement.urgence,
      receivedTime: new Date().toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }
    prependDossier(dossier)
    const mockFiles = [
      ...form.entreprise.documents.map((doc) => ({
        name: doc.name,
        objectKey: `${id}/entreprise/${doc.name}`,
        size: doc.size,
        contentType: doc.mimeType || 'application/pdf',
        category: 'entreprise' as const,
      })),
      ...(form.fournisseurBien.proformaFile
        ? [
            {
              name: form.fournisseurBien.proformaFile.name,
              objectKey: `${id}/proforma/${form.fournisseurBien.proformaFile.name}`,
              size: form.fournisseurBien.proformaFile.size,
              contentType: form.fournisseurBien.proformaFile.mimeType || 'application/pdf',
              category: 'proforma' as const,
            },
          ]
        : []),
    ]
    setMockDetailFiles(id, mockFiles)
    return {
      id,
      status: 'pending',
      message: `Dossier ${id} créé — documents en attente`,
    }
  }

  const res = await apiPostForm<CreateDossierResponse>(
    '/dossiers',
    buildCreateFormData(form),
  )
  notifyDossierStore()
  return res
}

export async function fetchDossiers(
  query: DossierQuery = {},
): Promise<DossierListResponse> {
  if (USE_MOCK) {
    await delay()
    const q = (query.q ?? '').trim().toLowerCase()
    const status = query.status ?? 'all'
    const all = getDossierStore()

    const items = all.filter((d) => {
      const statusOk = status === 'all' || d.status === status
      const textOk =
        !q ||
        d.id.toLowerCase().includes(q) ||
        d.name.toLowerCase().includes(q) ||
        d.sector.toLowerCase().includes(q) ||
        d.analyst.toLowerCase().includes(q)
      return statusOk && textOk
    })

    return { items, total: items.length }
  }

  const params = new URLSearchParams()
  if (query.status && query.status !== 'all') params.set('status', query.status)
  if (query.q) params.set('q', query.q)
  const qs = params.toString()
  return apiGet<DossierListResponse>(`/dossiers${qs ? `?${qs}` : ''}`)
}

export async function fetchDossierById(id: string): Promise<Dossier | null> {
  if (USE_MOCK) {
    await delay(120)
    return getDossierStore().find((d) => d.id === id) ?? null
  }
  return apiGet<Dossier>(`/dossiers/${encodeURIComponent(id)}`)
}

export async function fetchDossierDetail(id: string): Promise<DossierDetail | null> {
  if (USE_MOCK) {
    await delay(120)
    const dossier = getDossierStore().find((d) => d.id === id)
    if (!dossier) return null
    return buildMockDossierDetail(dossier)
  }
  try {
    return await apiGet<DossierDetail>(`/dossiers/${encodeURIComponent(id)}/detail`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

function buildMockDossierDetail(dossier: Dossier): DossierDetail {
  const apport = Math.round(dossier.amount * 0.2)
  const valeurBien = Math.round(dossier.amount / 0.8)
  const storedFiles = getMockDetailFiles(dossier.id)
  return {
    ...dossier,
    ice: '000000000000000',
    rc: '',
    nature: 'mobilier',
    valeurBien: storedFiles.length > 0 ? valeurBien : dossier.amount,
    apport: storedFiles.length > 0 ? apport : Math.round(dossier.amount * 0.2),
    fournisseur: 'Fournisseur agréé Wafabail',
    proformaReference: 'PRO-2026-001',
    natureBien: 'Équipement professionnel',
    etat: 'neuf',
    valeurHt: Math.round(valeurBien / 1.2),
    valeurTtc: valeurBien,
    files: storedFiles,
  }
}

const mockDetailFiles = new Map<string, DossierDetail['files']>()

export function getMockDetailFiles(dossierId: string): DossierDetail['files'] {
  if (!mockDetailFiles.has(dossierId)) {
    mockDetailFiles.set(dossierId, [])
  }
  return mockDetailFiles.get(dossierId)!
}

export function setMockDetailFiles(dossierId: string, files: DossierDetail['files']): void {
  mockDetailFiles.set(dossierId, files)
}

export async function replaceDossierDocument(
  dossierId: string,
  slotName: string,
  file: File,
): Promise<DossierDetail> {
  if (!isAllowedUpload(file)) {
    throw new Error(uploadRejectMessage(file))
  }

  if (USE_MOCK) {
    await delay(320)
    const dossier = getDossierStore().find((d) => d.id === dossierId)
    if (!dossier) {
      throw new Error('Dossier introuvable')
    }

    const files = [...getMockDetailFiles(dossierId)]
    if (files.length >= MAX_DOSSIER_DOCUMENTS && !files.some((f) => f.name === slotName)) {
      throw new Error(`Maximum ${MAX_DOSSIER_DOCUMENTS} documents autorisés`)
    }

    const category =
      slotName.toLowerCase().includes('proforma') || slotName.toLowerCase().includes('facture')
        ? 'proforma'
        : 'entreprise'
    const meta = {
      name: slotName,
      objectKey: `${dossierId}/${category}/${slotName}`,
      size: file.size,
      contentType: file.type || 'application/octet-stream',
      category,
    }
    const idx = files.findIndex((f) => f.name === slotName)
    if (idx >= 0) files[idx] = meta
    else files.push(meta)
    setMockDetailFiles(dossierId, files)
    return buildMockDossierDetail(dossier)
  }

  const body = new FormData()
  body.append('name', slotName)
  body.append('file', file, file.name)
  return apiPostForm<DossierDetail>(
    `/dossiers/${encodeURIComponent(dossierId)}/documents/replace`,
    body,
  )
}

async function persistDecision(
  id: string,
  mockStatus: DossierStatus,
  path: string,
  body: { reason?: string; comment?: string } = {},
): Promise<Dossier> {
  if (USE_MOCK) {
    await delay(180)
    const updated = updateDossierStatus(id, mockStatus)
    if (!updated) throw new Error('Dossier introuvable')
    return updated
  }
  const res = await apiPost<Dossier>(path, body)
  notifyDossierStore()
  return res
}

export function approveDossier(id: string, body?: { reason?: string; comment?: string }): Promise<Dossier> {
  return persistDecision(id, 'approved', `/dossiers/${encodeURIComponent(id)}/approve`, body)
}

export function rejectDossier(id: string, body?: { reason?: string; comment?: string }): Promise<Dossier> {
  return persistDecision(id, 'rejected', `/dossiers/${encodeURIComponent(id)}/reject`, body)
}

export function reserveDossier(id: string, body?: { reason?: string; comment?: string }): Promise<Dossier> {
  return persistDecision(id, 'reserved', `/dossiers/${encodeURIComponent(id)}/reserve`, body)
}

export async function fetchDecisionEligibility(id: string) {
  return apiGet(`/dossiers/${encodeURIComponent(id)}/decision-eligibility`)
}

export async function fetchMemos(id: string) {
  return apiGet<Array<{ id: string; status: string; signedAt?: string | null }>>(`/dossiers/${encodeURIComponent(id)}/memos`)
}

export async function createMemo(id: string, content: Record<string, unknown> = {}) {
  return apiPost<{ id: string; status: string }>(`/dossiers/${encodeURIComponent(id)}/memos`, { content })
}

export async function signMemo(id: string, memoId: string) {
  return apiPost(`/dossiers/${encodeURIComponent(id)}/memos/${encodeURIComponent(memoId)}/sign`, {
    signed_by: 'Analyste',
    signed_role: 'analyste',
  })
}

export function cancelDossierDecision(id: string): Promise<Dossier> {
  return persistDecision(id, 'pending', `/dossiers/${encodeURIComponent(id)}/cancel`)
}

export async function extractBilanIdentity(file: File): Promise<{
  ice: string | null
  rc: string | null
  raison_sociale: string | null
  identifiant_fiscal: string | null
  taxe_professionnelle: string | null
  activite: string | null
  adresse: string | null
  ville: string | null
  period_start: string | null
  period_end: string | null
}> {
  if (USE_MOCK) {
    return {
      ice: null,
      rc: null,
      raison_sociale: null,
      identifiant_fiscal: null,
      taxe_professionnelle: null,
      activite: null,
      adresse: null,
      ville: null,
      period_start: null,
      period_end: null,
    }
  }
  const body = new FormData()
  body.append('file', file, file.name)
  return apiPostForm('/extract/identity', body)
}
