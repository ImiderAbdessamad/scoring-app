import type { DossierStatus } from '@/types/dossier'


export function formatTodayFr(date: Date = new Date()): string {
  const raw = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}


export function formatDateShort(date: Date = new Date()): string {
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

export function formatMonthFr(date: Date = new Date()): string {
  return new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(date)
}


export function dateFromDaysAgo(daysAgo: number, base: Date = new Date()): string {
  const d = new Date(base)
  d.setHours(12, 0, 0, 0)
  d.setDate(d.getDate() - daysAgo)
  return formatDateShort(d)
}


export function relativeReceivedLabel(daysAgo: number, time = '09:00'): string {
  if (daysAgo <= 0) return `Auj. ${time}`
  if (daysAgo === 1) return `Hier ${time}`
  return dateFromDaysAgo(daysAgo)
}

export function formatAmountMad(amount: number): string {
  return formatMadCompact(amount)
}

export function formatMadExact(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—'
  return `${new Intl.NumberFormat('fr-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)} MAD`
}

export function formatMadCompact(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—'
  if (Math.abs(amount) >= 1_000_000) {
    const m = amount / 1_000_000
    const formatted = Number.isInteger(m) ? String(m) : m.toFixed(1).replace('.', ',')
    return `${formatted} M MAD`
  }
  return `${new Intl.NumberFormat('fr-MA').format(amount)} MAD`
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value.toFixed(digits).replace('.', ',')} %`
}

export function formatAmountShort(amount: number): string {
  if (amount >= 1_000_000) {
    const m = amount / 1_000_000
    return Number.isInteger(m) ? `${m} M` : `${m.toFixed(1).replace('.', ',')} M`
  }
  return `${Math.round(amount / 1000)} K`
}

export type ScoreTone = {
  color: string
  bg: string
}

export function scoreTone(_score?: number, classe?: string | null): ScoreTone {
  const g = classTone(classe)
  return { color: g.color, bg: g.bg }
}

export type GradeInfo = {
  letter: string
  label: string
  color: string
  bg: string
}

/** Mapping visuel à partir de la classe backend — aucun seuil métier ici. */
export function classTone(classe?: string | null): GradeInfo {
  const key = (classe || '').trim()
  if (key === 'A+') return { letter: 'A+', label: 'Excellent', color: '#15803D', bg: '#DCFCE7' }
  if (key === 'A/B+' || key === 'A') return { letter: key, label: 'Bon', color: '#15803D', bg: '#ECFDF5' }
  if (key === 'B/B-' || key === 'B') return { letter: key, label: 'Moyen', color: '#B45309', bg: '#FFF8EC' }
  if (key === 'C') return { letter: 'C', label: 'Sensible', color: '#C2410C', bg: '#FFF1E9' }
  if (key === 'D/F' || key === 'D' || key === 'F') return { letter: key, label: 'Risqué', color: '#DC2626', bg: '#FEF2F2' }
  return { letter: key || '—', label: 'Non classé', color: '#64748B', bg: '#F1F5F9' }
}

/** @deprecated Utiliser classTone(classe) fournie par le backend. */
export function gradeOf(score: number, classe?: string | null): GradeInfo {
  void score
  return classTone(classe)
}

export const STATUS_META: Record<
  DossierStatus,
  { label: string; color: string; bg: string }
> = {
  review: { label: 'Revue analyste', color: '#92400E', bg: '#FFFBEB' },
  analyzing: { label: 'En analyse', color: '#1D4ED8', bg: '#EFF6FF' },
  rejected: { label: 'Rejeté', color: '#DC2626', bg: '#FEF2F2' },
  ready: { label: 'Prêt pour analyse', color: '#B45309', bg: '#FFF8EC' },
  approved: { label: 'Approuvé', color: '#15803D', bg: '#DCFCE7' },
  reserved: { label: 'Sous réserve', color: '#B45309', bg: '#FFF8EC' },
  pending: { label: 'Docs en attente', color: '#64748B', bg: '#F1F5F9' },
  committee: { label: "Comité d'octroi", color: '#7C3AED', bg: '#F5F3FF' },
  contracting: { label: 'Contractualisation', color: '#0F766E', bg: '#F0FDFA' },
  active: { label: 'Contrat actif', color: '#15803D', bg: '#ECFDF5' },
  cancelled: { label: 'Annulé', color: '#64748B', bg: '#F8FAFC' },
}


export const LIST_FILTERS: Array<{ key: DossierStatus | 'all'; label: string }> = [
  { key: 'all', label: 'Tous' },
  { key: 'ready', label: 'Prêt à analyser' },
  { key: 'analyzing', label: 'En analyse' },
  { key: 'review', label: 'Revue analyste' },
  { key: 'approved', label: 'Approuvé' },
  { key: 'reserved', label: 'Sous réserve' },
  { key: 'rejected', label: 'Rejeté' },
  { key: 'pending', label: 'En attente' },
  { key: 'committee', label: 'Comité' },
]
