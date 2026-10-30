import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AuditLogs from './AuditLogs.jsx'

const { listAuditLogsMock } = vi.hoisted(() => ({
  listAuditLogsMock: vi.fn(),
}))

vi.mock('../services/auditService.js', () => ({
  listAuditLogs: listAuditLogsMock,
}))

beforeEach(() => {
  listAuditLogsMock.mockResolvedValue({
    items: [{
      id: 'event-1',
      actor_id: '0123456789abcdef01234567',
      action: 'user_created',
      entity_type: 'user',
      entity_id: '89abcdef0123456701234567',
      outcome: 'success',
      created_at: '2026-10-30T10:00:00Z',
      ip: '127.0.0.1',
    }],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AuditLogs page', () => {
  it('loads records and applies user, action, and date filters', async () => {
    render(<AuditLogs />)
    expect(await screen.findByText('user_created')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('User ID'), {
      target: { value: '0123456789abcdef01234567' },
    })
    fireEvent.change(screen.getByLabelText('Action'), {
      target: { value: 'user_created' },
    })
    fireEvent.change(screen.getByLabelText('From'), {
      target: { value: '2026-10-01' },
    })
    fireEvent.change(screen.getByLabelText('To'), {
      target: { value: '2026-10-30' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() =>
      expect(listAuditLogsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          user: '0123456789abcdef01234567',
          action: 'user_created',
          start_date: '2026-10-01',
          end_date: '2026-10-30',
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
  })

  it('does not request audit data when the user ID filter is malformed', async () => {
    render(<AuditLogs />)
    await screen.findByText('user_created')
    listAuditLogsMock.mockClear()
    fireEvent.change(screen.getByLabelText('User ID'), {
      target: { value: 'not-an-object-id' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(await screen.findByText(/valid 24-character user ID/)).toBeInTheDocument()
    expect(listAuditLogsMock).not.toHaveBeenCalled()
  })
})
