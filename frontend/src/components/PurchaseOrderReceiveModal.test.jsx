import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../context/ToastContext.jsx'
import PurchaseOrderReceiveModal from './PurchaseOrderReceiveModal.jsx'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const purchaseOrder = {
  id: 'po-1',
  po_number: 'PO-2026-000001',
  items: [
    {
      product_id: 'product-1',
      name: 'Desk',
      sku: 'DESK-1',
      quantity_ordered: 5,
      quantity_received: 2,
    },
  ],
}

describe('PurchaseOrderReceiveModal', () => {
  it('limits receipt quantities and sends a stable key when retrying the same attempt', async () => {
    const onReceive = vi.fn().mockRejectedValueOnce({
      response: {
        status: 503,
        data: { error: { message: 'Temporary failure.', details: {} } },
      },
    }).mockResolvedValueOnce(undefined)
    const randomUUID = vi.fn().mockReturnValue('receipt-attempt-uuid')
    vi.stubGlobal('crypto', { randomUUID })
    render(
      <ToastProvider>
        <PurchaseOrderReceiveModal
          onHide={vi.fn()}
          onReceive={onReceive}
          purchaseOrder={purchaseOrder}
          show
        />
      </ToastProvider>,
    )

    const quantity = screen.getByLabelText('Receive quantity for Desk')
    expect(quantity).toHaveAttribute('max', '3')
    fireEvent.change(quantity, { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record receipt' }))

    await waitFor(() =>
      expect(screen.getAllByText('Temporary failure.').length).toBeGreaterThan(0),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Record receipt' }))

    await waitFor(() => expect(onReceive).toHaveBeenCalledTimes(2))
    expect(randomUUID).toHaveBeenCalledOnce()
    expect(onReceive).toHaveBeenNthCalledWith(
      1,
      { items: [{ product_id: 'product-1', quantity_received: 2 }] },
      'receipt-attempt-uuid',
    )
    expect(onReceive).toHaveBeenNthCalledWith(
      2,
      { items: [{ product_id: 'product-1', quantity_received: 2 }] },
      'receipt-attempt-uuid',
    )
  })

  it('rejects empty receipts before calling the API', async () => {
    const onReceive = vi.fn()
    render(
      <ToastProvider>
        <PurchaseOrderReceiveModal
          onHide={vi.fn()}
          onReceive={onReceive}
          purchaseOrder={purchaseOrder}
          show
        />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Record receipt' }))

    expect(await screen.findByText('Enter a positive quantity for at least one product.')).toBeInTheDocument()
    expect(onReceive).not.toHaveBeenCalled()
  })
})
