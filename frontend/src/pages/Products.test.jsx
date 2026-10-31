import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { ToastProvider } from '../context/ToastContext.jsx'
import { useAuth } from '../hooks/useAuth.js'
import {
  listProductCategories,
  listProducts,
  updateProduct,
} from '../services/productService.js'
import Products from './Products.jsx'

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../services/productService.js', () => ({
  createProduct: vi.fn(),
  listProductCategories: vi.fn(),
  listProducts: vi.fn(),
  updateProduct: vi.fn(),
}))

const product = {
  id: 'product-1',
  sku: 'CHAIR-1',
  name: 'Office chair',
  category: 'Furniture',
  unit: 'each',
  selling_price: '129.95',
  quantity_on_hand: 10,
  reserved_quantity: 3,
  min_stock_level: 2,
  is_active: true,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  useAuth.mockReturnValue({
    hasPermission: (permission) => permission === 'products:write',
  })
  listProducts.mockResolvedValue({
    items: [product],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  listProductCategories.mockResolvedValue(['Furniture'])
})

describe('Products page', () => {
  it('shows product details and asks before deactivation', async () => {
    render(
      <BrowserRouter>
        <ToastProvider>
          <Products />
        </ToastProvider>
      </BrowserRouter>,
    )

    expect(await screen.findByText('Office chair')).toBeInTheDocument()
    expect(screen.getByText('10 / 3 / 7')).toBeInTheDocument()
    expect(screen.getByText('₹129.95')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate Office chair' }))
    expect(
      screen.getByText(/It cannot be used on new orders/),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate product' }))

    await waitFor(() => {
      expect(updateProduct).toHaveBeenCalledWith('product-1', {
        is_active: false,
      })
    })
  })
})
