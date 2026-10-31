import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../context/ToastContext.jsx'
import ProductFormModal from './ProductFormModal.jsx'

afterEach(cleanup)

describe('ProductFormModal', () => {
  it('does not send SKU or stock values when editing a product', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <ToastProvider>
        <ProductFormModal
          onHide={vi.fn()}
          onSave={onSave}
          product={{
            id: 'product-1',
            sku: 'DESK-1',
            name: 'Desk',
            description: null,
            category: 'Furniture',
            unit: 'each',
            cost_price: '20.00',
            selling_price: '35.00',
            quantity_on_hand: 8,
            reserved_quantity: 2,
            min_stock_level: 3,
            is_active: true,
          }}
          show
        />
      </ToastProvider>,
    )

    expect(screen.getByLabelText('SKU')).toHaveAttribute('readonly')
    expect(screen.queryByLabelText(/quantity on hand/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    const values = onSave.mock.calls[0][0]
    expect(values).not.toHaveProperty('sku')
    expect(values).not.toHaveProperty('quantity_on_hand')
    expect(values).not.toHaveProperty('reserved_quantity')
    expect(values).toMatchObject({
      name: 'Desk',
      cost_price: '20.00',
      selling_price: '35.00',
    })
  })

  it('normalizes the SKU to uppercase when creating a product', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <ToastProvider>
        <ProductFormModal onHide={vi.fn()} onSave={onSave} show />
      </ToastProvider>,
    )

    fireEvent.change(screen.getByLabelText('SKU'), { target: { value: ' desk-1 ' } })
    fireEvent.change(screen.getByLabelText('Product name'), {
      target: { value: 'Desk' },
    })
    fireEvent.change(screen.getByLabelText('Category'), {
      target: { value: 'Furniture' },
    })
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'each' } })
    fireEvent.change(screen.getByLabelText('Cost price'), {
      target: { value: '20.00' },
    })
    fireEvent.change(screen.getByLabelText('Selling price'), {
      target: { value: '35.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create product' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    expect(onSave.mock.calls[0][0].sku).toBe('DESK-1')
  })
})
