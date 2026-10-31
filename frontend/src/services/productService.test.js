import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from './apiClient.js'
import {
  adjustStock,
  listProducts,
  listStockMovements,
} from './productService.js'

vi.mock('./apiClient.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('productService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns products with their pagination metadata', async () => {
    const products = [{ id: 'product-1', sku: 'CHAIR-1' }]
    const meta = { page: 1, page_size: 20, total: 1, total_pages: 1 }
    apiClient.get.mockResolvedValue({
      data: { data: { products }, meta },
    })

    await expect(listProducts({ search: 'chair' })).resolves.toEqual({
      items: products,
      meta,
    })
    expect(apiClient.get).toHaveBeenCalledWith('/products/', {
      params: { search: 'chair' },
      signal: undefined,
    })
  })

  it('sends an idempotency key with a stock adjustment', async () => {
    const movement = { id: 'movement-1' }
    apiClient.post.mockResolvedValue({
      data: { data: { stock_movement: movement } },
    })
    const values = {
      product_id: 'product-1',
      quantity_change: 2,
      reason: 'Stock count',
    }

    await expect(adjustStock(values, 'request-key')).resolves.toBe(movement)
    expect(apiClient.post).toHaveBeenCalledWith('/stock-adjustments/', values, {
      headers: { 'Idempotency-Key': 'request-key' },
    })
  })

  it('passes validated movement filters to the list endpoint', async () => {
    const movements = [{ id: 'movement-1' }]
    const meta = { page: 1, page_size: 20, total: 1, total_pages: 1 }
    apiClient.get.mockResolvedValue({
      data: { data: { stock_movements: movements }, meta },
    })

    await expect(
      listStockMovements({ type: 'adjustment', user: 'user-id' }),
    ).resolves.toEqual({ items: movements, meta })
    expect(apiClient.get).toHaveBeenCalledWith('/stock-movements/', {
      params: { type: 'adjustment', user: 'user-id' },
      signal: undefined,
    })
  })
})
