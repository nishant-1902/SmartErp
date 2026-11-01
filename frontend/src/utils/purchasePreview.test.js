import { describe, expect, it } from 'vitest'
import { calculatePurchasePreview } from './purchasePreview.js'

describe('calculatePurchasePreview', () => {
  it('calculates tax and totals with integer minor units', () => {
    expect(
      calculatePurchasePreview(
        [
          { quantity_ordered: 3, unit_cost: '12.34' },
          { quantity_ordered: 2, unit_cost: '0.50' },
        ],
        '7.50',
      ),
    ).toEqual({
      subtotal: '38.02',
      taxTotal: '2.85',
      grandTotal: '40.87',
    })
  })

  it('rounds tax to the nearest cent and rejects invalid values', () => {
    expect(
      calculatePurchasePreview(
        [{ quantity_ordered: 1, unit_cost: '0.10' }],
        '5.00',
      ).taxTotal,
    ).toBe('0.01')
    expect(
      calculatePurchasePreview(
        [{ quantity_ordered: 1.5, unit_cost: '2.00' }],
        '0.00',
      ),
    ).toBeNull()
    expect(
      calculatePurchasePreview(
        [{ quantity_ordered: 1, unit_cost: '2.001' }],
        '0.00',
      ),
    ).toBeNull()
  })
})
