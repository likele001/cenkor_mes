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
}
