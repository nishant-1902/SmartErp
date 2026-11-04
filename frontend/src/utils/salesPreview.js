function parseCents(value) {
  if (typeof value !== 'string' || !/^\d{1,16}(?:\.\d{1,2})?$/.test(value)) {
    return null
  }
  const [whole, fraction = ''] = value.split('.')
  return BigInt(whole) * 100n + BigInt(`${fraction}00`.slice(0, 2))
}

function parsePercentBasisPoints(value) {
  if (typeof value !== 'string' || !/^\d{1,3}(?:\.\d{1,2})?$/.test(value)) {
    return null
  }
  const [whole, fraction = ''] = value.split('.')
  return BigInt(whole) * 100n + BigInt(`${fraction}00`.slice(0, 2))
}

function roundRatio(numerator, denominator) {
  return (numerator + denominator / 2n) / denominator
}

function fromCents(cents) {
  return `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`
}

/**
 * Calculate a display-only estimate with integer cents and per-line rounding.
 *
 * @param {Array<{quantity: string | number, unit_price: string, discount_percent: string, tax_percent: string}>} items
 * @returns {{subtotal: string, discountTotal: string, taxTotal: string, grandTotal: string} | null}
 */
export function calculateSalesPreview(items) {
  let subtotalCents = 0n
  let discountCents = 0n
  let taxCents = 0n
  let totalCents = 0n

  for (const item of items) {
    const priceCents = parseCents(item.unit_price)
    const discountRate = parsePercentBasisPoints(item.discount_percent)
    const taxRate = parsePercentBasisPoints(item.tax_percent)
    const quantity = Number(item.quantity)
    if (
      priceCents === null ||
      discountRate === null ||
      taxRate === null ||
      discountRate > 10000n ||
      taxRate > 10000n ||
      !Number.isSafeInteger(quantity) ||
      quantity < 1
    ) {
      return null
    }

    const lineSubtotal = priceCents * BigInt(quantity)
    const discounted = roundRatio(
      lineSubtotal * (10000n - discountRate),
      10000n,
    )
    const lineDiscount = lineSubtotal - discounted
    const lineTax = roundRatio(discounted * taxRate, 10000n)
    subtotalCents += lineSubtotal
    discountCents += lineDiscount
    taxCents += lineTax
    totalCents += discounted + lineTax
  }

  return {
    subtotal: fromCents(subtotalCents),
    discountTotal: fromCents(discountCents),
    taxTotal: fromCents(taxCents),
    grandTotal: fromCents(totalCents),
  }
}
