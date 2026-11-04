import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Table from 'react-bootstrap/Table'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { getInvoice } from '../services/invoiceService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'
import './invoice-print.css'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function formatAddress(address) {
  if (!address) return []
  return [
    address.line1,
    address.line2,
    [address.city, address.region, address.postal_code].filter(Boolean).join(', '),
    address.country,
  ].filter(Boolean)
}

/**
 * Display and print a historical invoice snapshot.
 *
 * @returns {JSX.Element}
 */
export default function InvoiceView() {
  const { invoiceId } = useParams()
  const [state, setState] = useState({ id: null, invoice: null, error: '' })

  useEffect(() => {
    const controller = new AbortController()
    getInvoice(invoiceId, { signal: controller.signal })
      .then((invoice) => setState({ id: invoiceId, invoice, error: '' }))
      .catch((error) => {
        if (!controller.signal.aborted) {
          setState({ id: invoiceId, invoice: null, error: getApiError(error).message })
        }
      })
    return () => controller.abort()
  }, [invoiceId])

  const loading = state.id !== invoiceId
  const invoice = loading ? null : state.invoice
  if (loading) return <LoadingSpinner label="Loading invoice" />
  if (state.error) return <ErrorMessage message={state.error} />
  if (!invoice) return <ErrorMessage message="Invoice was not found." />

  return (
    <section>
      <div className="invoice-actions d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
        <Link className="btn btn-outline-secondary" to={`/sales-orders/${invoice.sales_order_id}`}>
          Back to sales order
        </Link>
        <Button onClick={() => window.print()} variant="primary">Print invoice</Button>
      </div>
      <article className="invoice-paper border rounded bg-white p-4 p-md-5">
        <header className="d-flex flex-wrap justify-content-between gap-4 mb-5">
          <div>
            <p className="text-primary text-uppercase fw-bold small mb-2">SmartERP</p>
            <h1 className="h2">Invoice</h1>
          </div>
          <dl className="row mb-0 invoice-meta">
            <dt className="col-6">Invoice</dt><dd className="col-6">{invoice.invoice_number}</dd>
            <dt className="col-6">Issued</dt><dd className="col-6">{formatDate(invoice.issued_at)}</dd>
            <dt className="col-6">Due</dt><dd className="col-6">{formatDate(invoice.due_date)}</dd>
            <dt className="col-6">Sales order</dt><dd className="col-6">{invoice.sales_order_id}</dd>
          </dl>
        </header>
        <section className="mb-4">
          <h2 className="h6 text-uppercase text-muted">Bill to</h2>
          <strong>{invoice.customer_snapshot?.name}</strong>
          {invoice.customer_snapshot?.email && <div>{invoice.customer_snapshot.email}</div>}
          <div className="invoice-address">
            {formatAddress(invoice.customer_snapshot?.billing_address).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </section>
        <div className="table-responsive">
          <Table bordered className="align-middle">
            <thead>
              <tr><th>SKU</th><th>Description</th><th>Qty</th><th>Unit price</th><th>Discount</th><th>Tax</th><th className="text-end">Total</th></tr>
            </thead>
            <tbody>
              {invoice.items.map((item, index) => (
                <tr key={`${item.product_id ?? item.sku}-${index}`}>
                  <td>{item.sku}</td><td>{item.name}</td><td>{item.quantity}</td>
                  <td>{formatMoney(item.unit_price)}</td>
                  <td>{item.discount_percent}%</td><td>{formatMoney(item.line_tax)}</td>
                  <td className="text-end">{formatMoney(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
        <dl className="row col-md-6 ms-auto invoice-totals">
          <dt className="col-6">Subtotal</dt><dd className="col-6 text-end">{formatMoney(invoice.subtotal)}</dd>
          <dt className="col-6">Discount</dt><dd className="col-6 text-end">{formatMoney(invoice.discount_total)}</dd>
          <dt className="col-6">Tax</dt><dd className="col-6 text-end">{formatMoney(invoice.tax_total)}</dd>
          <dt className="col-6 fs-5">Total due</dt><dd className="col-6 fs-5 text-end fw-bold">{formatMoney(invoice.grand_total)}</dd>
        </dl>
      </article>
    </section>
  )
}
