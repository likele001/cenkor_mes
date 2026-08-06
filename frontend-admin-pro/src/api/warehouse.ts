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
}
