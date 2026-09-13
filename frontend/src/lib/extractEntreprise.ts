import type { UploadedFileMeta } from '@/types/create-dossier'
import {
  detectFromFilename,
  extractFromOcrResult,
  extractFromText,
} from '@/lib/extraction/detectors'
import { logOcr, logPipeline } from '@/lib/extraction/debug'
import { ocrImageFile } from '@/lib/extraction/ocr'
import { extractPdfContent } from '@/lib/extraction/pdf'
import {
  conflictSummary,
  mergeCandidates,
  stateFromForm,
} from '@/lib/extraction/merge'
import type {
  ExtractionCandidate,
  ExtractionState,
  ExtractedEntrepriseFields,
} from '@/lib/extraction/types'
import { stateToFields } from '@/lib/extraction/types'
import { ExtractionWorkspace } from '@/lib/extraction/workspace'

export type { ExtractedEntrepriseFields, ExtractionCandidate, ExtractionState }

function isImageFile(mime: string, lower: string): boolean {
  return mime.startsWith('image/') || /\.(png|jpe?g)$/i.test(lower)
}

function isPdfFile(mime: string, lower: string): boolean {
  return mime === 'application/pdf' || lower.endsWith('.pdf')
}

function dedupeCandidates(candidates: ExtractionCandidate[]): ExtractionCandidate[] {
  const map = new Map<string, ExtractionCandidate>()
  for (const c of candidates) {
    const key = `${c.fieldType}:${c.value}`
    const existing = map.get(key)
    if (!existing) {
      map.set(key, c)
      continue
    }
    existing.sources = [
      ...(existing.sources ?? [{ file: existing.sourceFile, context: existing.context }]),
      ...(c.sources ?? [{ file: c.sourceFile, page: c.page, context: c.context }]),
    ]
    if (c.confidence > existing.confidence) {
      map.set(key, { ...c, sources: existing.sources })
    }
  }
  return [...map.values()]
}

export async function extractCandidatesFromFile(
  file: File,
  workspace?: ExtractionWorkspace,
): Promise<ExtractionCandidate[]> {
  const sourceFile = file.name
  const mime = file.type || ''
  const lower = file.name.toLowerCase()
  const ws = workspace ?? new ExtractionWorkspace()

  if (workspace) {
    ws.add(file.name, file)
  }

  const fromName = detectFromFilename(file.name, sourceFile)
  let fromContent: ExtractionCandidate[] = []
  let ocrText = ''

  try {
    logPipeline('file start', { file: sourceFile, mime, size: file.size })

    if (isImageFile(mime, lower)) {
      logOcr('Processing image', { file: sourceFile, mime })
      const ocr = await ocrImageFile(file)
      ocrText = ocr.text
      fromContent = extractFromOcrResult({
        text: ocr.text,
        words: ocr.words,
        avgConfidence: ocr.avgConfidence,
        page: ocr.page,
        sourceFile,
      })
    } else if (isPdfFile(mime, lower)) {
      logOcr('Processing PDF', { file: sourceFile, mime })
      const pdf = await extractPdfContent(file, sourceFile)
      ocrText = pdf.combinedText
      for (let i = 0; i < pdf.textPages.length; i++) {
        const pageNum = i + 1
        const pageText = pdf.textPages[i]
        fromContent.push(...extractFromText(pageText, sourceFile, pageNum))
        const ocrPage = pdf.ocrPages.find((p) => p.page === pageNum)
        if (ocrPage) {
          fromContent.push(
            ...extractFromOcrResult({
              text: ocrPage.text,
              words: ocrPage.words,
              avgConfidence: ocrPage.avgConfidence,
              page: pageNum,
              sourceFile,
            }),
          )
        }
      }
    } else if (mime.startsWith('text/') || lower.endsWith('.txt')) {
      fromContent = extractFromText(await file.text(), sourceFile)
    }

    const all = dedupeCandidates([...fromContent, ...fromName])

    logPipeline('file done', {
      file: sourceFile,
      candidates: all.length,
      ice: all.find((c) => c.fieldType === 'ICE')?.value ?? '—',
      rc: all.find((c) => c.fieldType === 'RC')?.value ?? '—',
      raison: all.find((c) => c.fieldType === 'RAISON_SOCIALE')?.value ?? '—',
      ocrChars: ocrText.length,
    })

    return all
  } catch (err) {
    logPipeline('file error (ignored for other files)', {
      file: sourceFile,
      error: err instanceof Error ? err.message : String(err),
    })
    return fromName
  } finally {
    if (!workspace) {
      ws.cleanup()
    }
  }
}

export async function extractEntrepriseFromFile(
  file: File,
): Promise<ExtractedEntrepriseFields> {
  const ws = new ExtractionWorkspace()
  try {
    const candidates = await extractCandidatesFromFile(file, ws)
    const state = mergeCandidates({ conflicts: [] }, candidates)
    return stateToFields(state)
  } finally {
    ws.cleanup()
  }
}

export type FileExtractionProgress = {
  index: number
  total: number
  fileName: string
  state: ExtractionState
  fields: ExtractedEntrepriseFields
  candidates: ExtractionCandidate[]
}

export async function mergeFilesIntoStateSequential(
  files: UploadedFileMeta[],
  existing: ExtractionState,
  onFileDone?: (progress: FileExtractionProgress) => void,
): Promise<ExtractionState> {
  const ws = new ExtractionWorkspace()
  const withFile = files.filter((f) => f.file)
  try {
    let state = existing
    logPipeline('batch start', { total: withFile.length })

    for (let i = 0; i < withFile.length; i++) {
      const meta = withFile[i]
      if (!meta.file) continue

      logPipeline('batch file', {
        index: i + 1,
        total: withFile.length,
        file: meta.name,
      })

      const candidates = await extractCandidatesFromFile(meta.file, ws)
      state = mergeCandidates(state, candidates)

      onFileDone?.({
        index: i + 1,
        total: withFile.length,
        fileName: meta.name,
        state,
        fields: stateToFields(state),
        candidates,
      })
    }

    logPipeline('batch done', {
      ice: state.ice?.value ?? '—',
      rc: state.rc?.value ?? '—',
      raison: state.raisonSociale?.value ?? '—',
      conflicts: state.conflicts.length,
    })

    return state
  } finally {
    ws.cleanup()
  }
}

export async function mergeFilesIntoState(
  files: UploadedFileMeta[],
  existing: ExtractionState,
): Promise<ExtractionState> {
  return mergeFilesIntoStateSequential(files, existing)
}

export async function extractEntrepriseFromFiles(
  files: UploadedFileMeta[],
): Promise<ExtractedEntrepriseFields> {
  const state = await mergeFilesIntoState(files, { conflicts: [] })
  return stateToFields(state)
}

export { conflictSummary, mergeCandidates, stateFromForm, stateToFields }
