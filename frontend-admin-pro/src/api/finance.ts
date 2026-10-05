// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type CustomerStatementOut = {
  id: number
  customer_id: number
  code: string
  period_start: string | null
  period_end: string | null
  total_amount: number
  status: string
  paid_amount: number
  balance: number
  due_date: string | null
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
  paid_amount: number
  balance: number
  due_date: string | null
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
  due_date?: string | null
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

export type StatementPaymentOut = {
  id: number
  statement_type?: string
  statement_id: number
  amount: number
  paid_date: string | null
  method: string | null
  remark: string | null
  created_by: number | null
  created_at: string
}

export type StatementPaymentCreateIn = {
  amount: number
  paid_date?: string | null
  method?: string | null
  remark?: string | null
}

export type AgingBucket = { bucket: string; count: number; balance: number }
export type AgingItem = {
  statement_id: number
  code: string
  amount: number
  paid_amount: number
  balance: number
  due_date: string | null
  days_overdue: number
  bucket: string
  status: string
}
export type AgingResp = {
  direction: string
  as_of: string
  total_balance: number
  overdue_balance: number
  buckets: AgingBucket[]
  items: AgingItem[]
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
    return http.downloadBlob({ url: '/admin/finance/statements/export', method: 'GET', params })
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

  listCustomerStatementPayments(id: number) {
    return http.request<{ items: StatementPaymentOut[] }>({ url: `/admin/finance/${id}/payments`, method: 'GET' })
  },
  createCustomerStatementPayment(id: number, data: StatementPaymentCreateIn) {
    return http.request<{ payment: StatementPaymentOut; statement: CustomerStatementOut }>({ url: `/admin/finance/${id}/payments`, method: 'POST', data })
  },
  listSupplierStatementPayments(id: number) {
    return http.request<{ items: StatementPaymentOut[] }>({ url: `/admin/finance/supplier-statements/${id}/payments`, method: 'GET' })
  },
  createSupplierStatementPayment(id: number, data: StatementPaymentCreateIn) {
    return http.request<{ payment: StatementPaymentOut; statement: SupplierStatementOut }>({ url: `/admin/finance/supplier-statements/${id}/payments`, method: 'POST', data })
  },
  reversePayment(paymentId: number) {
    return http.request<{ reversed: number }>({ url: `/admin/finance/payments/${paymentId}`, method: 'DELETE' })
  },
  getAging(direction: 'ar' | 'ap') {
    return http.request<AgingResp>({ url: '/admin/finance/aging', method: 'GET', params: { direction } })
  },
}
