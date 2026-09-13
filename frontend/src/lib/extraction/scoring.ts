import type { ExtractionCandidate, FieldType } from '@/lib/extraction/types'
import {
  isNegativeIceContext,
  isNegativeRaisonContext,
  isNegativeRcContext,
  isValidIce,
  isValidRaison,
  isValidRc,
  normalizeIce,
} from '@/lib/extraction/normalize'

export type ScoreInput = {
  fieldType: FieldType
  rawValue: string
  normalizedValue: string
  matchedLabel: string
  context: string
  ocrConfidence?: number
  labelProximity?: 'adjacent' | 'near' | 'far'
  repeatCount?: number
}

export function scoreToConfidence(score: number): number {
  return Math.max(0, Math.min(1, score / 100))
}

export function scoreIce(input: ScoreInput): { confidence: number; reasons: string[] } {
  const reasons: string[] = []
  let score = 0
  const label = input.matchedLabel.toLowerCase()

  if (/identifiant\s+commun/i.test(label)) {
    score += 40
    reasons.push('+40 label Identifiant Commun')
  } else if (/\bice\b|i\.?\s*c\.?\s*e/i.test(label)) {
    score += 50
    reasons.push('+50 label ICE')
  }

  if (label === 'filename') {
    score += 25
    reasons.push('+25 indice dans le nom de fichier')
  }

  if (isValidIce(input.normalizedValue)) {
    score += 30
    reasons.push('+30 format 15 chiffres')
  } else {
    score -= 40
    reasons.push('-40 format ICE invalide')
  }

  if (input.labelProximity === 'adjacent') {
    score += 20
    reasons.push('+20 valeur proche du label')
  }

  if (isNegativeIceContext(input.context)) {
    score -= 50
    reasons.push('-50 contexte négatif (facture/tél/montant)')
  }

  if (input.ocrConfidence && input.ocrConfidence > 75) {
    score += 10
    reasons.push('+10 OCR confidence élevée')
  }

  if ((input.repeatCount ?? 0) > 1) {
    score += 10
    reasons.push('+10 valeur répétée')
  }

  return { confidence: scoreToConfidence(score), reasons }
}

export function scoreRc(input: ScoreInput): { confidence: number; reasons: string[] } {
  const reasons: string[] = []
  let score = 0
  const label = input.matchedLabel.toLowerCase()

  if (/chronologique/i.test(label)) {
    score += 70
    reasons.push('+70 label N° Chronologique (RC métier)')
  } else if (/registre\s+analytique|inscriptions?\s+port/i.test(label)) {
    score += 5
    reasons.push('+5 label registre analytique (non utilisé pour RC formulaire)')
  } else if (/registre\s+(?:de\s+|du\s+)?commerce/i.test(label)) {
    score += 60
    reasons.push('+60 label Registre de Commerce')
  } else if (/num[eé]ro\s*r\.?\s*c|n[°ºo]?\s*r\.?\s*c|\brc\b/i.test(label)) {
    score += 60
    reasons.push('+60 label RC explicite')
  }

  if (label === 'filename') {
    score += 25
    reasons.push('+25 indice dans le nom de fichier')
  }

  if (isValidRc(input.normalizedValue)) {
    score += 15
    reasons.push('+15 format RC cohérent')
  } else {
    score -= 30
    reasons.push('-30 format RC invalide')
  }

  if (input.labelProximity === 'adjacent') {
    score += 20
    reasons.push('+20 valeur proche du label')
  }

  if (
    isNegativeRcContext(input.context) &&
    !/registre\s+analytique|chronologique/i.test(label)
  ) {
    score -= 50
    reasons.push('-50 contexte négatif')
  }

  if (input.ocrConfidence && input.ocrConfidence > 75) {
    score += 10
    reasons.push('+10 OCR confidence élevée')
  }

  if ((input.repeatCount ?? 0) > 1) {
    score += 10
    reasons.push('+10 valeur répétée')
  }

  return { confidence: scoreToConfidence(score), reasons }
}

export function scoreRaison(input: ScoreInput): { confidence: number; reasons: string[] } {
  const reasons: string[] = []
  let score = 0
  const label = input.matchedLabel.toLowerCase()

  if (/raison\s+sociale/i.test(label)) {
    score += 70
    reasons.push('+70 label Raison sociale')
  } else if (/d[eé]nomination\s+sociale/i.test(label)) {
    score += 65
    reasons.push('+65 label Dénomination sociale')
  } else if (/d[eé]nominati/i.test(label)) {
    score += 40
    reasons.push('+40 label Dénomination')
  }

  if (isValidRaison(input.normalizedValue)) {
    score += 20
    reasons.push('+20 format raison sociale cohérent')
  } else {
    score -= 30
    reasons.push('-30 format raison sociale invalide')
  }

  if (input.labelProximity === 'adjacent') {
    score += 30
    reasons.push('+30 valeur proche du label')
  }

  if (isNegativeRaisonContext(input.context)) {
    score -= 40
    reasons.push('-40 contexte Client/Fournisseur')
  }

  if (input.ocrConfidence && input.ocrConfidence > 75) {
    score += 10
    reasons.push('+10 OCR confidence élevée')
  }

  return { confidence: scoreToConfidence(score), reasons }
}

export function scoreCandidate(input: ScoreInput): { confidence: number; reasons: string[] } {
  if (input.fieldType === 'ICE') return scoreIce(input)
  if (input.fieldType === 'RC') return scoreRc(input)
  return scoreRaison(input)
}

export function withScoring(candidate: ExtractionCandidate): ExtractionCandidate {
  const normalizedValue =
    candidate.fieldType === 'ICE'
      ? normalizeIce(candidate.normalizedValue ?? candidate.value)
      : (candidate.normalizedValue ?? candidate.value)

  const { confidence, reasons } = scoreCandidate({
    fieldType: candidate.fieldType,
    rawValue: candidate.rawValue ?? candidate.value,
    normalizedValue,
    matchedLabel: candidate.matchedLabel ?? candidate.label ?? '',
    context: candidate.context,
    ocrConfidence: candidate.ocrConfidence,
    labelProximity: candidate.labelProximity,
    repeatCount: candidate.sources?.length,
  })

  return {
    ...candidate,
    value: normalizedValue,
    normalizedValue,
    confidence,
    reasons: [...(candidate.reasons ?? []), ...reasons],
  }
}
