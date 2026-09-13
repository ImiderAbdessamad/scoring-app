import type { OcrResult } from '@/lib/extraction/types'
import { logOcr } from '@/lib/extraction/debug'
import { ocrCanvas } from '@/lib/extraction/ocr'

type PdfTextItem = { str: string; transform?: number[] }

async function loadPdfJs() {
  const pdfjs = await import('pdfjs-dist')
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url,
    ).toString()
  }
  return pdfjs
}

export type PdfExtractionResult = {
  textPages: string[]
  ocrPages: OcrResult[]
  combinedText: string
  usedOcr: boolean
}

export async function extractPdfContent(
  file: File,
  sourceFile: string,
): Promise<PdfExtractionResult> {
  const pdfjs = await loadPdfJs()
  const buf = await file.arrayBuffer()
  const pdf = await pdfjs.getDocument({ data: buf }).promise

  const textPages: string[] = []
  const ocrPages: OcrResult[] = []
  let usedOcr = false

  logOcr('PDF processing started', { file: sourceFile, pages: pdf.numPages })

  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
    const page = await pdf.getPage(pageNum)
    const textContent = await page.getTextContent()
    const pageText = (textContent.items as PdfTextItem[])
      .map((item) => item.str)
      .join(' ')
      .trim()

    textPages.push(pageText)

    const needsOcr = pageText.replace(/\s+/g, '').length < 40
    if (needsOcr) {
      usedOcr = true
      const viewport = page.getViewport({ scale: 2 })
      const canvas = document.createElement('canvas')
      canvas.width = viewport.width
      canvas.height = viewport.height
      const ctx = canvas.getContext('2d')
      if (ctx) {
        await page.render({ canvasContext: ctx, viewport, canvas }).promise
        const ocr = await ocrCanvas(canvas, sourceFile, pageNum)
        ocrPages.push(ocr)
        textPages[pageNum - 1] = `${pageText}\n${ocr.text}`.trim()
      }
    }

    logOcr('PDF page processed', {
      file: sourceFile,
      page: pageNum,
      textChars: pageText.length,
      ocr: needsOcr,
    })
  }

  const combinedText = textPages.join('\n\n')
  return { textPages, ocrPages, combinedText, usedOcr }
}
