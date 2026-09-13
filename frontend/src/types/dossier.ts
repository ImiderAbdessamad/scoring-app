
export type DossierStatus =
  | 'pending'
  | 'ready'
  | 'analyzing'
  | 'review'
  | 'committee'
  | 'approved'
  | 'reserved'
  | 'rejected'
  | 'contracting'
  | 'active'
  | 'cancelled'

export type Urgency = 'haute' | 'normale' | 'basse'

export interface Dossier {
  id: string
  name: string
  sector: string
  amount: number
  duration: number
  score: number
  status: DossierStatus
  analyst: string
  receivedDaysAgo: number
  date?: string
  decisionDate?: string
  urgency?: Urgency
  classe?: string | null
  riskLevel?: string | null
  receivedTime?: string
  analyseStatus?: string | null
  analyseProgressPct?: number | null
  source?: string | null
  noDemande?: string | null
  noPv?: string | null
}

export interface QueueItem {
  id: string
  name: string
  sector: string
  amountShort: string
  score: number
  urgency: Urgency
  received: string
}

export type RiskBucket = {
  label: string
  count: number
  pct: number
  tone: 'low' | 'mid' | 'high' | 'critical' | 'unknown'
}

export interface SectorStat {
  label: string
  count: number
}

export interface AlertItem {
  id: string
  type: string
  message: string
  time: string
  tone: 'danger' | 'warn' | 'info' | 'success'
  read: boolean
}

export interface DashboardKpis {
  inProgress: number
  inProgressDelta: string
  toAnalyze: number
  toAnalyzeHint: string
  approved: number
  approvedDelta: string
  approvedMonth: string
  rejected: number
  rejectedDelta: string
  rejectedMonth: string
  committedValue: string
  committedHint: string
  reviewRequired?: number
  failedAnalyses?: number
  qualityInsufficient?: number
}

export interface AnalystActivity {
  today: number
  week: number
  approvalRate: string
  avgDelay: string
}

export interface DashboardData {
  greeting: string
  dateLabel: string
  analystName: string
  kpis: DashboardKpis
  queue: QueueItem[]
  queueTotal: number
  riskDist: RiskBucket[]
  riskActiveTotal: number
  sectors: SectorStat[]
  alerts: AlertItem[]
  unreadAlertCount?: number
  activity: AnalystActivity
}

export interface DossierListResponse {
  items: Dossier[]
  total: number
}

export interface StoredFileMeta {
  name: string
  objectKey: string
  size: number
  contentType: string
  category: string
}

export interface DossierDetail extends Dossier {
  ice: string
  rc: string
  nature: string
  valeurBien: number
  apport: number
  fournisseur: string
  proformaReference: string
  natureBien: string
  etat: string
  valeurHt: number
  valeurTtc: number
  files: StoredFileMeta[]
  receivedLabel?: string | null
}
