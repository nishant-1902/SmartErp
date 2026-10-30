import Modal from 'react-bootstrap/Modal'

/**
 * Shared React-Bootstrap modal shell with a consistent title and footer.
 *
 * @param {{show: boolean, onHide: () => void, title: string, children: React.ReactNode, footer?: React.ReactNode, size?: 'sm' | 'lg' | 'xl'}} props
 */
export default function ModalWrapper({
  show,
  onHide,
  title,
  children,
  footer,
  size,
}) {
  return (
    <Modal centered onHide={onHide} show={show} size={size}>
      <Modal.Header closeButton>
        <Modal.Title>{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>{children}</Modal.Body>
      {footer && <Modal.Footer>{footer}</Modal.Footer>}
    </Modal>
  )
}
