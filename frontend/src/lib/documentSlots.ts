import type { StoredFileMeta } from '@/types/dossier'

export const MAX_DOSSIER_DOCUMENTS = 20

export type DocumentSlot = {
  id: string
  label: string
}

export function filesToDocumentItems(files: StoredFileMeta[]): StoredFileMeta[] {
  return [...files]
}
