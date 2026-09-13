import { formatDateShort } from '@/lib/format'
import type { Dossier, DossierStatus } from '@/types/dossier'
import { getMockDossiers as seedDossiers } from '@/services/mocks/data'

let dossiers: Dossier[] = seedDossiers()
const listeners = new Set<() => void>()

export function getDossierStore(): Dossier[] {
  return dossiers
}

export function subscribeDossierStore(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function notify() {
  listeners.forEach((l) => l())
}

export function notifyDossierStore() {
  notify()
}

export function prependDossier(dossier: Dossier): void {
  dossiers = [dossier, ...dossiers.filter((d) => d.id !== dossier.id)]
  notify()
}

export function updateDossierStatus(id: string, status: DossierStatus): Dossier | null {
  const current = dossiers.find((d) => d.id === id)
  if (!current) return null
  const updated: Dossier = {
    ...current,
    status,
    decisionDate: status === 'pending' ? undefined : formatDateShort(),
  }
  dossiers = dossiers.map((d) => (d.id === id ? updated : d))
  notify()
  return updated
}

export function resetDossierStore(): void {
  dossiers = seedDossiers()
  notify()
}
