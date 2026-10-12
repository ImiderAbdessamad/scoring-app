export type WorkspaceEntry = {
  name: string
  blob: Blob
  url?: string
}

function generateWorkspaceId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  if (
    typeof crypto !== "undefined" &&
    typeof crypto.getRandomValues === "function"
  ) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);

    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    const hex = Array.from(
      bytes,
      (byte) => byte.toString(16).padStart(2, "0")
    );

    return [
      hex.slice(0, 4).join(""),
      hex.slice(4, 6).join(""),
      hex.slice(6, 8).join(""),
      hex.slice(8, 10).join(""),
      hex.slice(10, 16).join(""),
    ].join("-");
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}


export class ExtractionWorkspace {
  readonly id: string
  private entries = new Map<string, WorkspaceEntry>()

  constructor(id = generateWorkspaceId()) {
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
