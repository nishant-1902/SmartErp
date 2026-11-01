function parseCents(value) {
  if (typeof value !== 'string' || !/^\d{1,16}(?:\.\d{1,2})?$/.test(value)) {
    return null
  }
  const [whole, fraction = ''] = value.split('.')
  return BigInt(whole) * 100n + BigInt(`${fraction}00`.slice(0, 2))
}

function fromCents(cents) {
  return `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`
}

/**
 * Calculate a display-only estimate using integer minor currency units.
 *
 * @param {Array<{quantity_ordered: string | number, unit_cost: string}>} items
 * @param {string} taxRate
 * @returns {{subtotal: string, taxTotal: string, grandTotal: string} | null}
 */
export function calculatePurchasePreview(items, taxRate) {
  const rateCents = parseCents(taxRate)
  if (rateCents === null || rateCents > 10000n) return null

  let subtotalCents = 0n
  for (const item of items) {
    const unitCostCents = parseCents(item.unit_cost)
    const quantity = Number(item.quantity_ordered)
    if (
      unitCostCents === null ||
      !Number.isSafeInteger(quantity) ||
      quantity < 1
    ) {
      return null
    }
    subtotalCents += unitCostCents * BigInt(quantity)
  }

  const taxTotalCents = (subtotalCents * rateCents + 5000n) / 10000n
  return {
    subtotal: fromCents(subtotalCents),
    taxTotal: fromCents(taxTotalCents),
    grandTotal: fromCents(subtotalCents + taxTotalCents),
  }
}
