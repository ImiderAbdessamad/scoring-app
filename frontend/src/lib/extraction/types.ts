export type FieldType = 'ICE' | 'RC' | 'RAISON_SOCIALE'

export type OcrWord = {
  text: string
  confidence: number
  page?: number
  x?: number
  y?: number
  width?: number
  height?: number
}

export type OcrResult = {
  text: string
  words: OcrWord[]
  avgConfidence: number
  page?: number
}

export type CandidateSource = {
  file: string
  page?: number
  context: string
}

export type ExtractionCandidate = {
  value: string
  rawValue?: string
  normalizedValue?: string
  confidence: number
  sourceFile: string
  context: string
  fieldType: FieldType
  label?: string
  matchedLabel?: string
  page?: number
  reasons?: string[]
  ocrConfidence?: number
  labelProximity?: 'adjacent' | 'near' | 'far'
  sources?: CandidateSource[]
}

export type FieldState = {
  value: string
  confidence: number
  sourceFile: string
  context: string
  sources?: CandidateSource[]
}

export type ExtractionConflict = {
  fieldType: FieldType
  existing: FieldState
  incoming: ExtractionCandidate
  candidates?: ExtractionCandidate[]
}

export type ExtractionState = {
  ice?: FieldState
  rc?: FieldState
  raisonSociale?: FieldState
  conflicts: ExtractionConflict[]
}

export type MergeDecision = 'ACCEPT' | 'REJECT' | 'KEEP' | 'CONFLICT'

export type MergeResult = {
  state: ExtractionState
  decision: MergeDecision
  reason: string
}

export const CONFIDENCE_HIGH = 0.8
export const CONFIDENCE_MEDIUM = 0.5

export type ExtractedEntrepriseFields = {
  ice?: string
  rc?: string
  raisonSociale?: string
}

export function stateToFields(state: ExtractionState): ExtractedEntrepriseFields {
  return {
    ice: state.ice?.value,
    rc: state.rc?.value,
    raisonSociale: state.raisonSociale?.value,
  }
}
