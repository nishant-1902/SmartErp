import { useContext } from 'react'
import { ToastContext } from '../context/toastContext.js'

/**
 * Returns toast actions from the nearest ToastProvider.
 *
 * @returns {{showToast: (message: string, variant?: string, title?: string) => number, dismissToast: (id: number) => void}}
 */
export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider.')
  }
  return context
}
