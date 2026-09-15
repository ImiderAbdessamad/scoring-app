export function formatSectorAmount(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const u = (unit || '').toUpperCase()
  if (u.includes('M MAD') || u === 'M MAD') {
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Md MAD`
    }
    return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} M MAD`
  }
  const abs = Math.abs(value)
  if (abs >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Md MAD`
  }
  return `${(value / 1_000_000).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} M MAD`
}

export function formatSectorPeriod(
  year: number | null | undefined,
  quarter?: number | null,
  compact = false,
): string {
  if (year == null) return '—'
  const y = compact ? String(year).slice(2) : String(year)
  return quarter ? `${y} T${quarter}` : y
}

export function formatSignedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits).replace('.', ',')} %`
}
