import { describe, expect, it } from 'vitest'
import { createSafeCsv } from './csvExport.js'

describe('createSafeCsv', () => {
  it('quotes CSV values and neutralizes spreadsheet formulas', () => {
    const csv = createSafeCsv(
      [
        { key: 'name', label: 'Customer' },
        { key: 'code', label: 'Code' },
        { key: 'amount', label: 'Amount' },
      ],
      [
        {
          name: 'Acme, "North"',
          code: ' =HYPERLINK("https://example.test")',
          amount: '-12.50',
        },
      ],
    )

    expect(csv).toBe(
      '\uFEFF"Customer","Code","Amount"\r\n' +
        '"Acme, ""North""","\' =HYPERLINK(""https://example.test"")","\'-12.50"',
    )
  })

  it('supports empty results and computed export fields', () => {
    expect(
      createSafeCsv([{ key: 'name', label: 'Name' }], []),
    ).toBe('\uFEFF"Name"')
    expect(
      createSafeCsv(
        [{ key: 'person', label: 'Person', exportValue: (row) => row.person.name }],
        [{ person: { name: '@formula' } }],
      ),
    ).toBe('\uFEFF"Person"\r\n"\'@formula"')
  })

  it('neutralizes a formula after leading control whitespace', () => {
    expect(
      createSafeCsv(
        [{ key: 'value', label: 'Value' }],
        [{ value: '\n=1+1' }],
      ),
    ).toBe('\uFEFF"Value"\r\n"\'\n=1+1"')
  })
})
