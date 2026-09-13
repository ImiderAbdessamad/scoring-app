export type WorkspaceEntry = {
  name: string
  blob: Blob
  url?: string
}

export class ExtractionWorkspace {
  readonly id: string
  private entries = new Map<string, WorkspaceEntry>()

  constructor(id = crypto.randomUUID()) {
    this.id = id
  }

  add(name: string, blob: Blob): string {
    const key = `${this.entries.size}-${name}`
    const url = URL.createObjectURL(blob)
    this.entries.set(key, { name, blob, url })
    return url
  }

  get(name: string): Blob | undefined {
    for (const entry of this.entries.values()) {
      if (entry.name === name) return entry.blob
    }
    return undefined
  }

  cleanup(): void {
    for (const entry of this.entries.values()) {
      if (entry.url) URL.revokeObjectURL(entry.url)
    }
    this.entries.clear()
  }
}

export async function withExtractionWorkspace<T>(
  fn: (ws: ExtractionWorkspace) => Promise<T>,
): Promise<T> {
  const ws = new ExtractionWorkspace()
  try {
    return await fn(ws)
  } finally {
    ws.cleanup()
  }
}
