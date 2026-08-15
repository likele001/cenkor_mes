import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'
import type { ExportJobOut } from '@/api/production'

export type CustomerStatementOut = {
  id: number
  customer_id: number
  code: string
  period_start: string | null
  period_end: string | null
  total_amount: number
  status: string
  remark: string | null
  created_at: string
  updated_at: string
}

export type CustomerStatementItemOut = {
  order_id: number
  order_code: string | null
  amount: number
}

export type CustomerStatementDetailOut = CustomerStatementOut & {
  customer: { id: number; code: string; name: string } | null
  items: CustomerStatementItemOut[]
}

export type LedgerOut = {
  id: number
  direction: string
  category: string
  party_type: string
  party_id: number | null
  statement_type: string | null
  statement_id: number | null
  amount: number
  biz_date: string
  remark: string | null
  created_by: number | null
  created_at: string
}

export type LedgerCreateIn = {
  direction: string
  category: string
  party_type: string
  party_id?: number | null
  statement_type?: string | null
  statement_id?: number | null
  amount: number
  biz_date: string
  remark?: string | null
}

export type SupplierStatementOut = {
  id: number
  supplier_id: number
  supplier_code: string | null
  supplier_name: string | null
  code: string
  period_start: string | null
  period_end: string | null
  total_amount: number
  status: string
  remark: string | null
  created_at: string
  updated_at: string
}

export type SupplierStatementItemOut = {
  purchase_order_id: number
  purchase_order_code: string | null
  amount: number
}

export type SupplierStatementDetailOut = SupplierStatementOut & {
  supplier: { id: number; code: string; name: string } | null
  items: SupplierStatementItemOut[]
}

export type SupplierStatementCreateIn = {
  supplier_id: number
  order_ids: number[]
  period_start?: string | null
  period_end?: string | null
  remark?: string | null
}

export type PayableOut = {
  supplier_id: number
  supplier_code: string | null
  supplier_name: string | null
  total_payable: number
  paid_amount: number
  unpaid_amount: number
}

export type ProfitOut = {
  month: string
  revenue: number
  cost: number
  gross_profit: number
  gross_margin: number
  breakdown: {
    customers: { customer_id: number; customer_name: string; amount: number }[]
    suppliers: { supplier_id: number; supplier_name: string; amount: number }[]
  }
}

export const financeApi = {
  listCustomerStatements(params: any) {
    return http.request<ListResp<CustomerStatementOut>>({ url: '/admin/finance', method: 'GET', params })
  },
  getCustomerStatement(id: number) {
    return http.request<CustomerStatementDetailOut>({ url: `/admin/finance/${id}`, method: 'GET' })
  },
  printCustomerStatement(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; statement_id: number; code: string; template_id: number }>({
      url: `/admin/finance/${id}/print`,
      method: 'GET',
      params,
    })
  },
  exportCustomerStatementPdf(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/finance/${id}/print-pdf`,
      method: 'GET',
      params,
    })
  },
  confirmCustomerStatement(id: number) {
    return http.request<{ id: number; status: string }>({ url: `/admin/finance/${id}/confirm`, method: 'POST' })
  },
  markCustomerStatementPaid(id: number) {
    return http.request<{ id: number; status: string; updated_at: string }>({ url: `/admin/finance/${id}/mark-paid`, method: 'POST' })
  },

  listLedgers(params: any) {
    return http.request<ListResp<LedgerOut>>({ url: '/admin/finance/ledgers', method: 'GET', params })
  },
  createLedger(data: LedgerCreateIn) {
    return http.request<LedgerOut>({ url: '/admin/finance/ledgers', method: 'POST', data })
  },

  getProfit(params: { month: string }) {
    return http.request<ProfitOut>({ url: '/admin/finance/profit', method: 'GET', params })
  },
  exportStatementsExcel(params: { customer_id?: number; status?: string }) {
    return http.request<ExportJobOut>({ url: '/admin/finance/statements/export', method: 'POST', params })
  },

  listSupplierStatements(params: any) {
    return http.request<ListResp<SupplierStatementOut>>({ url: '/admin/finance/supplier-statements', method: 'GET', params })
  },
  createSupplierStatement(data: SupplierStatementCreateIn) {
    return http.request<SupplierStatementOut>({ url: '/admin/finance/supplier-statements', method: 'POST', data })
  },
  getSupplierStatement(id: number) {
    return http.request<SupplierStatementDetailOut>({ url: `/admin/finance/supplier-statements/${id}`, method: 'GET' })
  },
  confirmSupplierStatement(id: number) {
    return http.request<{ id: number; status: string }>({ url: `/admin/finance/supplier-statements/${id}/confirm`, method: 'POST' })
  },
  markSupplierStatementPaid(id: number) {
    return http.request<{ id: number; status: string; updated_at: string }>({ url: `/admin/finance/supplier-statements/${id}/mark-paid`, method: 'POST' })
  },
  getSupplierPayables() {
    return http.request<ListResp<PayableOut>>({ url: '/admin/finance/supplier-statements/payables', method: 'GET' })
  },
}
