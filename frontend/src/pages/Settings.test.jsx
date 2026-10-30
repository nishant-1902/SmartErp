import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Settings from './Settings.jsx'
import Profile from './Profile.jsx'

const { logoutLocallyMock, changePasswordMock, showToastMock } = vi.hoisted(() => ({
  logoutLocallyMock: vi.fn(),
  changePasswordMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'alex@example.com',
      full_name: 'Alex Example',
      role: 'super_admin',
      is_active: true,
    },
    logoutLocally: logoutLocallyMock,
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/authService.js', () => ({
  changePassword: changePasswordMock,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Settings page', () => {
  it('shows the signed-in user on the Profile page', () => {
    render(
      <MemoryRouter>
        <Profile />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
    expect(screen.getByText('Alex Example')).toBeInTheDocument()
    expect(screen.getByText('alex@example.com')).toBeInTheDocument()
  })

  it('displays the current user and logs out locally after password change', async () => {
    changePasswordMock.mockResolvedValue({ message: 'Password changed successfully.' })
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    )

    expect(screen.getByText('alex@example.com')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Current password'), {
      target: { value: 'ExistingSafePass887!' },
    })
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'UniqueNewPassword991!' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'UniqueNewPassword991!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    await waitFor(() => {
      expect(changePasswordMock).toHaveBeenCalledWith({
        old_password: 'ExistingSafePass887!',
        new_password: 'UniqueNewPassword991!',
        confirm_password: 'UniqueNewPassword991!',
      })
      expect(logoutLocallyMock).toHaveBeenCalledWith({
        successMessage: 'Your password was changed. Please sign in again.',
      })
    })
  })

  it('rejects a password that is shorter than the backend minimum', async () => {
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText('Current password'), {
      target: { value: 'ExistingSafePass887!' },
    })
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'short' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'short' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Password must contain at least 10 characters.'))
      .toBeInTheDocument()
    expect(changePasswordMock).not.toHaveBeenCalled()
  })

  it('rejects a new password that matches the current email', async () => {
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText('Current password'), {
      target: { value: 'ExistingSafePass887!' },
    })
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'alex@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'alex@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Password must not be the same as the email address.'))
      .toBeInTheDocument()
    expect(changePasswordMock).not.toHaveBeenCalled()
  })

  it('rejects a commonly used password before sending the request', async () => {
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText('Current password'), {
      target: { value: 'ExistingSafePass887!' },
    })
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'password123' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Choose a password that is not commonly used.'))
      .toBeInTheDocument()
    expect(changePasswordMock).not.toHaveBeenCalled()
  })
})
