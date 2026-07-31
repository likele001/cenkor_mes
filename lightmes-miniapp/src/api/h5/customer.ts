import { apiGet, apiPost, apiPostQuery } from '../request'

export type CustomerSkuOut = {
  id: number
  code: string
  name: string
  display_name?: string
  product_id: number
  color: string | null
  material: string | null
  spec: string | null
  remark: string | null
}

export type CatalogProductOut = {
  id: number
  code: string
  name: string
  display_name?: string
  category: string | null
}

export type CustomerOrderListItem = {
  id: number
  code: string
  status: string
  due_date: string | null
  remark: string | null
  created_at: string
}

export type CustomerOrderProgressItem = {
  id: number
  line_no: number
  sku_id?: number | null
  sku: CustomerSkuOut | null
  qty: number
  remark: string | null
}

export type CustomerOrderDetail = {
  id: number
  code: string
  status: string
  due_date: string | null
  remark: string | null
  total_qty: number
  done_qty: number
  progress: number | null
  created_at: string
  updated_at: string
  items: CustomerOrderProgressItem[]
}

export type CustomerProcessOut = {
  id: number
  code: string
  name: string
}

export type CustomerOrderProgressTask = {
  id: number
  task_code: string
  seq: number
  process: CustomerProcessOut | null
  planned_qty: number
  done_qty: number
  progress: number | null
  status: string
}

export type CustomerOrderProgressWorkOrder = {
  id: number
  sku: CustomerSkuOut | null
  qty: number
  done_qty: number
  progress: number | null
  status: string
  tasks: CustomerOrderProgressTask[]
}

export type CustomerOrderProgress = CustomerOrderDetail & {
  work_orders: CustomerOrderProgressWorkOrder[]
}

export type CustomerStatementListItem = {
  id: number
  code: string
  period_start: string | null
  period_end: string | null
  total_amount: number
  status: string
  remark: string | null
  created_at: string
  updated_at: string
}

export type CustomerStatementDetailItem = {
  order_id: number
  order_code: string | null
  amount: number
}

export type CustomerStatementDetail = {
  id: number
  code: string
  period_start: string | null
  period_end: string | null
  total_amount: number
  status: string
  remark: string | null
  created_at: string
  updated_at: string
  items: CustomerStatementDetailItem[]
}

export type ShipmentOut = {
  id: number
  code: string
  logistics_company: string | null
  logistics_no: string | null
  status: string
  shipped_at: string | null
  remark: string | null
}

export type AfterSaleOut = {
  id: number
  code: string
  sale_type: string
  reason: string | null
  solution: string | null
  status: string
  created_at: string
}

export function getCatalog(params?: { product_id?: number; keyword?: string }) {
  return apiGet<{ items: CustomerSkuOut[]; products: CatalogProductOut[]; hint?: string }>(
    '/h5/customer/catalog',
    params,
  )
}

export function placeOrder(body: {
  items: Array<{ sku_id: number; qty: number; remark?: string }>
  due_date?: string
  remark?: string
  submit?: boolean
}) {
  return apiPost<{ id: number; code: string; status: string; created_at: string }>('/h5/customer/orders', body)
}

export function listMyOrders() {
  return apiGet<{ items: CustomerOrderListItem[] }>('/h5/customer/orders')
}

export function getMyOrderDetail(orderId: number) {
  return apiGet<CustomerOrderDetail>(`/h5/customer/orders/${orderId}`)
}

export function getMyOrderProgress(orderId: number) {
  return apiGet<CustomerOrderProgress>(`/h5/customer/orders/${orderId}/progress`)
}

export function listMyStatements(params?: { status?: string; offset?: number; limit?: number }) {
  return apiGet<{ items: CustomerStatementListItem[] }>('/h5/customer/statements', params)
}

export function getMyStatementDetail(id: number) {
  return apiGet<CustomerStatementDetail>(`/h5/customer/statements/${id}`)
}

export function ackMyStatement(id: number) {
  return apiPost<{ id: number; status: string; updated_at: string }>(`/h5/customer/statements/${id}/ack`, {})
}

export function markMyStatementPaid(id: number) {
  return apiPost<{ id: number; status: string; updated_at: string }>(`/h5/customer/statements/${id}/mark-paid`, {})
}

export function getOrderShipments(orderId: number) {
  return apiGet<{ items: ShipmentOut[] }>(`/h5/customer/orders/${orderId}/shipments`)
}

export function getOrderAfterSales(orderId: number) {
  return apiGet<{ items: AfterSaleOut[] }>(`/h5/customer/orders/${orderId}/after-sales`)
}

export function createAfterSale(orderId: number, params: { sale_type: string; reason?: string }) {
  return apiPostQuery<{ id: number; code: string; sale_type: string; status: string; created_at: string }>(
    `/h5/customer/orders/${orderId}/after-sales`,
    params,
  )
}

export function buildStatementDownloadUrl(id: number): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const prefix = base.replace(/\/$/, '')
  const token = uni.getStorageSync('cenkormes_token') || ''
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${prefix}/h5/customer/statements/${id}/download${qs}`
}
