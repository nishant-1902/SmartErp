import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../context/ToastContext.jsx'
import StockAdjustmentModal from './StockAdjustmentModal.jsx'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('StockAdjustmentModal', () => {
  it('sends a fresh UUID key and prevents duplicate submission while pending', async () => {
    let finishSubmission
    const onSubmit = vi.fn(
      () =>
        new Promise((resolve) => {
          finishSubmission = resolve
        }),
    )
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue(
      'b71e13fc-c064-42c4-ad88-3fce79d2c618',
    )
    render(
      <ToastProvider>
        <StockAdjustmentModal
          onHide={vi.fn()}
          onSubmit={onSubmit}
          product={{
            id: 'product-1',
            name: 'Desk',
            quantity_on_hand: 8,
            reserved_quantity: 3,
          }}
          show
        />
      </ToastProvider>,
    )

    fireEvent.change(screen.getByLabelText('Quantity change'), {
      target: { value: '2' },
    })
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Stock count' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply adjustment' }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        {
          product_id: 'product-1',
          quantity_change: 2,
          reason: 'Stock count',
        },
        'b71e13fc-c064-42c4-ad88-3fce79d2c618',
      )
    })
    expect(
      screen.getByRole('button', { name: 'Applying…' }),
    ).toBeDisabled()

    finishSubmission()
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'Applying…' }),
      ).not.toBeInTheDocument()
    })
  })

  it('rejects zero and non-integer quantity changes without calling the API', () => {
    const onSubmit = vi.fn()
    render(
      <ToastProvider>
        <StockAdjustmentModal
          onHide={vi.fn()}
          onSubmit={onSubmit}
          product={{
            id: 'product-1',
            name: 'Desk',
            quantity_on_hand: 8,
            reserved_quantity: 3,
          }}
          show
        />
      </ToastProvider>,
    )
    fireEvent.change(screen.getByLabelText('Quantity change'), {
      target: { value: '0' },
    })
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Stock count' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply adjustment' }))

    expect(screen.getByText('Enter a non-zero whole number.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
