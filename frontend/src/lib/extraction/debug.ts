const DEBUG = import.meta.env.DEV

function fmt(details: Record<string, unknown>): string {
  return Object.entries(details)
    .map(([k, v]) => {
      if (v === undefined || v === null) return `${k}=—`
      if (typeof v === 'string') return `${k}="${v}"`
      if (typeof v === 'object') return `${k}=${JSON.stringify(v)}`
      return `${k}=${v}`
    })
    .join(' | ')
}

export function logExtraction(section: string, details: Record<string, unknown> = {}) {
  if (!DEBUG) return
  console.log(`%c[${section}]%c ${fmt(details)}`, 'color:#c2410c;font-weight:bold', 'color:inherit')
}

export function logOcr(message: string, details?: Record<string, unknown>) {
  logExtraction('OCR', { message, ...details })
}

export function logFieldDetection(details: Record<string, unknown>) {
  logExtraction('FIELD DETECTION', details)
}

export function logDecision(details: Record<string, unknown>) {
  logExtraction('DECISION', details)
}

export function logPipeline(message: string, details?: Record<string, unknown>) {
  logExtraction('PIPELINE', { message, ...details })
}

export function withSilentTesseractConsole<T>(fn: () => Promise<T>): Promise<T> {
  const originalError = console.error
  const originalWarn = console.warn
  const mute = (...args: unknown[]) => {
    const msg = String(args[0] ?? '')
    if (
      /Estimating resolution|Detected \d+ diacritics|Warning:|Error in pix|Image too large/i.test(
        msg,
      )
    ) {
      return
    }
    originalError.apply(console, args as [])
  }
  console.error = mute as typeof console.error
  console.warn = mute as typeof console.warn
  return fn().finally(() => {
    console.error = originalError
    console.warn = originalWarn
  })
}
