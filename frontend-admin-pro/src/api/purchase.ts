// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type PurchaseOrderReturnItemIn = {
  item_id: number
  return_qty: number
}

export type PurchaseOrderReturnIn = {
  warehouse_id: number
  items: PurchaseOrderReturnItemIn[]
}

export type PurchaseOrderItemOut = {
  id: number
  material_id: number
  material_code: string | null
  material_name: string | null
  qty: number
  received_qty: number
  returned_qty: number
  unit_price: string | null
  remark: string | null
}

export type PurchaseOrderOut = {
  id: number
  supplier_id: number
  supplier_code: string | null
  supplier_name: string | null
  code: string
  status: string
  remark: string | null
  confirmed_at: string | null
  confirmed_by: number | null
  created_by: number | null
  created_at: string
  updated_at: string
  items: PurchaseOrderItemOut[]
}

export type PurchaseOrderCreateItemIn = {
  material_id: number
  qty: number
  unit_price?: string | null
  remark?: string | null
}

export type PurchaseOrderCreateIn = {
  supplier_id: number
  code?: string | null
  remark?: string | null
  items?: PurchaseOrderCreateItemIn[]
}

export type PurchaseReceiveItemIn = {
  item_id: number
  receive_qty: number
}

export type PurchaseReceiveIn = {
  warehouse_id: number
  items?: PurchaseReceiveItemIn[] | null
}

export type KittingItemOut = {
  material_id: number
  material_code: string | null
  material_name: string | null
  unit: string | null
  spec: string | null
  supplier_id: number | null
  sku_id: number
  demand_qty: number
  stock_qty: number
  shortage_qty: number
}

export type KittingOut = {
  plan_id: number
  plan_code: string
  order_id: number
  order_code: string | null
  customer_name: string | null
  items: KittingItemOut[]
  missing_boms: { sku_id: number; sku_code: string; sku_name: string }[]
}

export type KittingCreatePurchaseOut = {
  items: { id: number; code: string; supplier_id: number }[]
}

export type PlanKittingPurchaseOrderOut = {
  id: number
  code: string
  status: string
  remark: string | null
  created_at: string
  supplier_id: number
  supplier_code: string | null
  supplier_name: string | null
  total_qty: number
  received_qty: number
}

export const purchaseApi = {
  listOrders(params: any) {
    return http.request<ListResp<PurchaseOrderOut>>({ url: '/admin/purchase/orders', method: 'GET', params })
  },
  createOrder(data: PurchaseOrderCreateIn) {
    return http.request<PurchaseOrderOut>({ url: '/admin/purchase/orders', method: 'POST', data })
  },
  getOrder(id: number) {
    return http.request<PurchaseOrderOut>({ url: `/admin/purchase/orders/${id}`, method: 'GET' })
  },
  confirmOrder(id: number) {
    return http.request<PurchaseOrderOut>({ url: `/admin/purchase/orders/${id}/confirm`, method: 'POST' })
  },
  receiveOrder(id: number, data: PurchaseReceiveIn) {
    return http.request<PurchaseOrderOut>({ url: `/admin/purchase/orders/${id}/receive`, method: 'POST', data })
  },
  returnOrder(id: number, data: PurchaseOrderReturnIn) {
    return http.request<PurchaseOrderOut>({ url: `/admin/purchase/orders/${id}/return`, method: 'POST', data })
  },
  cancelOrder(id: number) {
    return http.request<PurchaseOrderOut>({ url: `/admin/purchase/orders/${id}/cancel`, method: 'POST' })
  },
  printOrder(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; order_id: number; code: string; template_id: number }>({
      url: `/admin/purchase/orders/${id}/print`,
      method: 'GET',
      params,
    })
  },
  exportOrderPdf(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/purchase/orders/${id}/print-pdf`,
      method: 'GET',
      params,
    })
  },

  getPlanKitting(planId: number) {
    return http.request<KittingOut>({ url: `/admin/plans/${planId}/kitting`, method: 'GET' })
  },
  createPurchaseFromKitting(planId: number, supplier_id?: number | null) {
    return http.request<KittingCreatePurchaseOut>({
      url: `/admin/plans/${planId}/kitting/create-purchase`,
      method: 'POST',
      data: supplier_id ? { supplier_id } : undefined,
      params: supplier_id ? { supplier_id } : undefined,
    })
  },
  listKittingPurchaseOrders(planId: number) {
    return http.request<{ items: PlanKittingPurchaseOrderOut[] }>({ url: `/admin/plans/${planId}/kitting/purchase-orders`, method: 'GET' })
  },
  exportOrders(params?: any) {
    return http.downloadBlob({ url: '/admin/purchase/orders/export', method: 'GET', params })
  },
}
