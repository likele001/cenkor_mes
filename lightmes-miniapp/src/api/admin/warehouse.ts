import { apiGet, apiPostQuery } from '../request'

export type StockRow = {
  id: number
  warehouse_id: number
  warehouse_name?: string | null
  sku_id: number
  sku_code?: string | null
  sku_name?: string | null
  qty: number
  updated_at?: string | null
}

export const warehouseAdminApi = {
  listWarehouses: () => apiGet<{ items: { id: number; code: string; name: string }[] }>('/admin/warehouse/warehouses', undefined, true),
  listStocks: (p?: Record<string, unknown>) => apiGet<{ items: StockRow[] }>('/admin/warehouse/stocks', p, true),
  adjustStock: (p: { warehouse_id: number; sku_id: number; change_qty: number; remark?: string }) =>
    apiPostQuery<{ qty: number }>('/admin/warehouse/stocks/adjust', { ...p, biz_type: 'manual' }, true),
  listLogs: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/warehouse/logs', p, true),
}
