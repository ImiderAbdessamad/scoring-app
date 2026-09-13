import type { OcrResult, OcrWord } from '@/lib/extraction/types'
import { logOcr, withSilentTesseractConsole } from '@/lib/extraction/debug'

const TESS_LANG = 'fra+eng'
const TESS_LANG_PATH = 'https://cdn.jsdelivr.net/gh/naptha/tessdata@gh-pages/4.0.0'

type PreprocessMode = 'soft' | 'binary'

async function preprocessForOcr(blob: Blob, mode: PreprocessMode = 'soft'): Promise<Blob> {
  const bitmap = await createImageBitmap(blob)
  const scale = mode === 'soft' ? 2.5 : 3
  const w = Math.round(bitmap.width * scale)
  const h = Math.round(bitmap.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return blob

  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(bitmap, 0, 0, w, h)
  bitmap.close()

  const img = ctx.getImageData(0, 0, w, h)
  const d = img.data
  let min = 255
  let max = 0
  const gray = new Float32Array(w * h)
  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    const g = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]
    gray[p] = g
    if (g < min) min = g
    if (g > max) max = g
  }
  const range = Math.max(1, max - min)
  for (let i = 0, p = 0; i < d.length; i += 4, p++) {
    const normalized = ((gray[p] - min) / range) * 255
    const contrasted = Math.min(255, Math.max(0, normalized * 1.25 - 10))
    const v = mode === 'binary' ? (contrasted > 155 ? 255 : 0) : contrasted
    d[i] = d[i + 1] = d[i + 2] = v
    d[i + 3] = 255
  }
  ctx.putImageData(img, 0, 0)

  const out = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/png', 1),
  )
  return out ?? blob
}

function mapWords(data: {
  words?: Array<{
    text: string
    confidence: number
    bbox: { x0: number; y0: number; x1: number; y1: number }
  }>
  blocks?: Array<{
    paragraphs?: Array<{
      lines?: Array<{
        words?: Array<{
          text: string
          confidence: number
          bbox: { x0: number; y0: number; x1: number; y1: number }
        }>
      }>
    }>
  }> | null
}): OcrWord[] {
  if (data.words?.length) {
    return data.words.map((w) => ({
      text: w.text,
      confidence: w.confidence,
      x: w.bbox.x0,
      y: w.bbox.y0,
      width: w.bbox.x1 - w.bbox.x0,
      height: w.bbox.y1 - w.bbox.y0,
    }))
  }

  const words: OcrWord[] = []
  for (const block of data.blocks ?? []) {
    for (const para of block.paragraphs ?? []) {
      for (const line of para.lines ?? []) {
        for (const w of line.words ?? []) {
          words.push({
            text: w.text,
            confidence: w.confidence,
            x: w.bbox.x0,
            y: w.bbox.y0,
            width: w.bbox.x1 - w.bbox.x0,
            height: w.bbox.y1 - w.bbox.y0,
          })
        }
      }
    }
  }
  return words
}

async function recognizeOnce(
  prepared: Blob,
  _sourceFile: string,
  page?: number,
): Promise<OcrResult> {
  const { createWorker, PSM } = await import('tesseract.js')

  return withSilentTesseractConsole(async () => {
    const worker = await createWorker(TESS_LANG, 1, {
      langPath: TESS_LANG_PATH,
      cacheMethod: 'none',
      gzip: true,
      logger: () => {},
    })

    try {
      await worker.setParameters({ tessedit_pageseg_mode: PSM.AUTO })
      const first = await worker.recognize(prepared, {}, { blocks: true, text: true })
      let text = first.data.text || ''
      let words = mapWords(first.data)

      if (text.trim().length < 80) {
        await worker.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_BLOCK })
        const second = await worker.recognize(prepared, {}, { blocks: true, text: true })
        text = `${text}\n${second.data.text || ''}`
        words = [...words, ...mapWords(second.data)]
      }

      const avgConfidence =
        words.length > 0
          ? words.reduce((s, w) => s + w.confidence, 0) / words.length
          : 0

      return { text, words, avgConfidence, page }
    } finally {
      await worker.terminate()
    }
  })
}

export async function ocrBlob(
  blob: Blob,
  sourceFile: string,
  page?: number,
): Promise<OcrResult> {
  logOcr('OCR started', { file: sourceFile, type: blob.type, page: page ?? 1, mode: 'soft' })

  const soft = await preprocessForOcr(blob, 'soft')
  let result = await recognizeOnce(soft, sourceFile, page)

  const hasChronoRc =
    /chron[oa]/i.test(result.text) &&
    result.words.some((w) => {
      const d = w.text.replace(/\D/g, '')
      return /^\d{2,6}$/.test(d) && !/^20\d{2}$/.test(d)
    })

  const looksWeak =
    result.text.trim().length < 120 ||
    !/(ICE|RC|D[eé]nomination|Registre|analytique|Raison|Chron)/i.test(result.text)

  if (looksWeak && !hasChronoRc) {
    logOcr('OCR soft weak — retry binary', {
      file: sourceFile,
      chars: result.text.length,
    })
    const binary = await preprocessForOcr(blob, 'binary')
    const second = await recognizeOnce(binary, sourceFile, page)
    if (second.text.trim().length > result.text.trim().length) {
      result = {
        text: `${result.text}\n${second.text}`,
        words: [...result.words, ...second.words],
        avgConfidence: (result.avgConfidence + second.avgConfidence) / 2,
        page,
      }
    } else {
      result = {
        text: `${result.text}\n${second.text}`,
        words: [...result.words, ...second.words],
        avgConfidence: result.avgConfidence,
        page,
      }
    }
  }

  logOcr('OCR completed', {
    file: sourceFile,
    page: page ?? 1,
    chars: result.text.length,
    words: result.words.length,
    avgConfidence: result.avgConfidence.toFixed(1),
    preview: result.text.slice(0, 280).replace(/\n/g, ' '),
  })

  return result
}

export async function ocrImageFile(file: File): Promise<OcrResult> {
  return ocrBlob(file, file.name)
}

export async function ocrCanvas(
  canvas: HTMLCanvasElement,
  sourceFile: string,
  page: number,
): Promise<OcrResult> {
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Canvas toBlob failed'))), 'image/png')
  })
  return ocrBlob(blob, sourceFile, page)
}

export function wordsToLines(words: OcrWord[], lineTolerance = 12): string[] {
  if (words.length === 0) return []
  const sorted = [...words].sort((a, b) => (a.y ?? 0) - (b.y ?? 0) || (a.x ?? 0) - (b.x ?? 0))
  const lines: Array<{ y: number; texts: string[] }> = []

  for (const w of sorted) {
    const y = w.y ?? 0
    const line = lines.find((l) => Math.abs(l.y - y) <= lineTolerance)
    if (line) {
      line.texts.push(w.text)
    } else {
      lines.push({ y, texts: [w.text] })
    }
  }

  return lines.map((l) => l.texts.join(' '))
}
