import type { ExtractionCandidate, OcrWord } from '@/lib/extraction/types'
import { logFieldDetection } from '@/lib/extraction/debug'
import {
  digitsOnly,
  fixOcrDigits,
  isNegativeIceContext,
  isNegativeRaisonContext,
  isNegativeRcContext,
  isValidIce,
  isValidRaison,
  isValidRc,
  normalizeIce,
  normalizeRaison,
  normalizeRc,
  normalizeRcAnalytique,
  prepareTextForExtraction,
  snippet,
} from '@/lib/extraction/normalize'
import { withScoring } from '@/lib/extraction/scoring'
import { wordsToLines } from '@/lib/extraction/ocr'

const ICE_LABEL =
  /(?:IDENTIFIANT\s+COMMUN\s+DE\s+L['']?ENTREPRISE|\bICE\b|N[°ºo]\s*ICE|رقم\s+التعريف\s+الموحد)/gi

const RC_LABEL =
  /(?:Num[eé]ro\s*R\.?\s*C\.?|Registre\s+(?:de\s+|du\s+)?Commerce|N[°ºo]?\s*R\.?\s*C\.?\s*:|\bR\.?\s*C\.?\s*:|\bRC\s*:)/gi

const RC_ANALYTIQUE_LABEL =
  /(?:Copie\s+des\s+Inscriptions\s+Port[eé]es\s+au\s+registre\s+analytique|Inscriptions\s+Port[eé]es\s+au\s+registre\s+analytique|registre\s+analytique)/gi

const RC_CHRONOLOGIQUE_LABEL =
  /(?:N[°ºo*.\s]*Chron[oa0]l[oa0]g\w*|Num[eé]ro\s+Chron[oa0]l\w*|Chronotogique|Chronalogique)/gi

const RAISON_LABEL =
  /(?:Raison\s+sociale|D[eé]nominati(?:on|o)\s+sociale|D[eé]nomination|Nom\s+de\s+l['']?entreprise)/gi

function pushUnique(candidates: ExtractionCandidate[], candidate: ExtractionCandidate) {
  const scored = withScoring(candidate)
  const key = `${scored.fieldType}:${scored.value}`
  const existing = candidates.find((c) => `${c.fieldType}:${c.value}` === key)
  if (existing) {
    existing.sources = [
      ...(existing.sources ?? [{ file: existing.sourceFile, context: existing.context }]),
      { file: scored.sourceFile, page: scored.page, context: scored.context },
    ]
    if (scored.confidence > existing.confidence) {
      Object.assign(existing, scored)
    }
    return
  }
  candidates.push(scored)
  logFieldDetection({
    field: scored.fieldType,
    value: scored.value,
    rawValue: scored.rawValue,
    label: scored.matchedLabel,
    confidence: scored.confidence.toFixed(2),
    reasons: scored.reasons?.join('; '),
  })
}

function detectIceCandidates(
  normalized: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []

  for (const match of normalized.matchAll(ICE_LABEL)) {
    const index = match.index ?? 0
    const window = normalized.slice(index, index + 160)
    const context = snippet(normalized, index)
    if (isNegativeIceContext(context)) continue

    const num = window.match(/(?:ICE|IDENTIFIANT\s+COMMUN[^0-9]{0,40})([0-9OIl\s.\-]{12,22})/i)
      ?? window.match(/([0-9OIl][0-9OIl\s.\-]{12,22})/)
    if (!num) continue
    const rawValue = num[1].trim()
    const digits = normalizeIce(rawValue)
    if (!isValidIce(digits)) continue

    pushUnique(candidates, {
      fieldType: 'ICE',
      value: digits,
      rawValue,
      normalizedValue: digits,
      confidence: 0,
      sourceFile,
      page,
      context,
      label: match[0],
      matchedLabel: match[0],
      ocrConfidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context }],
    })
  }

  if (
    candidates.length === 0 &&
    /identification du contribuable/i.test(normalized)
  ) {
    const m = normalized.match(/\b(\d{15})\b/)
    if (m && isValidIce(m[1])) {
      pushUnique(candidates, {
        fieldType: 'ICE',
        value: digitsOnly(m[1]),
        rawValue: m[1],
        normalizedValue: digitsOnly(m[1]),
        confidence: 0,
        sourceFile,
        page,
        context: snippet(normalized, m.index ?? 0),
        label: 'Identification du contribuable',
        matchedLabel: 'Identification du contribuable',
        ocrConfidence,
        labelProximity: 'near',
        sources: [{ file: sourceFile, page, context: snippet(normalized, m.index ?? 0) }],
      })
    }
  }

  return candidates
}

function detectRcAnalytiqueCandidates(
  normalized: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []

  for (const match of normalized.matchAll(RC_ANALYTIQUE_LABEL)) {
    const index = match.index ?? 0
    const context = snippet(normalized, index, 90)
    const window = normalized.slice(index, index + 120)

    const valueMatch =
      window.match(/registre\s+analytique\s+N[°ºo.]?\s*:?\s*([0-9OIl]{4,8})/i) ??
      window.match(/analytique\s+N[°ºo.]?\s*:?\s*([0-9OIl]{4,8})/i) ??
      window.match(/Inscriptions?\s+Port[eé]es[^0-9]{0,40}N[°ºo.]?\s*:?\s*([0-9OIl]{4,8})/i) ??
      window.match(/N[°ºo.]?\s*:?\s*([0-9OIl]{4,8})/i)

    if (!valueMatch) continue
    const rawValue = valueMatch[1]
    const value = normalizeRcAnalytique(rawValue)
    if (!isValidRc(value)) continue

    pushUnique(candidates, {
      fieldType: 'RC',
      value,
      rawValue,
      normalizedValue: value,
      confidence: 0,
      sourceFile,
      page,
      context,
      label: match[0],
      matchedLabel: 'registre analytique',
      ocrConfidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context }],
    })
  }

  return candidates
}

function detectRcChronologiqueCandidates(
  normalized: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []

  const tryPush = (rawValue: string, label: string, context: string) => {
    const value = normalizeRc(digitsOnly(fixOcrDigits(rawValue)))
    if (!isValidRc(value)) return
    if (value.length > 6) return
    pushUnique(candidates, {
      fieldType: 'RC',
      value,
      rawValue,
      normalizedValue: value,
      confidence: 0,
      sourceFile,
      page,
      context,
      label,
      matchedLabel: 'N° Chronologique',
      ocrConfidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context }],
    })
  }

  for (const match of normalized.matchAll(RC_CHRONOLOGIQUE_LABEL)) {
    const index = match.index ?? 0
    const context = snippet(normalized, index, 100)
    const window = normalized.slice(index, index + 120)

    const valueMatch =
      window.match(
        /Chron[oa0]l[oa0]g\w*[^0-9]{0,40}?([0-9OIl]{2,6})\b/i,
      ) ?? window.match(/:\s*([0-9OIl]{2,6})\b/)

    if (valueMatch) tryPush(valueMatch[1], match[0], context)
  }

  for (const match of normalized.matchAll(
    /Immatriculation[^.\n]{0,80}?Chron[oa0]l[oa0]g\w*[^0-9]{0,40}([0-9OIl]{2,6})/gi,
  )) {
    tryPush(match[1], 'N° Chronologique', snippet(normalized, match.index ?? 0, 100))
  }

  if (candidates.length === 0) {
    const loose = normalized.match(
      /Chron[oa0]l[oa0]g\w{0,12}[\s\S]{0,60}?([0-9OIl]{2,6})(?!\d)/i,
    )
    if (loose) tryPush(loose[1], 'N° Chronologique', loose[0])
  }

  return candidates
}

function detectRcCandidates(
  normalized: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []
  const chrono = detectRcChronologiqueCandidates(normalized, sourceFile, page, ocrConfidence)
  const analytique = detectRcAnalytiqueCandidates(normalized, sourceFile, page, ocrConfidence)
  candidates.push(...chrono, ...analytique)

  for (const match of normalized.matchAll(RC_LABEL)) {
    const index = match.index ?? 0
    const context = snippet(normalized, index)
    if (isNegativeRcContext(context)) continue
    if (/analytique|inscriptions?\s+port/i.test(context) && chrono.length > 0) continue

    const window = normalized.slice(index, index + 120)
    const valueMatch = window.match(
      /(?:Num[eé]ro\s*R\.?\s*C\.?|Registre\s+(?:de\s+|du\s+)?Commerce|\bR\.?\s*C\.?|N[°ºo]?\s*R\.?\s*C|\bRC)\s*:?\s*([0-9]{1,8}\s*[/%]\s*[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{2,20}|[0-9]{2,8}\s*\/\s*[A-Za-zÀ-ÿ\-]+|[A-Za-zÀ-ÿ]{3,20}\s+[0-9]{2,8}|[0-9]{2,8})/i,
    )
    if (!valueMatch) continue
    const rawValue = valueMatch[1].trim()
    const value = normalizeRc(rawValue)
    if (!isValidRc(value)) continue
    if (/registre\s+(?:de\s+|du\s+)?commerce/i.test(match[0]) && /^\d{4,8}$/.test(value) && chrono.length > 0) {
      continue
    }

    pushUnique(candidates, {
      fieldType: 'RC',
      value,
      rawValue,
      normalizedValue: value,
      confidence: 0,
      sourceFile,
      page,
      context,
      label: match[0],
      matchedLabel: match[0],
      ocrConfidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context }],
    })
  }

  return candidates
}

function detectRaisonCandidates(
  normalized: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []

  for (const match of normalized.matchAll(RAISON_LABEL)) {
    const index = match.index ?? 0
    const context = snippet(normalized, index)
    if (isNegativeRaisonContext(context)) continue

    const window = normalized.slice(index, index + 200)
    const valueMatch = window.match(
      /(?:Raison\s+sociale|D[eé]nominati(?:on|o)\s+sociale|D[eé]nomination|Nom\s+de\s+l['']?entreprise)\s*(?:\([^)]*\))?\s*:?\s*([A-ZÀ-Ÿ0-9][A-ZÀ-Ÿ0-9\s,'’\-&\.]{3,120})/i,
    )
    if (!valueMatch) continue

    const rawValue = valueMatch[1]
    const value = cleanRaisonValue(rawValue)
    if (!isValidRaison(value)) continue

    pushUnique(candidates, {
      fieldType: 'RAISON_SOCIALE',
      value,
      rawValue,
      normalizedValue: value,
      confidence: 0,
      sourceFile,
      page,
      context,
      label: match[0],
      matchedLabel: match[0],
      ocrConfidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context }],
    })
  }

  return candidates
}

function cleanRaisonValue(raw: string): string {
  const stop = raw.search(
    /\s+(?:N[°ºo]|Num[eé]ro|CODE\s+DEMANDE|Chronologique|IDENTIFIANT|CNSS|Origine|Activit[eé]|Si[eè]ge|Sigle)\b/i,
  )
  const trimmed = stop > 0 ? raw.slice(0, stop) : raw
  return normalizeRaison(
    trimmed
      .replace(/\b(IDENTIFIANT|FISCAL|NUMERO|CNSS|RC|Sigle)\b.*$/i, '')
      .replace(/\s+N\s*$/i, '')
      .replace(/\([a-z)]*\)\s*$/i, ''),
  )
}

function detectRcFromWordBoxes(
  words: OcrWord[],
  sourceFile: string,
  page?: number,
): ExtractionCandidate[] {
  const candidates: ExtractionCandidate[] = []
  const chronoLabels = words.filter((w) => /chron[oa0]/i.test(w.text))

  for (const label of chronoLabels) {
    const ly = label.y ?? 0
    const lx = (label.x ?? 0) + (label.width ?? 0)

    const numberWords = words
      .map((w) => ({
        word: w,
        digits: digitsOnly(fixOcrDigits(w.text.replace(/^N[°ºo*:.\s]*/i, ''))),
      }))
      .filter(({ word, digits }) => {
        if (!/^\d{2,6}$/.test(digits)) return false
        if (/^20\d{2}$/.test(digits)) return false
        const wy = word.y ?? 0
        const wx = word.x ?? 0
        return Math.abs(wy - ly) <= 24 && wx >= lx - 20
      })
      .sort((a, b) => b.word.confidence - a.word.confidence || (a.word.x ?? 0) - (b.word.x ?? 0))

    const best = numberWords[0]
    if (!best) continue

    const value = normalizeRc(best.digits)
    if (!isValidRc(value) || value.length > 6) continue

    pushUnique(candidates, {
      fieldType: 'RC',
      value,
      rawValue: best.word.text,
      normalizedValue: value,
      confidence: 0,
      sourceFile,
      page,
      context: `OCR boxes: "${label.text}" → "${best.word.text}" (conf ${best.word.confidence.toFixed(0)})`,
      label: label.text,
      matchedLabel: 'N° Chronologique',
      ocrConfidence: best.word.confidence,
      labelProximity: 'adjacent',
      sources: [{ file: sourceFile, page, context: label.text }],
    })
  }

  return candidates
}

function detectFromOcrWords(
  words: OcrWord[],
  sourceFile: string,
  page?: number,
  avgConfidence?: number,
): ExtractionCandidate[] {
  if (words.length === 0) return []
  const fromBoxes = detectRcFromWordBoxes(words, sourceFile, page)
  const lines = wordsToLines(words)
  const text = prepareTextForExtraction(lines.join('\n'))
  const fromText = detectCandidates(text, sourceFile, page, avgConfidence)

  if (fromBoxes.length > 0) {
    const boxRc = new Set(fromBoxes.map((c) => c.value))
    return [
      ...fromBoxes,
      ...fromText.filter(
        (c) =>
          c.fieldType !== 'RC' ||
          boxRc.has(c.value) ||
          (c.matchedLabel && /num[eé]ro\s*r/i.test(c.matchedLabel)),
      ),
    ]
  }

  return fromText
}

export function detectCandidates(
  text: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  const normalized = prepareTextForExtraction(text)
  const all: ExtractionCandidate[] = []

  for (const c of detectIceCandidates(normalized, sourceFile, page, ocrConfidence)) {
    all.push(c)
  }
  for (const c of detectRcCandidates(normalized, sourceFile, page, ocrConfidence)) {
    all.push(c)
  }
  for (const c of detectRaisonCandidates(normalized, sourceFile, page, ocrConfidence)) {
    all.push(c)
  }

  return all
}

export function detectFromFilename(
  filename: string,
  sourceFile: string,
): ExtractionCandidate[] {
  const base = filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ')
  const candidates: ExtractionCandidate[] = []

  const iceMatch =
    base.match(/(?:ICE|ice)[\s_-]*([0-9]{15})/) ?? base.match(/\b([0-9]{15})\b/)
  if (iceMatch && isValidIce(digitsOnly(iceMatch[1]))) {
    pushUnique(candidates, {
      fieldType: 'ICE',
      value: digitsOnly(iceMatch[1]),
      rawValue: iceMatch[1],
      confidence: 0,
      sourceFile,
      context: `filename: ${filename}`,
      label: 'filename',
      matchedLabel: 'filename',
      labelProximity: 'far',
      sources: [{ file: sourceFile, context: `filename: ${filename}` }],
    })
  }

  const rcMatch = base.match(/(?:RC|rc)[\s_-]*([0-9]{1,8}[/%][A-Za-z]+|[0-9]{2,8})/i)
  if (rcMatch) {
    const value = normalizeRc(rcMatch[1])
    if (isValidRc(value)) {
      pushUnique(candidates, {
        fieldType: 'RC',
        value,
        rawValue: rcMatch[1],
        confidence: 0,
        sourceFile,
        context: `filename: ${filename}`,
        label: 'filename',
        matchedLabel: 'filename',
        labelProximity: 'far',
        sources: [{ file: sourceFile, context: `filename: ${filename}` }],
      })
    }
  }

  return candidates
}

export function extractFromText(
  text: string,
  sourceFile: string,
  page?: number,
  ocrConfidence?: number,
): ExtractionCandidate[] {
  return detectCandidates(text, sourceFile, page, ocrConfidence)
}

export function extractFromOcrResult(result: {
  text: string
  words: OcrWord[]
  avgConfidence: number
  page?: number
  sourceFile: string
}): ExtractionCandidate[] {
  const fromBoxes = detectRcFromWordBoxes(result.words, result.sourceFile, result.page)
  const fromText = detectCandidates(
    result.text,
    result.sourceFile,
    result.page,
    result.avgConfidence,
  )

  if (fromBoxes.length > 0) {
    const boxRcValues = new Set(fromBoxes.map((c) => c.value))
    const filtered = fromText.filter(
      (c) =>
        c.fieldType !== 'RC' ||
        boxRcValues.has(c.value) ||
        (c.matchedLabel && /num[eé]ro\s*r\.?\s*c/i.test(c.matchedLabel)),
    )
    const merged: ExtractionCandidate[] = [...fromBoxes]
    for (const c of filtered) pushUnique(merged, c)
    return merged
  }

  const fromWords = detectFromOcrWords(
    result.words,
    result.sourceFile,
    result.page,
    result.avgConfidence,
  )
  const merged: ExtractionCandidate[] = [...fromText]
  for (const c of fromWords) pushUnique(merged, c)
  return merged
}
