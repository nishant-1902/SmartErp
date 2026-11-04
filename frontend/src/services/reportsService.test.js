import { afterEach, describe, expect, it } from 'vitest'
import apiClient from './apiClient.js'
import {
  getDashboard,
  getInventorySummary,
  listReport,
} from './reportsService.js'

const originalAdapter = apiClient.defaults.adapter

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
})

describe('reports service', () => {
  it('fetches the dashboard and unwraps its permission-filtered data', async () => {
    let request
    apiClient.defaults.adapter = async (config) => {
      request = config
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: { dashboard: { total_products: 4 } },
        },
      }
    }

    await expect(getDashboard()).resolves.toEqual({ total_products: 4 })
    expect(request.url).toBe('/reports/dashboard/')
  })

  it('uses the allowlisted report route and retains pagination metadata', async () => {
    let request
    apiClient.defaults.adapter = async (config) => {
      request = config
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: { sales: [{ order_number: 'SO-1' }] },
          meta: { page: 2, page_size: 20, total: 25, total_pages: 2 },
        },
      }
    }

    const report = await listReport(
      'sales',
      { page: 2, page_size: 20, date_from: '2026-03-01' },
      { signal: new AbortController().signal },
    )

    expect(request.url).toBe('/reports/sales/')
    expect(request.params).toEqual({
      page: 2,
      page_size: 20,
      date_from: '2026-03-01',
    })
    expect(report.items).toEqual([{ order_number: 'SO-1' }])
    expect(report.meta.total_pages).toBe(2)
    await expect(listReport('unknown', {})).rejects.toThrow(
      'Unsupported report type.',
    )
  })

  it('fetches the inventory summary from the existing endpoint', async () => {
    apiClient.defaults.adapter = async (config) => ({
      status: 200,
      headers: {},
      config,
      data: {
        success: true,
        data: { inventory: { available_quantity: 8 } },
      },
    })

    await expect(getInventorySummary()).resolves.toEqual({
      available_quantity: 8,
    })
  })
})
