function collectMessages(value) {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(collectMessages)
  if (value && typeof value === 'object') {
    return Object.values(value).flatMap(collectMessages)
  }
  return []
}

/**
 * Extract the standard backend error envelope and HTTP status.
 *
 * @param {unknown} error
 * @returns {{status: number | null, code: string, message: string, details: object}}
 */
export function getApiError(error) {
  const body = error?.response?.data
  const status = error?.response?.status ?? null
  const envelope = body?.error ?? {}
  const statusMessage =
    status === 403
      ? 'You do not have permission to perform this action.'
      : status === 409
        ? 'This change conflicts with an existing record.'
        : status === 400
          ? 'Check the highlighted fields and try again.'
          : 'The request could not be completed. Please try again.'

  return {
    status,
    code: envelope.code ?? 'request_error',
    message: envelope.message ?? statusMessage,
    details: envelope.details ?? {},
  }
}

/**
 * Translate backend validation details into React Hook Form field errors.
 *
 * @param {object} details
 * @param {(name: string, error: {type: string, message: string}) => void} setError
 * @returns {string[]} Messages not associated with a known form field.
 */
export function applyApiFieldErrors(details, setError) {
  const fieldNames = new Set([
    'employee_code',
    'first_name',
    'last_name',
    'email',
    'phone',
    'department_id',
    'designation',
    'joining_date',
    'status',
    'code',
    'name',
    'description',
    'manager_employee_id',
    'is_active',
    'full_name',
    'role',
    'employee_id',
    'password',
    'old_password',
    'new_password',
    'confirm_password',
    'token',
    'sku',
    'category',
    'unit',
    'cost_price',
    'selling_price',
    'min_stock_level',
    'quantity_change',
    'reason',
    'product_id',
  ])
  const remaining = []

  if (!details || typeof details !== 'object') {
    return collectMessages(details)
  }

  for (const [field, value] of Object.entries(details)) {
    const messages = collectMessages(value)
    if (fieldNames.has(field) && messages.length) {
      setError(field, { type: 'server', message: messages.join(' ') })
    } else {
      remaining.push(...messages)
    }
  }
  return remaining
}
