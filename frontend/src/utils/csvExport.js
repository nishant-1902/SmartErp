function safeCell(value) {
  const stringValue =
    value === null || value === undefined
      ? ''
      : typeof value === 'object'
        ? JSON.stringify(value)
        : String(value)
  let firstVisibleCharacter = 0
  while (
    firstVisibleCharacter < stringValue.length &&
    stringValue.charCodeAt(firstVisibleCharacter) <= 0x20
  ) {
    firstVisibleCharacter += 1
  }
  const escapedFormula = ['=', '+', '-', '@'].includes(
    stringValue[firstVisibleCharacter],
  )
    ? `'${stringValue}`
    : stringValue
  return `"${escapedFormula.replaceAll('"', '""')}"`
}

/**
 * Create UTF-8 CSV and neutralize spreadsheet formula prefixes in every cell.
 *
 * @param {Array<{key: string, label: string, exportValue?: (row: object) => unknown}>} columns
 * @param {object[]} rows
 * @returns {string}
 */
export function createSafeCsv(columns, rows) {
  const records = [
    columns.map((column) => safeCell(column.label)).join(','),
    ...rows.map((row) =>
      columns
        .map((column) =>
          safeCell(
            column.exportValue ? column.exportValue(row) : row[column.key],
          ),
        )
        .join(','),
    ),
  ]
  return `\uFEFF${records.join('\r\n')}`
}

/**
 * Download the current report rows using a temporary browser object URL.
 *
 * @param {Array<{key: string, label: string, exportValue?: (row: object) => unknown}>} columns
 * @param {object[]} rows
 * @param {string} reportName
 * @returns {void}
 */
export function downloadCsv(columns, rows, reportName) {
  const blob = new Blob([createSafeCsv(columns, rows)], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `smarterp-${reportName}-report.csv`
  document.body.append(link)
  try {
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(url)
  }
}
