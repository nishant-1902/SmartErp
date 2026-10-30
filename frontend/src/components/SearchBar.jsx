import { useEffect, useId, useRef, useState } from 'react'

/**
 * Search input that emits changes only after the user pauses typing.
 *
 * @param {{onSearch: (value: string) => void, placeholder?: string, delay?: number, label?: string}} props
 */
export default function SearchBar({
  onSearch,
  placeholder = 'Search',
  delay = 300,
  label = 'Search',
}) {
  const [value, setValue] = useState('')
  const inputId = useId()
  const onSearchRef = useRef(onSearch)
  const hasChanged = useRef(false)

  useEffect(() => {
    onSearchRef.current = onSearch
  }, [onSearch])

  useEffect(() => {
    if (!hasChanged.current) return undefined
    const timeoutId = window.setTimeout(
      () => onSearchRef.current(value.trim()),
      delay,
    )
    return () => window.clearTimeout(timeoutId)
  }, [delay, value])

  return (
    <div className="input-group">
      <label className="visually-hidden" htmlFor={inputId}>
        {label}
      </label>
      <span aria-hidden="true" className="input-group-text bg-white">
        ⌕
      </span>
      <input
        autoComplete="off"
        className="form-control"
        id={inputId}
        onChange={(event) => {
          hasChanged.current = true
          setValue(event.target.value)
        }}
        placeholder={placeholder}
        type="search"
        value={value}
      />
    </div>
  )
}
