export function stripScore(text: string): string {
  return text
    .replace(/\s*\(\s*score[^)]*\/\s*100[^)]*\)/gi, '')
    .replace(/score(\s+(final|composite|global))?\s*:?\s*[\d.,]+\s*\/\s*100(\s*\([^)]*\))?/gi, '')
    .replace(/\s*[\d]+(?:[.,]\d+)?\s*\/\s*100\b/g, '')
    .replace(/\s*[—–-]\s*(?=[—–-]|$)/g, '')
    .replace(/^\s*[—–-]\s*/, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([.,;:])/g, '$1')
    .trim()
}

export function hasText(text: string | undefined | null): boolean {
  return !!text && /[\p{L}\d]/u.test(text)
}
