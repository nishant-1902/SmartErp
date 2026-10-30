import Button from 'react-bootstrap/Button'
import ModalWrapper from './ModalWrapper.jsx'

/**
 * Presents a confirmation prompt and prevents duplicate submission while busy.
 *
 * @param {{show: boolean, title?: string, message: React.ReactNode, confirmLabel?: string, confirmVariant?: string, busy?: boolean, onConfirm: () => void, onCancel: () => void}} props
 */
export default function ConfirmDialog({
  show,
  title = 'Please confirm',
  message,
  confirmLabel = 'Confirm',
  confirmVariant = 'danger',
  busy = false,
  onConfirm,
  onCancel,
}) {
  const footer = (
    <>
      <Button disabled={busy} onClick={onCancel} variant="outline-secondary">
        Cancel
      </Button>
      <Button disabled={busy} onClick={onConfirm} variant={confirmVariant}>
        {busy ? 'Please wait…' : confirmLabel}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onCancel}
      show={show}
      title={title}
    >
      {message}
    </ModalWrapper>
  )
}
