/**
 * Format a decimal string as currency without converting its amount to Number.
 *
 * @param {string} value
 * @param {string} currency
 * @param {string | undefined} locale
 * @returns {string}
 */
export function formatMoney(value, currency = 'INR', locale) {
  if (typeof value !== 'string') {
    throw new TypeError('Money values must be decimal strings.')
  }
  const match = value.trim().match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/)
  if (!match) {
    throw new TypeError('Money value must be a decimal string with at most two places.')
  }

  const [, sign, wholePart, fractionPart = ''] = match
  const whole = BigInt(`${sign}${wholePart}`)
  const currencyFormatter = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
  const wholeParts = currencyFormatter.formatToParts(whole)
  const lastIntegerIndex = wholeParts.reduce(
    (lastIndex, part, index) => (part.type === 'integer' ? index : lastIndex),
    -1,
  )
  if (lastIntegerIndex < 0) {
    throw new TypeError('Currency formatter did not return integer parts.')
  }

  const digitFormatter = new Intl.NumberFormat(locale, {
    useGrouping: false,
    maximumFractionDigits: 0,
  })
  const localizedDigits = Array.from({ length: 10 }, (_, digit) =>
    digitFormatter.format(digit),
  )
  const fraction = `${fractionPart}00`.slice(0, 2)
  const localizedFraction = [...fraction]
    .map((digit) => localizedDigits[Number(digit)])
    .join('')
  const decimalSeparator =
    new Intl.NumberFormat(locale, { minimumFractionDigits: 1 })
      .formatToParts(1.1)
      .find((part) => part.type === 'decimal')?.value ?? '.'

  const formattedParts = [...wholeParts]
  formattedParts.splice(lastIntegerIndex + 1, 0, {
    type: 'decimal',
    value: decimalSeparator,
  }, {
    type: 'fraction',
    value: localizedFraction,
  })
  return formattedParts.map((part) => part.value).join('')
}
