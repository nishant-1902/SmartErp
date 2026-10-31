import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { ToastProvider } from '../context/ToastContext.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { adjustStock, listProducts } from '../services/productService.js'
import Inventory from './Inventory.jsx'

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../services/productService.js', () => ({
  adjustStock: vi.fn(),
  listProducts: vi.fn(),
}))

const product = {
  id: '0123456789abcdef01234567',
  sku: 'CHAIR-1',
  name: 'Office chair',
  category: 'Furniture',
  unit: 'each',
  quantity_on_hand: 8,
  reserved_quantity: 3,
  min_stock_level: 5,
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

beforeEach(() => {
  useAuth.mockReturnValue({
    hasPermission: (permission) => permission === 'stock:adjust',
  })
  listProducts.mockResolvedValue({
    items: [product],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  adjustStock.mockResolvedValue({})
})

describe('Inventory page', () => {
  it('highlights low available stock and submits an idempotent adjustment', async () => {
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue(
      'b71e13fc-c064-42c4-ad88-3fce79d2c618',
    )
    render(
      <BrowserRouter>
        <ToastProvider>
          <Inventory />
        </ToastProvider>
      </BrowserRouter>,
    )

    expect(await screen.findByText('Low stock')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Adjust stock for Office chair' }))
    fireEvent.change(screen.getByLabelText('Quantity change'), {
      target: { value: '2' },
    })
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Stock count' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply adjustment' }))

    await waitFor(() => {
      expect(adjustStock).toHaveBeenCalledWith(
        {
          product_id: product.id,
          quantity_change: 2,
          reason: 'Stock count',
        },
        'b71e13fc-c064-42c4-ad88-3fce79d2c618',
      )
    })
  })
})
