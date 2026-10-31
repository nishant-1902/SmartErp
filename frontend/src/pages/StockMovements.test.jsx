import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { listStockMovements } from '../services/productService.js'
import StockMovements from './StockMovements.jsx'

vi.mock('../services/productService.js', () => ({
  listStockMovements: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  listStockMovements.mockResolvedValue({
    items: [],
    meta: { page: 1, page_size: 20, total: 0, total_pages: 0 },
  })
})

describe('StockMovements page', () => {
  it('applies ObjectId, type, and inclusive date filters to the API query', async () => {
    render(<StockMovements />)
    await waitFor(() => expect(listStockMovements).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Filter movements by product ID'), {
      target: { value: '0123456789abcdef01234567' },
    })
    fireEvent.change(screen.getByLabelText('Filter movements by user ID'), {
      target: { value: 'fedcba9876543210fedcba98' },
    })
    fireEvent.change(screen.getByLabelText('Start date'), {
      target: { value: '2026-01-02' },
    })
    fireEvent.change(screen.getByLabelText('End date'), {
      target: { value: '2026-01-08' },
    })
    fireEvent.change(screen.getByLabelText('Filter movements by type'), {
      target: { value: 'adjustment' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply ID and date filters' }))

    await waitFor(() => {
      expect(listStockMovements).toHaveBeenLastCalledWith(
        expect.objectContaining({
          product: '0123456789abcdef01234567',
          user: 'fedcba9876543210fedcba98',
          type: 'adjustment',
          start_date: '2026-01-02T00:00:00Z',
          end_date: '2026-01-08T23:59:59.999Z',
        }),
        expect.any(Object),
      )
    })
  })

  it('rejects malformed product and user IDs before requesting', async () => {
    render(<StockMovements />)
    await waitFor(() => expect(listStockMovements).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText('Filter movements by product ID'), {
      target: { value: 'not-an-object-id' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply ID and date filters' }))

    expect(
      await screen.findByText(
        'Product ID must be a 24-character hexadecimal ObjectId.',
      ),
    ).toBeInTheDocument()
    expect(listStockMovements).toHaveBeenCalledTimes(1)
  })
})
