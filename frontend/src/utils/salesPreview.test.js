import { describe, expect, it } from 'vitest'
import { calculateSalesPreview } from './salesPreview.js'

describe('calculateSalesPreview', () => {
  it('calculates discount and tax per line with half-up rounding', () => {
    expect(
      calculateSalesPreview([
        {
          quantity: 3,
          unit_price: '10.00',
          discount_percent: '10.00',
          tax_percent: '8.00',
        },
        {
          quantity: 2,
          unit_price: '19.99',
          discount_percent: '12.50',
          tax_percent: '5.00',
        },
      ]),
    ).toEqual({
      subtotal: '69.98',
      discountTotal: '8.00',
      taxTotal: '3.91',
      grandTotal: '65.89',
    })
  })

  it('returns no preview for invalid prices, rates, or quantities', () => {
    expect(
      calculateSalesPreview([
        {
          quantity: 1.5,
          unit_price: '2.00',
          discount_percent: '0',
          tax_percent: '0',
        },
      ]),
    ).toBeNull()
    expect(
      calculateSalesPreview([
        {
          quantity: 1,
          unit_price: '2.001',
          discount_percent: '0',
          tax_percent: '0',
        },
      ]),
    ).toBeNull()
  })
})
