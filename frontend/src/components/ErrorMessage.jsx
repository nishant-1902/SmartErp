import Alert from 'react-bootstrap/Alert'

/**
 * Displays a visible, accessible error message using a Bootstrap alert.
 *
 * @param {{message: string, title?: string, onClose?: () => void}} props
 */
export default function ErrorMessage({ message, title, onClose }) {
  if (!message) return null

  return (
    <Alert
      className="mb-3"
      dismissible={Boolean(onClose)}
      onClose={onClose}
      role="alert"
      variant="danger"
    >
      {title && <Alert.Heading className="h6">{title}</Alert.Heading>}
      {message}
    </Alert>
  )
}
