import { afterEach, describe, expect, it, vi } from 'vitest'
import apiClient from './apiClient.js'
import {
  fulfilSalesOrder,
  listSalesOrders,
  recordSalesOrderPayment,
} from './salesOrderService.js'

vi.mock('./apiClient.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

afterEach(() => vi.clearAllMocks())

describe('salesOrderService', () => {
  it('sends supported order filters to the list endpoint', async () => {
    const orders = [{ id: 'order-1' }]
    const meta = { page: 1, total: 1 }
    apiClient.get.mockResolvedValue({
      data: { data: { sales_orders: orders }, meta },
    })

    await expect(
      listSalesOrders({
        status: 'fulfilled',
        payment_status: 'partial',
        customer_id: 'customer-1',
      }),
    ).resolves.toEqual({ items: orders, meta })
    expect(apiClient.get).toHaveBeenCalledWith('/sales-orders/', {
      params: {
        status: 'fulfilled',
        payment_status: 'partial',
        customer_id: 'customer-1',
      },
      signal: undefined,
    })
  })

  it('sends idempotency keys with fulfillment and payment requests', async () => {
    apiClient.post.mockResolvedValue({
      data: { data: { sales_order: { id: 'order-1' } } },
    })
    await fulfilSalesOrder('order-1', 'fulfill-key')
    await recordSalesOrderPayment(
      'order-1',
      { amount: '10.00', method: 'cash' },
      'payment-key',
    )

    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      '/sales-orders/order-1/fulfill/',
      {},
      { headers: { 'Idempotency-Key': 'fulfill-key' } },
    )
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      '/sales-orders/order-1/payments/',
      { amount: '10.00', method: 'cash' },
      { headers: { 'Idempotency-Key': 'payment-key' } },
    )
  })
})
