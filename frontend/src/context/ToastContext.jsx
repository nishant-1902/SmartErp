import { useCallback, useMemo, useRef, useState } from 'react'
import Toast from 'react-bootstrap/Toast'
import ToastContainer from 'react-bootstrap/ToastContainer'
import { ToastContext } from './toastContext.js'

/**
 * Provides app-wide toast notifications and renders them in an accessible stack.
 *
 * @param {{children: React.ReactNode}} props
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(0)

  const dismissToast = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback(
    (message, variant = 'success', title) => {
      const id = nextId.current++
      setToasts((current) => [
        ...current,
        { id, message, variant, title: title ?? variant },
      ])
      return id
    },
    [],
  )

  const value = useMemo(() => ({ showToast, dismissToast }), [dismissToast, showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer
        aria-live="polite"
        className="toast-stack p-3"
        position="bottom-end"
      >
        {toasts.map((toast) => (
          <Toast
            bg={toast.variant}
            delay={5000}
            key={toast.id}
            onClose={() => dismissToast(toast.id)}
            role={toast.variant === 'danger' ? 'alert' : 'status'}
            show
            autohide
          >
            <Toast.Header closeButton>
              <strong className="me-auto text-capitalize">{toast.title}</strong>
            </Toast.Header>
            <Toast.Body
              className={
                toast.variant === 'danger' || toast.variant === 'success'
                  ? 'text-white'
                  : ''
              }
            >
              {toast.message}
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </ToastContext.Provider>
  )
}
