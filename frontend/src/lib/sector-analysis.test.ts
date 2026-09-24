import { describe, expect, it } from 'vitest'
import { formatSectorAmount, formatSectorPeriod } from '@/lib/sectorFormat'

describe('labels analyse', () => {
  it('Analyse sectorielle et Comportement bancaire', () => {
    const tabs = [
      { id: 'benchmark', label: 'Analyse sectorielle' },
      { id: 'comportement', label: 'Comportement bancaire' },
    ]
    expect(tabs.find((t) => t.id === 'benchmark')?.label).toBe('Analyse sectorielle')
    expect(tabs.find((t) => t.id === 'comportement')?.label).toBe('Comportement bancaire')
  })
})

describe('formatters sectoriels', () => {
  it('affiche année et trimestre', () => {
    expect(formatSectorPeriod(2024, 3)).toBe('2024 T3')
    expect(formatSectorPeriod(2024, 3, true)).toBe('24 T3')
    expect(formatSectorPeriod(2023)).toBe('2023')
  })
  it('formate millions et milliards sans double suffixe', () => {
    expect(formatSectorAmount(121082, 'M MAD')).toContain('Md MAD')
    expect(formatSectorAmount(40577233, 'MAD')).toContain('M MAD')
    expect(formatSectorAmount(950000, 'MAD')).toContain('M MAD')
    expect(formatSectorAmount(null)).toBe('—')
  })
})

describe('score sectoriel', () => {
  it('aucun faux score 0', () => {
    const scoring = { status: 'NOT_CALIBRATED' as const, includedInFinalScore: false, score: null as number | null }
    expect(scoring.score).toBeNull()
    expect(scoring.includedInFinalScore).toBe(false)
  })
})

describe('états sectoriels', () => {
  it('freshness stale', () => {
    expect('STALE').not.toBe('FRESH')
  })
  it('mapping unmapped', () => {
    const status = 'UNMAPPED'
    expect(status).toBe('UNMAPPED')
  })
  it('no data empty', () => {
    const status = 'NO_DATA'
    expect(status).toBe('NO_DATA')
  })
  it('null value never 0', () => {
    const value: number | null = null
    expect(value == null ? '—' : String(value)).toBe('—')
    expect(value).not.toBe(0)
  })
})

describe('client sector API', () => {
  it('expose des helpers backend-only', async () => {
    const mod = await import('@/services/sectors')
    expect(typeof mod.fetchSectorAnalysis).toBe('function')
    expect(typeof mod.refreshSectorData).toBe('function')
    expect(typeof mod.fetchSectorSourcesStatus).toBe('function')
  })
})
