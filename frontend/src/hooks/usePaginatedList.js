import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Provides debounced, abortable server-side list queries and pagination controls.
 *
 * @param {(params: object, options: {signal: AbortSignal}) => Promise<{items: object[], meta: object}>} fetchPage
 * @param {{pageSize?: number, debounceMs?: number, scopeKey?: string}} options
 */
export function usePaginatedList(
  fetchPage,
  { pageSize = 20, debounceMs = 300, scopeKey = '' } = {},
) {
  const searchTimeoutRef = useRef(null)
  const [result, setResult] = useState({ key: null, items: [], meta: null, error: null })
  const [page, setPageState] = useState(1)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({})
  const [sort, setSort] = useState({ sort_by: '', sort_order: 'asc' })
  const [refreshKey, setRefreshKey] = useState(0)

  const setSearchInputDebounced = useCallback(
    (value) => {
      setSearchInput(value)
      window.clearTimeout(searchTimeoutRef.current)
      searchTimeoutRef.current = window.setTimeout(() => {
        setSearch(value.trim())
        setPageState(1)
      }, value ? debounceMs : 0)
    },
    [debounceMs],
  )

  useEffect(
    () => () => window.clearTimeout(searchTimeoutRef.current),
    [],
  )

  const requestKey = JSON.stringify([
    scopeKey,
    page,
    pageSize,
    search,
    filters,
    sort.sort_by,
    sort.sort_order,
    refreshKey,
  ])
  const loading = result.key !== requestKey

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    const params = {
      page,
      page_size: pageSize,
      ...(search ? { search } : {}),
      ...filters,
      ...(sort.sort_by
        ? { sort_by: sort.sort_by, sort_order: sort.sort_order }
        : {}),
    }

    fetchPage(params, { signal: controller.signal })
      .then((result) => {
        if (!active) return
        setResult({
          key: requestKey,
          items: result.items,
          meta: result.meta ?? {},
          error: null,
        })
      })
      .catch((requestError) => {
        if (!active || controller.signal.aborted) return
        setResult({
          key: requestKey,
          items: [],
          meta: null,
          error: requestError,
        })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [
    filters,
    fetchPage,
    page,
    pageSize,
    requestKey,
    search,
    sort.sort_by,
    sort.sort_order,
  ])

  const setPage = useCallback((nextPage) => {
    setPageState(Math.max(1, nextPage))
  }, [])

  const setFilter = useCallback((name, value) => {
    setFilters((current) => {
      const next = { ...current }
      if (value === '' || value === null || value === undefined) {
        delete next[name]
      } else {
        next[name] = value
      }
      return next
    })
    setPageState(1)
  }, [])

  const setSorting = useCallback((sortBy, sortOrder) => {
    setSort({ sort_by: sortBy, sort_order: sortOrder })
    setPageState(1)
  }, [])

  const refresh = useCallback(() => {
    setRefreshKey((current) => current + 1)
  }, [])

  return {
    items: result.key === requestKey ? result.items : [],
    meta: result.key === requestKey && result.meta
      ? result.meta
      : { page, page_size: pageSize, total: 0, total_pages: 0 },
    page,
    pageSize,
    searchInput,
    filters,
    setSearchInput: setSearchInputDebounced,
    setPage,
    setFilter,
    setSorting,
    refresh,
    loading,
    error: result.key === requestKey ? result.error : null,
  }
}
