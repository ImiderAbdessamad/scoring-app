import { dashboardSectorLabel } from '@/lib/sector'
import { formatAmountMad, formatDateShort, formatMonthFr } from '@/lib/format'
import type { Dossier, DashboardKpis, RiskBucket, SectorStat } from '@/types/dossier'

const OPEN_STATUSES = new Set([
  'pending',
  'ready',
  'analyzing',
  'review',
  'committee',
  'contracting',
])
const TO_ANALYZE_STATUSES = new Set(['pending', 'ready'])
const SECTOR_ORDER = ['Transport', 'BTP', 'Commerce', 'Santé', 'Industrie', 'Autres'] as const

function parseFrDate(value?: string): Date | null {
  if (!value) return null
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value)
  if (!match) return null
  return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]), 12, 0, 0)
}

function sameMonth(a: Date, year: number, month: number): boolean {
  return a.getFullYear() === year && a.getMonth() === month
}

function decisionDateOf(d: Dossier): Date | null {
  const fromDecision = parseFrDate(d.decisionDate)
  if (fromDecision) return fromDecision
  const fromCreated = parseFrDate(d.date)
  if (fromCreated) return fromCreated
  const fallback = new Date()
  fallback.setHours(12, 0, 0, 0)
  fallback.setDate(fallback.getDate() - d.receivedDaysAgo)
  return fallback
}

function createdYesterdayHint(count: number): string {
  if (count <= 0) return 'Aucun nouveau hier'
  if (count === 1) return '+1 nouveau hier'
  return `+${count} nouveaux hier`
}

function monthDeltaHint(current: number, previous: number): string {
  const diff = current - previous
  if (diff > 0) return `+${diff} vs mois précédent`
  if (diff < 0) return `−${Math.abs(diff)} vs mois précédent`
  return 'Stable vs mois précédent'
}

export function computeDashboardKpis(records: Dossier[], now = new Date()): DashboardKpis {
  const year = now.getFullYear()
  const month = now.getMonth()
  const prev = new Date(year, month - 1, 1)
  const yesterday = new Date(now)
  yesterday.setHours(12, 0, 0, 0)
  yesterday.setDate(yesterday.getDate() - 1)
  const yesterdayKey = formatDateShort(yesterday)
  const monthLabel = formatMonthFr(now)

  let inProgress = 0
  let toAnalyze = 0
  let approvedThis = 0
  let approvedPrev = 0
  let rejectedThis = 0
  let rejectedPrev = 0
  let createdYesterday = 0
  let reviewRequired = 0
  let committed = 0

  for (const d of records) {
    if (OPEN_STATUSES.has(d.status)) inProgress += 1
    if (TO_ANALYZE_STATUSES.has(d.status)) toAnalyze += 1
    if (d.status === 'review') reviewRequired += 1

    const createdKey =
      d.date ||
      formatDateShort(
        new Date(now.getFullYear(), now.getMonth(), now.getDate() - d.receivedDaysAgo, 12),
      )
    if (createdKey === yesterdayKey) createdYesterday += 1

    const decided = decisionDateOf(d)
    if (d.status === 'approved') {
      committed += d.amount
      if (decided && sameMonth(decided, year, month)) approvedThis += 1
      else if (decided && sameMonth(decided, prev.getFullYear(), prev.getMonth())) approvedPrev += 1
    } else if (d.status === 'rejected') {
      if (decided && sameMonth(decided, year, month)) rejectedThis += 1
      else if (decided && sameMonth(decided, prev.getFullYear(), prev.getMonth())) rejectedPrev += 1
    } else if (d.status === 'active') {
      committed += d.amount
    }
  }

  return {
    inProgress,
    inProgressDelta: createdYesterdayHint(createdYesterday),
    toAnalyze,
    toAnalyzeHint: toAnalyze ? 'Priorité · en file' : 'Aucun dossier en file',
    approved: approvedThis,
    approvedDelta: monthDeltaHint(approvedThis, approvedPrev),
    approvedMonth: monthLabel,
    rejected: rejectedThis,
    rejectedDelta: monthDeltaHint(rejectedThis, rejectedPrev),
    rejectedMonth: monthLabel,
    committedValue: formatAmountMad(committed),
    committedHint: 'Portefeuille actif',
    reviewRequired,
  }
}

function riskToneFromDossier(d: Dossier): 'low' | 'mid' | 'high' | 'critical' | 'unknown' {
  const level = (d.riskLevel || '').toLowerCase()
  const mapped: Record<string, 'low' | 'mid' | 'high' | 'critical'> = {
    faible: 'low',
    modere: 'mid',
    'modéré': 'mid',
    eleve: 'high',
    'élevé': 'high',
    critique: 'critical',
  }
  if (level && mapped[level]) return mapped[level]
  const classe = (d.classe || '').trim()
  if (classe === 'A+' || classe === 'A/B+' || classe === 'A') return 'low'
  if (classe === 'B/B-' || classe === 'B') return 'mid'
  if (classe === 'C') return 'high'
  if (classe === 'D/F' || classe === 'D' || classe === 'F') return 'critical'
  return 'unknown'
}

export function computeRiskDistribution(records: Dossier[]): {
  riskDist: RiskBucket[]
  riskActiveTotal: number
  sectors: SectorStat[]
} {
  const counts: Record<'low' | 'mid' | 'high' | 'critical' | 'unknown', number> = {
    low: 0,
    mid: 0,
    high: 0,
    critical: 0,
    unknown: 0,
  }
  const total = records.length
  for (const d of records) counts[riskToneFromDossier(d)] += 1

  const riskDist: RiskBucket[] = [
    { label: 'Faible', tone: 'low', count: counts.low, pct: total ? Math.round((100 * counts.low) / total) : 0 },
    { label: 'Modéré', tone: 'mid', count: counts.mid, pct: total ? Math.round((100 * counts.mid) / total) : 0 },
    { label: 'Élevé', tone: 'high', count: counts.high, pct: total ? Math.round((100 * counts.high) / total) : 0 },
    { label: 'Critique', tone: 'critical', count: counts.critical, pct: total ? Math.round((100 * counts.critical) / total) : 0 },
  ]

  const sectorCounts = new Map<string, number>()
  for (const d of records) {
    const label = dashboardSectorLabel(d.sector)
    sectorCounts.set(label, (sectorCounts.get(label) ?? 0) + 1)
  }

  const sectors: SectorStat[] = []
  const seen = new Set<string>()
  for (const label of SECTOR_ORDER) {
    const count = sectorCounts.get(label) ?? 0
    if (!count) continue
    sectors.push({ label, count })
    seen.add(label)
  }
  const extras = [...sectorCounts.entries()]
    .filter(([label, count]) => !seen.has(label) && count > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'fr'))
  for (const [label, count] of extras) sectors.push({ label, count })

  return { riskDist, riskActiveTotal: total, sectors }
}
