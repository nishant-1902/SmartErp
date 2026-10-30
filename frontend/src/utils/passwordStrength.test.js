import { describe, expect, it } from 'vitest'
import { isCommonPassword } from './passwordStrength.js'

describe('password strength helpers', () => {
  it('identifies frequent weak passwords case-insensitively', () => {
    expect(isCommonPassword('Password123')).toBe(true)
    expect(isCommonPassword('A-Unique-Phrase-2026')).toBe(false)
  })
})
