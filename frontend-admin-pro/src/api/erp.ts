import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type InvoiceItemOut = {
  id?: number
  line_no: number
  order_id: number | null
  purchase_order_id: number | null
  sku_id: number | null
  material_id: number | null
  qty: number
  unit_price: number
  amount: number
  tax_rate: number
  tax_amount: number
  total_amount: number
}

export type InvoiceOut = {
  id: number
  tenant_id: number
  code: string
  invoice_no: string | null
  direction: string
  invoice_type: string
  customer_id: number | null
  supplier_id: number | null
  statement_id: number | null
  supplier_statement_id: number | null
  order_id: number | null
  purchase_order_id: number | null
  invoice_date: string
  tax_rate: number
  amount: number
  tax_amount: number
  total_amount: number
  status: string
  remark: string | null
  created_at: string
  updated_at: string
  items?: InvoiceItemOut[]
}

export type InvoiceCreateIn = {
  code?: string
  invoice_no?: string | null
  direction: string
  invoice_type: string
  customer_id?: number | null
  supplier_id?: number | null
  statement_id?: number | null
  supplier_statement_id?: number | null
  order_id?: number | null
  purchase_order_id?: number | null
  invoice_date: string
  tax_rate: number
  amount: number
  tax_amount: number
  total_amount: number
  remark?: string | null
  items: InvoiceItemOut[]
}

export type AccountOut = {
  id: number
  code: string
  name: string
  subject_type: string
  direction: string
  parent_id: number | null
  is_active: boolean
  opening_balance: number
  remark: string | null
}

export type VoucherEntryOut = {
  id?: number
  line_no: number
  account_subject_id: number
  summary: string | null
  debit_amount: number
  credit_amount: number
  party_type: string | null
  party_id: number | null
}

export type VoucherOut = {
  id: number
  code: string
  voucher_date: string
  voucher_type: string
  summary: string | null
  amount: number
  period: string
  status: string
  created_at: string
  entries?: VoucherEntryOut[]
}

export type WorkOrderCostOut = {
  id: number
  work_order_id: number
  order_id: number | null
  product_id: number | null
  sku_id: number | null
  qty: number
  material_cost: number
  labor_cost: number
  overhead_cost: number
  total_cost: number
  unit_cost: number
  quote_amount: number
  gross_profit: number
  gross_margin: number
  status: string
  computed_at: string | null
  updated_at: string
  items?: Array<{ id: number; cost_type: string; source_type: string; source_id: number | null; ref_code: string | null; amount: number; remark: string | null }>
}

export type FixedAssetOut = {
  id: number
  asset_no: string
  name: string
  category: string
  model: string | null
  equipment_id: number | null
  workshop: string | null
  department_id: number | null
  original_value: number
  residual_value: number
  useful_life_months: number
  depreciation_method: string
  monthly_depreciation: number
  purchase_date: string | null
  start_use_date: string | null
  status: string
  accumulated_depreciation: number
  book_value: number
  remark: string | null
}

export type DepreciationRecordOut = {
  id: number
  asset_id: number
  period: string
  depreciation_amount: number
  accumulated_depreciation: number
  book_value: number
}

export type AssetCheckOut = {
  id: number
  check_no: string
  check_date: string
  status: string
  remark: string | null
  created_at: string
  items?: Array<{ id?: number; asset_id: number; expected_qty: number; checked_qty: number; diff_qty: number; status: string; remark: string | null }>
}

export type TrialBalanceRow = {
  account_id: number
  code: string
  name: string
  subject_type: string
  direction: string
  opening_balance: number
  debit_amount: number
  credit_amount: number
  ending_balance: number
}

export const erpApi = {
  // 发票
  listInvoices: (params: Record<string, unknown>) => http.get<ListResp<InvoiceOut>>('/admin/erp/invoices', { params }),
  getInvoice: (id: number) => http.get<InvoiceOut>(`/admin/erp/invoices/${id}`),
  createInvoice: (data: InvoiceCreateIn) => http.post('/admin/erp/invoices', data),
  updateInvoice: (id: number, data: Partial<InvoiceCreateIn>) => http.put(`/admin/erp/invoices/${id}`, data),
  deleteInvoice: (id: number) => http.delete(`/admin/erp/invoices/${id}`),
  postInvoice: (id: number) => http.post(`/admin/erp/invoices/${id}/post`),
  voidInvoice: (id: number) => http.post(`/admin/erp/invoices/${id}/void`),

  // 科目
  listAccounts: (params?: Record<string, unknown>) => http.get<{ items: AccountOut[] }>('/admin/erp/accounts', { params }),
  accountOptions: () => http.get<Array<{ id: number; code: string; name: string; direction: string }>>('/admin/erp/accounts/options'),
  createAccount: (data: Record<string, unknown>) => http.post('/admin/erp/accounts', data),
  updateAccount: (id: number, data: Record<string, unknown>) => http.put(`/admin/erp/accounts/${id}`, data),
  deleteAccount: (id: number) => http.delete(`/admin/erp/accounts/${id}`),

  // 凭证
  listVouchers: (params: Record<string, unknown>) => http.get<ListResp<VoucherOut>>('/admin/erp/vouchers', { params }),
  getVoucher: (id: number) => http.get<VoucherOut>(`/admin/erp/vouchers/${id}`),
  createVoucher: (data: Record<string, unknown>) => http.post('/admin/erp/vouchers', data),
  updateVoucher: (id: number, data: Record<string, unknown>) => http.put(`/admin/erp/vouchers/${id}`, data),
  deleteVoucher: (id: number) => http.delete(`/admin/erp/vouchers/${id}`),
  postVoucher: (id: number) => http.post(`/admin/erp/vouchers/${id}/post`),
  unpostVoucher: (id: number) => http.post(`/admin/erp/vouchers/${id}/unpost`),

  // 报表
  trialBalance: (period: string) => http.get<{ period: string; items: TrialBalanceRow[] }>('/admin/erp/reports/trial-balance', { params: { period } }),
  balanceSheet: (period: string) => http.get<{ period: string; assets: number; liabilities: number; equity: number; balance: number }>('/admin/erp/reports/balance-sheet', { params: { period } }),

  // 成本
  listCosts: (params: Record<string, unknown>) => http.get<ListResp<WorkOrderCostOut>>('/admin/erp/costs', { params }),
  getCost: (workOrderId: number) => http.get<WorkOrderCostOut>(`/admin/erp/costs/${workOrderId}`),
  calculateCost: (data: { work_order_id?: number; period?: string }) => http.post('/admin/erp/costs/calculate', data),
  addOverhead: (workOrderId: number, data: { amount: number; remark?: string }) => http.post(`/admin/erp/costs/${workOrderId}/overhead`, data),
  closeCost: (workOrderId: number) => http.post(`/admin/erp/costs/${workOrderId}/close`),

  // 资产
  listAssets: (params: Record<string, unknown>) => http.get<ListResp<FixedAssetOut>>('/admin/erp/assets', { params }),
  getAsset: (id: number) => http.get<FixedAssetOut>(`/admin/erp/assets/${id}`),
  createAsset: (data: Record<string, unknown>) => http.post('/admin/erp/assets', data),
  updateAsset: (id: number, data: Record<string, unknown>) => http.put(`/admin/erp/assets/${id}`, data),
  deleteAsset: (id: number) => http.delete(`/admin/erp/assets/${id}`),
  depreciateBatch: (period: string) => http.post('/admin/erp/assets/depreciate-batch', { period }),
  listDepreciation: (params: Record<string, unknown>) => http.get<ListResp<DepreciationRecordOut>>('/admin/erp/assets/depreciation', { params }),
  listChecks: (params: Record<string, unknown>) => http.get<ListResp<AssetCheckOut>>('/admin/erp/assets/checks', { params }),
  getCheck: (id: number) => http.get<AssetCheckOut>(`/admin/erp/assets/checks/${id}`),
  createCheck: (data: Record<string, unknown>) => http.post('/admin/erp/assets/checks', data),
  updateCheckItems: (id: number, items: Array<Record<string, unknown>>) => http.put(`/admin/erp/assets/checks/${id}`, items),
  completeCheck: (id: number) => http.post(`/admin/erp/assets/checks/${id}/complete`),
}
