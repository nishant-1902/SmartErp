import { afterEach, describe, expect, it, vi } from 'vitest'
import apiClient from './apiClient.js'
import { receivePurchaseOrder } from './purchaseOrderService.js'

vi.mock('./apiClient.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

afterEach(() => vi.clearAllMocks())

describe('purchaseOrderService', () => {
  it('sends the receipt payload and Idempotency-Key header to the receive endpoint', async () => {
    apiClient.post.mockResolvedValue({
      data: { data: { purchase_receipt: { receipt_reference: 'RCPT-2026-000001' } } },
    })
    const payload = {
      items: [{ product_id: 'product-1', quantity_received: 2 }],
    }

    await expect(
      receivePurchaseOrder('po-1', payload, 'idempotency-uuid'),
    ).resolves.toEqual({ receipt_reference: 'RCPT-2026-000001' })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/purchase-orders/po-1/receive/',
      payload,
      { headers: { 'Idempotency-Key': 'idempotency-uuid' } },
    )
  })
})
