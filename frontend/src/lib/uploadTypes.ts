export const UPLOAD_ACCEPT = '.pdf,.png,.jpg,.jpeg'

const ALLOWED_EXT = ['.pdf', '.png', '.jpg', '.jpeg'] as const

const ALLOWED_MIME = new Set([
  'application/pdf',
  'application/x-pdf',
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/pjpeg',
  'application/octet-stream',
])

export function isAllowedUpload(file: File): boolean {
  const name = file.name.toLowerCase()
  if (name.endsWith('.webp')) return false
  if (ALLOWED_EXT.some((ext) => name.endsWith(ext))) return true
  const mime = (file.type || '').split(';')[0].trim().toLowerCase()
  if (mime === 'image/webp') return false
  return ALLOWED_MIME.has(mime)
}

export function uploadRejectMessage(file: File): string {
  return `Format non autorisé : ${file.name}. Utilisez PDF, PNG ou JPG.`
}
