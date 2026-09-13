import type {
  ExtractionCandidate,
  ExtractionConflict,
  ExtractionState,
  FieldState,
  FieldType,
  MergeDecision,
  MergeResult,
} from '@/lib/extraction/types'
import { CONFIDENCE_HIGH, CONFIDENCE_MEDIUM } from '@/lib/extraction/types'
import { logDecision } from '@/lib/extraction/debug'
import { normalizeIce, normalizeRaison, normalizeRc } from '@/lib/extraction/normalize'

const DEBUG = import.meta.env.DEV

function normalizeForField(fieldType: FieldType, value: string): string {
  if (fieldType === 'ICE') return normalizeIce(value)
  if (fieldType === 'RC') return normalizeRc(value)
  return normalizeRaison(value)
}

function toFieldState(candidate: ExtractionCandidate): FieldState {
  return {
    value: candidate.value,
    confidence: candidate.confidence,
    sourceFile: candidate.sourceFile,
    context: candidate.context,
    sources: candidate.sources,
  }
}

function logMergeDecision(
  candidate: ExtractionCandidate,
  current: FieldState | undefined,
  decision: MergeDecision,
  reason: string,
) {
  if (!DEBUG) return
  logDecision({
    file: candidate.sourceFile,
    field: candidate.fieldType,
    value: candidate.value,
    context: candidate.context.slice(0, 90),
    label: candidate.matchedLabel ?? candidate.label,
    confidence: candidate.confidence.toFixed(2),
    existing: current?.value ?? '—',
    existingConfidence: current?.confidence?.toFixed(2) ?? 'n/a',
    decision,
    reason,
    scoring: candidate.reasons?.join('; '),
  })
}

export function mergeField(
  current: FieldState | undefined,
  candidate: ExtractionCandidate,
): { next?: FieldState; decision: MergeDecision; reason: string; conflict?: ExtractionConflict } {
  if (candidate.confidence < CONFIDENCE_MEDIUM) {
    return { next: current, decision: 'REJECT', reason: 'confidence below medium threshold' }
  }

  const candNorm = normalizeForField(candidate.fieldType, candidate.value)
  const currNorm = current ? normalizeForField(candidate.fieldType, current.value) : ''

  if (current && candNorm === currNorm) {
    return { next: current, decision: 'KEEP', reason: 'same validated value' }
  }

  if (!current) {
    return {
      next: toFieldState({ ...candidate, value: candNorm }),
      decision: 'ACCEPT',
      reason:
        candidate.confidence >= CONFIDENCE_HIGH
          ? 'new high-confidence value'
          : 'new medium-confidence value on empty field',
    }
  }

  if (current && candNorm !== currNorm) {
    if (Math.abs(candidate.confidence - current.confidence) <= 0.05) {
      return {
        next: current,
        decision: 'CONFLICT',
        reason: 'conflicting values with similar confidence',
        conflict: { fieldType: candidate.fieldType, existing: current, incoming: candidate },
      }
    }
    if (candidate.confidence > current.confidence + 0.05) {
      return {
        next: toFieldState({ ...candidate, value: candNorm }),
        decision: 'ACCEPT',
        reason: 'incoming value has higher confidence',
      }
    }
    return { next: current, decision: 'REJECT', reason: 'existing value is more reliable' }
  }

  return { next: current, decision: 'KEEP', reason: 'default keep existing' }
}

export function mergeCandidate(state: ExtractionState, candidate: ExtractionCandidate): MergeResult {
  const key =
    candidate.fieldType === 'ICE'
      ? 'ice'
      : candidate.fieldType === 'RC'
        ? 'rc'
        : 'raisonSociale'

  const current = state[key]
  const { next, decision, reason, conflict } = mergeField(current, candidate)
  logMergeDecision(candidate, current, decision, reason)

  const nextState: ExtractionState = {
    ...state,
    [key]: next,
    conflicts: conflict ? [...state.conflicts, conflict] : state.conflicts,
  }

  return { state: nextState, decision, reason }
}

export function mergeCandidates(
  state: ExtractionState,
  candidates: ExtractionCandidate[],
): ExtractionState {
  return candidates.reduce((acc, c) => mergeCandidate(acc, c).state, state)
}

export function stateFromForm(values: {
  ice?: string
  rc?: string
  raisonSociale?: string
}): ExtractionState {
  const state: ExtractionState = { conflicts: [] }
  if (values.ice?.trim()) {
    state.ice = {
      value: normalizeIce(values.ice),
      confidence: 1,
      sourceFile: 'form',
      context: 'existing form value',
    }
  }
  if (values.rc?.trim()) {
    state.rc = {
      value: normalizeRc(values.rc),
      confidence: 1,
      sourceFile: 'form',
      context: 'existing form value',
    }
  }
  if (values.raisonSociale?.trim()) {
    state.raisonSociale = {
      value: normalizeRaison(values.raisonSociale),
      confidence: 1,
      sourceFile: 'form',
      context: 'existing form value',
    }
  }
  return state
}

export function conflictSummary(state: ExtractionState): string | null {
  if (state.conflicts.length === 0) return null
  const fields = [...new Set(state.conflicts.map((c) => c.fieldType))].join(', ')
  return `Conflit détecté sur ${fields} — vérifiez les documents avant de continuer.`
}
