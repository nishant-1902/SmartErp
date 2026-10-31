import { describe, expect, it } from 'vitest'
import { formatMoney } from './formatMoney.js'

describe('formatMoney', () => {
  it('formats decimal strings without floating point conversion', () => {
    expect(formatMoney('9007199254740993.25', 'USD', 'en-US')).toBe(
      '$9,007,199,254,740,993.25',
    )
    expect(formatMoney('1234567.5', 'INR', 'en-IN')).toContain('12,34,567.50')
  })

  it('formats negative and zero values', () => {
    expect(formatMoney('-2.50', 'USD', 'en-US')).toBe('-$2.50')
    expect(formatMoney('0', 'USD', 'en-US')).toBe('$0.00')
  })

  it('rejects invalid monetary values rather than hiding them', () => {
    expect(() => formatMoney(1.2)).toThrow(TypeError)
    expect(() => formatMoney('1.234')).toThrow(TypeError)
  })
})
