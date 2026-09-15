import { describe, expect, it } from 'vitest'

describe('score status display', () => {
  it('PARTIAL n’affiche pas de classe finale', () => {
    const scoring = { scoreStatus: 'PARTIAL' as const, finalScore: null as number | null, classe: null as string | null, partialScore: 83.24 }
    expect(scoring.finalScore).toBeNull()
    expect(scoring.classe).toBeNull()
    expect(scoring.partialScore).toBe(83.24)
  })
})

describe('ApiError 409', () => {
  it('conserve les blockers', () => {
    const payload = { detail: { code: 'DECISION_NOT_ELIGIBLE', blocking_reasons: ['BAM_NOT_CHECKED'] } }
    expect(payload.detail.code).toBe('DECISION_NOT_ELIGIBLE')
    expect(payload.detail.blocking_reasons).toContain('BAM_NOT_CHECKED')
  })
})
