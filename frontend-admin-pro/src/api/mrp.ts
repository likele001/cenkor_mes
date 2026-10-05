// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export interface MrpItemOut {
  id: number
  work_order_id: number | null
  order_id: number | null
  sku_id: number
  material_id: number
  bom_id: number | null
  bom_scope: string | null
  wo_qty: number
  qty_per: number
  gross_qty: number
  stock_qty: number
  on_order_qty: number
  net_qty: number
  suggested_purchase_qty: number
  supplier_id: number | null
  unit_price: string | null
  purchase_order_id: number | null
  work_order_code: string | null
  order_code: string | null
  sku_code: string | null
  sku_name: string | null
  material_code: string | null
  material_name: string | null
  material_unit: string | null
  supplier_name: string | null
}

export interface MrpPlanBrief {
  id: number
  code: string
  status: string
  source_type: string
  total_skus: number
  total_materials: number
  total_purchase_qty: number
  created_at: string
}

export interface MrpPlanOut {
  id: number
  code: string
  status: string
  source_type: string
  remark: string | null
  total_skus: number
  total_materials: number
  total_purchase_qty: number
  created_at: string
  items: MrpItemOut[]
}

export interface MrpComputeIn {
  work_order_ids: number[]
  remark?: string | null
  /** 限定统计哪些仓库的库存；不传＝全部启用中的仓库 */
  warehouse_ids?: number[] | null
}

export interface MrpConvertIn {
  item_ids?: number[] | null
  only_with_supplier?: boolean
  remark?: string | null
}

export interface MrpConvertOut {
  plan_id: number
  plan_code: string
  status: string
  purchase_orders: { purchase_order_id: number; code: string; lines: number }[]
  converted_items: number
  skipped_no_supplier: number
}

export const mrpApi = {
  listPlans(params: any) {
    return http.request<ListResp<MrpPlanBrief> & { total?: number }>({ url: '/admin/mrp', method: 'GET', params })
  },
  getPlan(id: number) {
    return http.request<MrpPlanOut>({ url: `/admin/mrp/${id}`, method: 'GET' })
  },
  compute(data: MrpComputeIn) {
    return http.request<{ id: number; code: string; total_purchase_qty: number }>({ url: '/admin/mrp/compute', method: 'POST', data })
  },
  convertPlan(id: number, data: MrpConvertIn) {
    return http.request<MrpConvertOut>({ url: `/admin/mrp/${id}/convert`, method: 'POST', data })
  },
}
