import { http } from '@/utils/http'

export type KittingOut = {
  plan_code: string
  order_code: string
  customer_name: string
  missing_boms: string[]
  plan_id: number
  items: Array<{
    shortage_qty: number
    supplier_id: number
    material_code: string
    material_name: string
    spec: string
    demand_qty: number
    unit: string
    stock_qty: number
  }>
  summary: string
}

export type PlanKittingPurchaseOrderOut = {
  id: number
  order_no: string
  status: string
  code: string
  supplier_name: string
  received_qty: number
  total_qty: number
  created_at: string
}

export const purchaseApi = {
  listKittingPurchaseOrders: (planId: number) => http.request<any>({ url: `/purchase/kitting/${planId}/orders`, method: 'GET' }),
  createPurchaseFromKitting: (planId: number, supplierId: number) => http.request<any>({ url: '/purchase/kitting/create-order', method: 'POST', data: { plan_id: planId, supplier_id: supplierId } }),
}
