import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ForgotPassword from './ForgotPassword.jsx'
import ResetPassword from './ResetPassword.jsx'

const { requestPasswordResetMock, confirmPasswordResetMock } = vi.hoisted(() => ({
  requestPasswordResetMock: vi.fn(),
  confirmPasswordResetMock: vi.fn(),
}))

vi.mock('../services/authService.js', () => ({
  requestPasswordReset: requestPasswordResetMock,
  confirmPasswordReset: confirmPasswordResetMock,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function NavigationResult() {
  const location = useLocation()
  return <div>{location.state?.successMessage}</div>
}

describe('password-reset pages', () => {
  it('requests a password reset and shows a non-enumerating success message', async () => {
    requestPasswordResetMock.mockResolvedValue({
      message: 'If an account matches this email, a password reset link has been generated.',
    })
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'alex@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Request reset link' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'If an account matches this email, a password reset link has been generated.',
    )
    expect(requestPasswordResetMock).toHaveBeenCalledWith('alex@example.com')
  })

  it('reads the email and token from the URL and sends the reset confirmation', async () => {
    confirmPasswordResetMock.mockResolvedValue({ message: 'Password reset complete.' })
    render(
      <MemoryRouter
        initialEntries={[
          '/reset-password?email=alex%40example.com&token=one-time-token',
        ]}
      >
        <Routes>
          <Route element={<ResetPassword />} path="/reset-password" />
          <Route element={<NavigationResult />} path="/login" />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'DistinctResetPassword991!' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'DistinctResetPassword991!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    await waitFor(() =>
      expect(confirmPasswordResetMock).toHaveBeenCalledWith({
        email: 'alex@example.com',
        token: 'one-time-token',
        password: 'DistinctResetPassword991!',
        confirm_password: 'DistinctResetPassword991!',
      }),
    )
    expect(await screen.findByText(
      'Your password was reset. Sign in with your new password.',
    )).toBeInTheDocument()
  })
})
