import { apiGet, apiPost, apiPostQuery } from '../request'

export type CustomerStatement = {
  id: number
  customer_id: number
  code: string
  period_start?: string | null
  period_end?: string | null
  total_amount: number
  status: string
  remark?: string | null
  created_at?: string
  customer?: { id: number; code: string; name: string } | null
  items?: { order_id: number; order_code?: string | null; amount: number }[]
}

export type LedgerRow = {
  id: number
  direction: string
  category: string
  party_type: string
  party_id?: number | null
  amount: number
  biz_date: string
  remark?: string | null
  created_at?: string
}

export type ProfitData = {
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

export const financeAdminApi = {
  listStatements: (p?: Record<string, unknown>) => apiGet<{ items: CustomerStatement[] }>('/admin/finance', p, true),
  getStatement: (id: number) => apiGet<CustomerStatement>(`/admin/finance/${id}`, undefined, true),
  createStatement: (p: {
    customer_id: number
    order_ids: string
    period_start?: string | null
    period_end?: string | null
    remark?: string | null
    code?: string | null
  }) => apiPostQuery<CustomerStatement>('/admin/finance', p, true),
  confirmStatement: (id: number) => apiPost<{ id: number; status: string }>(`/admin/finance/${id}/confirm`, {}, true),
  markStatementPaid: (id: number) => apiPost<{ id: number; status: string }>(`/admin/finance/${id}/mark-paid`, {}, true),
  listLedgers: (p?: Record<string, unknown>) => apiGet<{ items: LedgerRow[] }>('/admin/finance/ledgers', p, true),
  createLedger: (data: object) => apiPost<LedgerRow>('/admin/finance/ledgers', data, true),
  getProfit: (month: string) => apiGet<ProfitData>('/admin/finance/profit', { month }, true),
  listCustomers: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/production/customers', { limit: 200 }, true),
  listSuppliers: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/master/suppliers', { limit: 200 }, true),
}
