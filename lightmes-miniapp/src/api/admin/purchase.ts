import { apiGet, apiPost } from '../request'

export type PurchaseOrderItem = {
  id?: number
  material_id: number
  material_code?: string | null
  material_name?: string | null
  qty: number
  received_qty?: number
  returned_qty?: number
  unit_price?: string | number | null
  remark?: string | null
}

export type PurchaseOrder = {
  id: number
  supplier_id: number
  supplier_name?: string | null
  code: string
  status: string
  remark?: string | null
  items: PurchaseOrderItem[]
}

export const purchaseAdminApi = {
  list: (p?: Record<string, unknown>) => apiGet<{ items: PurchaseOrder[] }>('/admin/purchase/orders', p, true),
  get: (id: number) => apiGet<PurchaseOrder>(`/admin/purchase/orders/${id}`, undefined, true),
  create: (data: object) => apiPost<PurchaseOrder>('/admin/purchase/orders', data, true),
  confirm: (id: number) => apiPost<PurchaseOrder>(`/admin/purchase/orders/${id}/confirm`, {}, true),
  cancel: (id: number) => apiPost<PurchaseOrder>(`/admin/purchase/orders/${id}/cancel`, {}, true),
  receive: (id: number, data: object) => apiPost<PurchaseOrder>(`/admin/purchase/orders/${id}/receive`, data, true),
  listStatements: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/purchase/statements', p, true),
  createStatement: (data: object) => apiPost('/admin/purchase/statements', data, true),
  getStatement: (id: number) => apiGet(`/admin/purchase/statements/${id}`, undefined, true),
  confirmStatement: (id: number) => apiPost(`/admin/purchase/statements/${id}/confirm`, {}, true),
  markStatementPaid: (id: number) => apiPost(`/admin/purchase/statements/${id}/mark-paid`, {}, true),
  listWarehouses: () => apiGet<{ items: { id: number; name: string; code: string }[] }>('/admin/warehouse/warehouses', undefined, true),
  listSuppliers: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/master/suppliers', { limit: 200 }, true),
  listMaterials: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/master/materials', { limit: 200 }, true),
}
