import type { DossierStatus } from '@/types/dossier'


export type AnalyseTabId =
  | 'synthese'
  | 'etats'
  | 'bien'
  | 'ratios'
  | 'factorielle'
  | 'fiscal'
  | 'capital'
  | 'qualite'
  | 'comportement'
  | 'benchmark'
  | 'memo'

export type DecisionKind = 'approve' | 'reserve' | 'reject'

export type RatioStatus = 'GOOD' | 'WARN' | 'BAD'
export type TraceLineType = 'in' | 'ok' | 'warn' | 'res'
export type SignalTone = 'ok' | 'warn'

export interface AnalyseHeader {
  id: string
  shortCode: string
  companyName: string
  subtitle: string
  status: DossierStatus
  statusLabel: string
  analyst: string
  amountFinanced: number
  assetValue: number
  durationMonths: number
  apportPct: number
  location: string
  source?: string | null
  noDemande?: string | null
  noPv?: string | null
  tiers?: string | null
  clientLookupStatus?: 'MATCHED' | 'MULTIPLE' | 'NOT_FOUND' | 'SKIPPED' | 'ERROR' | null
}

export interface IaClientMatch {
  ice?: string | null
  tiers?: string | null
  rc?: string | null
  identifiant_fiscal?: string | null
  raison_sociale?: string | null
}

export interface ClientLookup {
  status: 'MATCHED' | 'MULTIPLE' | 'NOT_FOUND' | 'SKIPPED' | 'ERROR'
  query: Record<string, string>
  matches: IaClientMatch[]
  primary?: IaClientMatch | null
  message?: string | null
}

export interface PipelineStepMeta {
  label: string
  meta: string
}

export interface PipelineTraceLine {
  type: TraceLineType
  text: string
  step: number
}

export interface PipelineData {
  policyVersion: string
  steps: PipelineStepMeta[]
  
  fullTrace: PipelineTraceLine[]
  initialStep: number
  initialScore: number
}

export interface DocumentItem {
  id: string
  name: string
  meta: string
  confidence: number | null
  uploadName?: string
}

export interface MissingDocument {
  id: string
  name: string
  meta: string
}

export interface ExtractedField {
  label: string
  value: string
  source: string
  confidence: number | null
}

export interface DocumentExtraction {
  title: string
  flag: string
  fields: ExtractedField[]
}

export interface DocumentsBlock {
  present: number
  total: number
  completenessPct: number
  items: DocumentItem[]
  missing: MissingDocument[]
  required?: Array<{ id: string; name: string; ok?: boolean }>
  extractions: Record<string, DocumentExtraction>
  defaultDocId: string
}

export interface ScoreFactor {
  label: string
  impact: number
}

export interface ScoringAttention {
  pointsForts: string[]
  pointsVigilance: string[]
  scoreFinal: string
}

export interface TrendYear {
  year: string
  caLabel: string
  rnLabel?: string
  caHeightPct: number
  rnHeightPct: number
}

export interface ScoringBlock {
  score: number
  scoreRaw?: number | null
  scoreStatus?: ScoreStatus
  financialScore?: number | null
  behavioralScore?: number | null
  sectorScore?: number | null
  partialScore?: number | null
  finalScore?: number | null
  classe?: string
  recommendation: string
  riskLabel: string
  riskLevel?: string
  provisional?: boolean
  stale?: boolean
  summary: string
  modelConfidencePct?: number
  ratiosOk: number
  ratiosTotal: number
  dossierCompletenessPct: number
  factors: ScoreFactor[]
  trend: TrendYear[]
  trendCaption: string
  attention: ScoringAttention
}

export type ScoreStatus = 'NOT_CALCULABLE' | 'PARTIAL' | 'FINAL'

export interface DecisionEligibility {
  financial_analysis_ready: boolean
  behavioral_analysis_ready: boolean
  sector_analysis_ready: boolean
  bam_checked: boolean
  bam_clear: boolean | null
  incidents_checked: boolean
  incidents_clear: boolean | null
  mandatory_documents_ready: boolean
  quality_gate_passed: boolean
  analysis_stale: boolean
  score_status: ScoreStatus
  eligible_for_automatic_recommendation: boolean
  eligible_for_approval: boolean
  eligible_for_reserve: boolean
  eligible_for_rejection: boolean
  blocking_reasons: string[]
  warnings: string[]
}

export interface RatioItem {
  label: string
  formula: string
  threshold?: string
  value: string
  status: RatioStatus
  barPct: number
  interpretation: string
}

export interface FiscalKpi {
  label: string
  value: string
  tone: 'neutral' | 'warn' | 'ok'
}

export interface RatiosBlock {
  calcTime: string
  conformCount: number
  watchCount: number
  items: RatioItem[]
  fiscal: FiscalKpi[]
  aggregates?: FiscalKpi[]
}

export interface BienUnit {
  qty: string
  designation: string
  marque: string
  modele: string
  annee: string
  valeur: string
}

export interface BienBlock {
  title: string
  subtitle: string
  assetValueLabel: string
  financedLabel: string
  durationLabel: string
  residualLabel: string | null
  estimateNote?: string
  units: BienUnit[]
  totalTtcLabel: string
  specs: Array<{ key: string; value: string }>
  schedule: Array<{ label: string; count: string; amount: string; highlight?: boolean }>
  totalCostLabel: string
  creditCostLabel: string
  guarantees: Array<{ ok: boolean; title: string; detail: string }>
}

export interface FactorAxisRow {
  label: string
  y1: string
  y2: string
  y3: string
  variation: string
  variationTone: 'up' | 'flat' | 'down'
}

export interface FactorAxisRatio {
  label: string
  value: string
  status: RatioStatus
  formula?: string
  threshold?: string
}

export interface FactorAxis {
  num: string
  title: string
  unit: string
  yearLabels?: [string, string, string] | string[]
  rows: FactorAxisRow[]
  ratios: FactorAxisRatio[]
}

export interface BehaviourMetric {
  label: string
  value: string
  tone: 'neutral' | 'ok' | 'warn'
  sub: string
}

export interface BehaviourMonth {
  label: string
  valueK: number
}

export interface BehaviourSignal {
  tone: SignalTone
  title: string
  detail: string
}

export interface BehaviourBlock {
  score: number | null
  status?: string
  available?: boolean
  profileLabel: string
  summary: string
  metrics: BehaviourMetric[]
  months: BehaviourMonth[]
  signals: BehaviourSignal[]
}

export interface BenchmarkRow {
  label: string
  client: string
  median: string
  clientPct: number
  medianPct: number
  tone: 'ok' | 'bad'
  percentile: string
}

export interface ComparableCase {
  id: string
  name: string
  score: number
  decision: string
  decisionTone: 'ok' | 'warn'
  date: string
}

export interface BenchmarkBlock {
  sectorLabel: string
  sampleSize: number | null
  status?: string
  caption: string
  rows: BenchmarkRow[]
  aboveMedianLabel: string
  comparables: ComparableCase[]
  meta?: {
    year?: number
    source?: string
    sample_size?: number
    version?: string
    sector_code?: string
  }
}

export interface MemoSection {
  title: string
  paragraphs?: string[]
  table?: { headers: string[]; rows: string[][] }
  tableNote?: string
  chips?: Array<{ ok: boolean; label: string; value: string }>
  risks?: Array<{ tone: 'warn' | 'info'; text: string }>
  conditions?: string[]
  conclusionBanner?: string
}

export interface MemoBlock {
  title: string
  subtitle: string
  refLine: string
  recommendation: string
  scoreLine: string
  clientGrid: Array<{ label: string; value: string }>
  sections: MemoSection[]
  signerName: string
  signerRole: string
  signedAt: string
}

export interface CopilotQa {
  pourquoi: string
  risque: string
  complet: string
  secteur: string
  fallback: string
}

export interface CopilotBlock {
  welcomeMessage: string
  chips: Array<{ label: string; intent: keyof Omit<CopilotQa, 'fallback'> }>
  qa: CopilotQa
}


export type FieldQualityStatus =
  | 'confirmed'
  | 'cross_checked'
  | 'validated_by_equation'
  | 'validated_by_repeated_source'
  | 'ambiguous'
  | 'suspect'
  | 'conflicting'
  | 'missing'
  | 'blank_on_form'
  | 'derived'

export type AnalysisStatus = 'pending' | 'queued' | 'processing' | 'completed' | 'failed'
export type QualityStatus = 'valid' | 'warning' | 'review_required' | 'blocked'
export type ScoringReadinessStatus = 'ready' | 'review_required' | 'insufficient_data' | 'blocked'

export interface PeriodFieldValue {
  observed_value?: number | null
  usable_value?: number | null
  status?: FieldQualityStatus | string
  usable?: boolean
  confidence?: number | null
  evidence?: unknown[]
  warnings?: string[]
}

export interface FinancialField {
  code: string
  label: string
  source?: string | null
  current: PeriodFieldValue
  previous?: PeriodFieldValue | null
  value?: number | null
  value_n1?: number | null
}

export interface AccountingControl {
  code: string
  label: string
  period?: 'current' | 'previous' | null
  period_label?: string | null
  status: 'passed' | 'failed' | 'not_evaluable' | string
  expected?: number | null
  observed?: number | null
  difference?: number | null
  message?: string
}

export interface QualitySummary {
  observed_current_count?: number
  usable_current_count?: number
  observed_previous_count?: number
  usable_previous_count?: number
  suspect_count?: number
  conflict_count?: number
  cross_checked_count?: number
  passed_checks?: number
  failed_checks?: number
  not_evaluable_checks?: number
  presence_completeness_pct?: number
  usable_completeness_pct?: number
  scoring_input_completeness_pct?: number
}

export interface ScoringReadiness {
  ready_for_automatic_scoring?: boolean
  status?: ScoringReadinessStatus | string
  blocking_reasons?: string[]
  scoring_inputs_required?: number
  scoring_inputs_available?: number
  scoring_inputs_usable?: number
}

export interface FiscalDetail {
  label: string
  amount?: number | null
}

export interface FiscalAnalysis {
  available?: boolean
  resultat_net_comptable?: { value?: number | null; status?: string }
  reintegrations?: { total?: number | null; details?: FiscalDetail[] }
  deductions?: { total?: number | null; details?: FiscalDetail[] }
  resultat_brut_fiscal?: { value?: number | null; status?: string }
  reports_deficitaires?: { value?: number | null; status?: string }
  resultat_net_fiscal?: { value?: number | null; status?: string }
  validation_status?: string | null
  warnings?: string[]
}

export interface AssociateRow {
  name?: string | null
  identifier?: string | null
  identifier_type?: string | null
  titres_previous?: number | null
  titres_current?: number | null
  nominal_value?: number | null
  capital_souscrit?: number | null
  capital_appele?: number | null
  capital_libere?: number | null
  status?: string
}

export interface CapitalAnalysis {
  available?: boolean
  capital_social?: { value?: number | null; status?: string }
  validation_status?: string | null
  warnings?: string[]
  associates?: AssociateRow[]
}

export interface FinancialStatementRow {
  label: string
  n?: number | null
  n1?: number | null
  nStatus?: string
  n1Status?: string
  source?: string
  page?: number | null
  confidence?: number | null
  brut?: number | null
  amort?: number | null
}

export interface FinancialStatements {
  synthese?: FinancialStatementRow[]
  actif?: FinancialStatementRow[]
  passif?: FinancialStatementRow[]
  cpc?: FinancialStatementRow[]
  esg?: FinancialStatementRow[]
}

export type SectorAnalysisStatus =
  | 'AVAILABLE'
  | 'PARTIAL'
  | 'UNAVAILABLE'
  | 'MAPPING_REVIEW_REQUIRED'
  | 'UNMAPPED'
  | 'NO_DATA'
  | 'STALE'
  | 'ERROR'

export type SectorDataFreshness = 'FRESH' | 'STALE' | 'VERY_STALE' | 'UNAVAILABLE' | 'REFRESHING' | 'ERROR'

export interface SectorSeriesPoint {
  year: number
  quarter?: number | null
  value: number | null
  unit: string
  growthYoy?: number | null
}

export interface CompanyAnnualPoint {
  year: number
  va: number | null
  ca?: number | null
  unit: string
  vaUsable: boolean
  caUsable?: boolean
}

export interface NormalizedSectorPoint {
  year: number
  companyIndex: number | null
  sectorIndex: number | null
}

export interface GrowthComparisonPoint {
  year: number
  companyGrowth: number | null
  sectorGrowth: number | null
  gapPp: number | null
  companyAvailable: boolean
}

export interface SectorComparableIndicator {
  code: string
  label: string
  companyValue: number | null
  sectorValue: number | null
  unit: string
  gap?: number | null
  comparable: boolean
  reason?: string
  source?: string
}

export interface SectorAnalysisData {
  status: SectorAnalysisStatus
  sector: {
    rawActivity?: string | null
    code?: string | null
    label?: string | null
    mappingConfidence?: number | null
    mappingStatus?: 'MATCHED' | 'REVIEW_REQUIRED' | 'UNMATCHED'
    mappingType?: string | null
    validated?: boolean
    sourceId?: string | null
    sourceLabel?: string | null
    sourceCode?: string | null
  }
  dataFreshness: {
    status: SectorDataFreshness
    lastSyncAt?: string | null
    latestObservationPeriod?: string | null
    source?: string
    datasetVersions?: Array<{ datasetId?: string; sha256?: string | null }>
    cached?: boolean
  }
  headline: {
    latestSectorVa: number | null
    latestYear: number | null
    latestQuarterlyPeriod?: string | null
    latestUnit?: string
    nominalGrowthYoy: number | null
    realGrowthYoy: number | null
    cagr3y: number | null
  }
  sectorAnnualCurrent: SectorSeriesPoint[]
  sectorAnnualReal: SectorSeriesPoint[]
  sectorQuarterly: SectorSeriesPoint[]
  companyAnnual: CompanyAnnualPoint[]
  normalizedComparison: NormalizedSectorPoint[]
  growthComparison: GrowthComparisonPoint[]
  comparableIndicators: SectorComparableIndicator[]
  summary?: string | null
  warnings: string[]
  insights?: Array<{ code: string; severity?: string; text: string }>
  momentum?: {
    trend?: string | null
    latestRealGrowth?: number | null
    previousRealGrowth?: number | null
  }
  scoring: {
    status: 'NOT_CALIBRATED' | 'AVAILABLE' | 'INSUFFICIENT_DATA'
    includedInFinalScore: boolean
    score: number | null
    note?: string
  }
  realGrowthNote?: string
}

export interface AnalyseWorkspace {
  header: AnalyseHeader
  pipeline: PipelineData
  documents: DocumentsBlock
  scoring: ScoringBlock
  ratios: RatiosBlock
  bien: BienBlock
  factorielle: FactorAxis[]
  yearLabels?: [string, string, string] | string[]
  comportement: BehaviourBlock
  sectorAnalysis?: SectorAnalysisData | null
  clientLookup?: ClientLookup | null
  benchmark: BenchmarkBlock
  memo: MemoBlock
  copilot: CopilotBlock
  period?: { start?: string | null; end?: string | null; label?: string | null; yearN?: number | null; yearN1?: number | null }
  financialStatements?: FinancialStatements | null
  fiscalAnalysis?: FiscalAnalysis | null
  capitalAnalysis?: CapitalAnalysis | null
  quality?: QualitySummary | null
  readiness?: ScoringReadiness | null
  controls?: AccountingControl[]
  analysisStale?: boolean
  staleMessage?: string
}

export type AnalyseDecisionPayload = {
  decision: DecisionKind
  comment?: string
}
