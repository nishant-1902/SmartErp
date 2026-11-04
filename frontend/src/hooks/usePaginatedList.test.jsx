import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { usePaginatedList } from './usePaginatedList.js'

afterEach(() => {
  cleanup()
})

describe('usePaginatedList', () => {
  it('debounces search before making a server-side request', async () => {
    const fetchPage = vi.fn(async (params) => ({
      items: [{ id: params.search || 'initial' }],
      meta: { page: params.page, page_size: params.page_size, total: 1 },
    }))
    const { result } = renderHook(() =>
      usePaginatedList(fetchPage, { debounceMs: 30, pageSize: 10 }),
    )

    await waitFor(() => expect(fetchPage).toHaveBeenCalledTimes(1))
    expect(fetchPage).toHaveBeenCalledTimes(1)
    expect(fetchPage.mock.calls[0][0]).toMatchObject({ page: 1, page_size: 10 })

    act(() => result.current.setSearchInput('  Ada  '))
    expect(fetchPage).toHaveBeenCalledTimes(1)

    await waitFor(() => expect(fetchPage).toHaveBeenCalledTimes(2))
    expect(fetchPage.mock.calls[1][0].search).toBe('Ada')
    await waitFor(() => expect(result.current.items).toEqual([{ id: 'Ada' }]))
  })

  it('aborts stale requests and never displays stale results', async () => {
    const requests = []
    const fetchPage = vi.fn((params, { signal }) => new Promise((resolve) => {
      requests.push({ params, resolve, signal })
    }))
    const { result } = renderHook(() =>
      usePaginatedList(fetchPage, { debounceMs: 0 }),
    )

    await waitFor(() => expect(requests).toHaveLength(1))
    act(() => result.current.setFilter('status', 'active'))
    await waitFor(() => expect(requests).toHaveLength(2))
    expect(requests[0].signal.aborted).toBe(true)

    await act(async () => {
      requests[0].resolve({
        items: [{ id: 'stale' }],
        meta: { page: 1, page_size: 20, total: 1 },
      })
      requests[1].resolve({
        items: [{ id: 'fresh' }],
        meta: { page: 1, page_size: 20, total: 1 },
      })
    })
    await waitFor(() => expect(result.current.items).toEqual([{ id: 'fresh' }]))
  })
})
