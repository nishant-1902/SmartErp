import Form from 'react-bootstrap/Form'

/**
 * Accessible Bootstrap input that accepts React Hook Form registration props.
 *
 * @param {{id?: string, name: string, label: string, type?: string, registerProps?: object, error?: {message?: string}, hint?: string, [key: string]: any}} props
 */
export default function FormInput({
  id,
  name,
  label,
  type = 'text',
  registerProps = {},
  error,
  hint,
  ...inputProps
}) {
  const inputId = id ?? name
  const feedbackId = `${inputId}-feedback`
  const hintId = `${inputId}-hint`
  const describedBy = [
    hint ? hintId : null,
    error?.message ? feedbackId : null,
  ]
    .filter(Boolean)
    .join(' ') || undefined

  return (
    <Form.Group className="mb-3">
      <Form.Label htmlFor={inputId}>{label}</Form.Label>
      <Form.Control
        aria-describedby={describedBy}
        aria-invalid={Boolean(error)}
        autoComplete={inputProps.autoComplete}
        id={inputId}
        isInvalid={Boolean(error)}
        name={name}
        type={type}
        {...registerProps}
        {...inputProps}
      />
      {hint && (
        <Form.Text className="text-muted" id={hintId}>
          {hint}
        </Form.Text>
      )}
      {error?.message && (
        <Form.Control.Feedback id={feedbackId} type="invalid">
          {error.message}
        </Form.Control.Feedback>
      )}
    </Form.Group>
  )
}
