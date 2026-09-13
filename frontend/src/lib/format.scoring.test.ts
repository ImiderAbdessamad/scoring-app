import { describe, expect, it } from 'vitest'
import { classTone, formatMadCompact, formatMadExact, gradeOf } from '@/lib/format'
import { computeRiskDistribution } from '@/lib/dashboardKpis'
import type { Dossier } from '@/types/dossier'

describe('classTone', () => {
  it('maps backend class without using score thresholds', () => {
    expect(classTone('A+').letter).toBe('A+')
    expect(gradeOf(10, 'A+').letter).toBe('A+')
    expect(gradeOf(95).letter).toBe('—')
  })

  it('formats exact MAD amounts', () => {
    expect(formatMadExact(147741686.4)).toContain('147')
    expect(formatMadCompact(147741686.4)).toContain('M MAD')
  })
})

describe('risk vs urgency', () => {
  it('does not treat high urgency as credit risk', () => {
    const records: Dossier[] = [
      {
        id: '1',
        name: 'A',
        sector: 'Industrie',
        amount: 1_000_000,
        duration: 48,
        score: 82,
        status: 'review',
        analyst: 'Analyste',
        receivedDaysAgo: 1,
        urgency: 'haute',
        classe: 'A/B+',
        riskLevel: 'faible',
      },
    ]
    const { riskDist } = computeRiskDistribution(records)
    const high = riskDist.find((b) => b.tone === 'high')
    const low = riskDist.find((b) => b.tone === 'low')
    expect(high?.count).toBe(0)
    expect(low?.count).toBe(1)
  })
})
