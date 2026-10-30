const commonPasswords = new Set([
  'password',
  'password1',
  'password123',
  'passw0rd',
  '123456789',
  '1234567890',
  'qwerty123',
  'letmein123',
  'welcome123',
  'admin123',
  'abc123',
  'iloveyou',
  'monkey123',
  'dragon123',
  'sunshine1',
  'football1',
  'princess1',
  'trustno1',
  'changeme1',
  'default123',
])

/**
 * Detect frequent weak passwords locally; the backend applies Django's full list.
 *
 * @param {string} password
 * @returns {boolean}
 */
export function isCommonPassword(password) {
  return commonPasswords.has(password.toLowerCase())
}
