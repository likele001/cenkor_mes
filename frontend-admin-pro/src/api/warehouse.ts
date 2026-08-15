import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'
import type { ExportJobOut } from '@/api/production'

export type WarehouseOut = { id: number; code: string; name: string; address: string | null }

export type StockOut = {
  id: number
  warehouse_id: number
  warehouse_name: string | null
  sku_id: number
  sku_code: string | null
  sku_name: string | null
  qty: number
  updated_at: string
}

export type MaterialIssueItemOut = {
  id: number
  material_id: number
  material_code: string | null
  material_name: string | null
  sku_id: number
  sku_code: string | null
  qty: number
  unit_cost: number
  cost_amount: number
}

export type MaterialIssueOut = {
  id: number
  code: string
  status: 'draft' | 'issued' | 'cancelled'
  warehouse_id: number
  warehouse_name: string | null
  work_order_id: number | null
  work_order_code: string | null
  total_qty: number
  total_cost: number
  issued_at: string | null
  remark: string | null
  created_at: string
  items?: MaterialIssueItemOut[]
}

export type MaterialReturnOut = {
  id: number
  code: string
  status: 'draft' | 'returned' | 'cancelled'
  warehouse_id: number
  warehouse_name: string | null
  work_order_id: number | null
  work_order_code: string | null
  issue_id: number | null
  issue_code: string | null
  total_qty: number
  total_cost: number
  returned_at: string | null
  remark: string | null
  created_at: string
  items?: MaterialIssueItemOut[]
}

export type IssueItemIn = { material_id: number; sku_id: number; qty: number }
export type ReturnItemIn = { material_id: number; sku_id: number; qty: number; issue_item_id?: number }

export type StockLogOut = {
  id: number
  warehouse_id: number
  warehouse_name: string | null
  sku_id: number
  sku_code: string | null
  sku_name: string | null
  change_qty: number
  balance_qty: number
  biz_type: string
  remark: string | null
  created_at: string
}


export type EntryItemOut = {
  id: number
  material_id: number
  material_code: string | null
  material_name: string | null
  sku_id: number
  sku_code: string | null
  sku_name: string | null
  qty: number
  unit_cost: string
  cost_amount: string
}

export type WarehouseEntryOut = {
  id: number
  code: string
  status: string
  source_type: string
  warehouse_id: number
  warehouse_code: string | null
  warehouse_name: string | null
  purchase_order_id: number | null
  purchase_order_code: string | null
  material_return_id: number | null
  material_return_code: string | null
  total_qty: number
  total_cost: string
  confirmed_at: string | null
  confirmed_by: number | null
  remark: string | null
  created_by: number | null
  created_at: string | null
  items: EntryItemOut[]
}

export type EntryItemIn = { material_id: number; sku_id: number; qty: number }

export const warehouseApi = {
  listWarehouses() {
    return http.request<ListResp<WarehouseOut>>({ url: '/admin/warehouse/warehouses', method: 'GET' })
  },
  listStocks(params: { warehouse_id?: number; item_type?: 'product' | 'material' | 'all' }) {
    const p: any = { warehouse_id: params.warehouse_id }
    if (params.item_type && params.item_type !== 'all') p.item_type = params.item_type
    return http.request<ListResp<StockOut>>({ url: '/admin/warehouse/stocks', method: 'GET', params: p })
  },
  exportStocks(params: { warehouse_id?: number; item_type?: 'product' | 'material' | 'all' }) {
    const p: any = {}
    if (params.warehouse_id) p.warehouse_id = params.warehouse_id
    if (params.item_type && params.item_type !== 'all') p.item_type = params.item_type
    return http.request<ExportJobOut>({ url: '/admin/warehouse/stocks/export', method: 'POST', params: p })
  },
  exportWarehouses(params?: any) {
    return http.downloadBlob({ url: '/admin/warehouse/warehouses/export', method: 'GET', params })
  },
  listLogs(params: { warehouse_id?: number; sku_id?: number; item_type?: 'product' | 'material' | 'all'; offset?: number; limit?: number }) {
    const p: any = { warehouse_id: params.warehouse_id, sku_id: params.sku_id, offset: params.offset, limit: params.limit }
    if (params.item_type && params.item_type !== 'all') p.item_type = params.item_type
    return http.request<ListResp<StockLogOut>>({ url: '/admin/warehouse/logs', method: 'GET', params: p })
  },
  listIssues(params: { warehouse_id?: number; work_order_id?: number; status?: string; offset?: number; limit?: number }) {
    const p: any = { offset: params.offset, limit: params.limit }
    if (params.warehouse_id) p.warehouse_id = params.warehouse_id
    if (params.work_order_id) p.work_order_id = params.work_order_id
    if (params.status) p.status = params.status
    return http.request<ListResp<MaterialIssueOut>>({ url: '/admin/warehouse/issues', method: 'GET', params: p })
  },
  getIssue(id: number) {
    return http.request<MaterialIssueOut>({ url: `/admin/warehouse/issues/${id}`, method: 'GET' })
  },
  createIssue(payload: { code?: string; warehouse_id: number; work_order_id?: number; remark?: string; items: IssueItemIn[] }) {
    return http.request<MaterialIssueOut>({ url: '/admin/warehouse/issues', method: 'POST', data: payload })
  },
  issueMaterials(id: number) {
    return http.request<MaterialIssueOut>({ url: `/admin/warehouse/issues/${id}/issue`, method: 'POST' })
  },
  cancelIssue(id: number) {
    return http.request<MaterialIssueOut>({ url: `/admin/warehouse/issues/${id}/cancel`, method: 'POST' })
  },
  listReturns(params: { warehouse_id?: number; work_order_id?: number; status?: string; offset?: number; limit?: number }) {
    const p: any = { offset: params.offset, limit: params.limit }
    if (params.warehouse_id) p.warehouse_id = params.warehouse_id
    if (params.work_order_id) p.work_order_id = params.work_order_id
    if (params.status) p.status = params.status
    return http.request<ListResp<MaterialReturnOut>>({ url: '/admin/warehouse/returns', method: 'GET', params: p })
  },
  getReturn(id: number) {
    return http.request<MaterialReturnOut>({ url: `/admin/warehouse/returns/${id}`, method: 'GET' })
  },
  createReturn(payload: { code?: string; warehouse_id: number; work_order_id?: number; issue_id?: number; remark?: string; items: ReturnItemIn[] }) {
    return http.request<MaterialReturnOut>({ url: '/admin/warehouse/returns', method: 'POST', data: payload })
  },
  confirmReturn(id: number) {
    return http.request<MaterialReturnOut>({ url: `/admin/warehouse/returns/${id}/confirm`, method: 'POST' })
  },
  cancelReturn(id: number) {
    return http.request<MaterialReturnOut>({ url: `/admin/warehouse/returns/${id}/cancel`, method: 'POST' })
  },
  listEntries(params: { warehouse_id?: number; source_type?: string; status?: string; offset?: number; limit?: number }) {
    const p: any = { offset: params.offset, limit: params.limit }
    if (params.warehouse_id) p.warehouse_id = params.warehouse_id
    if (params.source_type) p.source_type = params.source_type
    if (params.status) p.status = params.status
    return http.request<ListResp<WarehouseEntryOut>>({ url: '/admin/warehouse/entries', method: 'GET', params: p })
  },
  getEntry(id: number) {
    return http.request<WarehouseEntryOut>({ url: `/admin/warehouse/entries/${id}`, method: 'GET' })
  },
  createEntry(payload: { code?: string; source_type: string; warehouse_id: number; purchase_order_id?: number; material_return_id?: number; remark?: string; items: EntryItemIn[] }) {
    return http.request<WarehouseEntryOut>({ url: '/admin/warehouse/entries', method: 'POST', data: payload })
  },
  confirmEntry(id: number) {
    return http.request<WarehouseEntryOut>({ url: `/admin/warehouse/entries/${id}/confirm`, method: 'POST' })
  },
  cancelEntry(id: number) {
    return http.request<WarehouseEntryOut>({ url: `/admin/warehouse/entries/${id}/cancel`, method: 'POST' })
  },
}
