import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Home from './Home.jsx'

describe('Home', () => {
  it('shows the SmartERP welcome message', () => {
    render(<Home />)

    expect(
      screen.getByRole('heading', { name: 'Welcome to SmartERP' }),
    ).toBeInTheDocument()
  })
})
