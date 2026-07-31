import axios from 'axios'
import { masterApi } from '@/api/master'
import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'
import { customerApi } from '@/api/customers'

export type OrderSkuOption = {
  id: number
  code: string
  product_id?: number
  product_name?: string
  sku_name?: string
  display_label?: string
}

export type OrderFormOptions = {
  customers: { id: number; code: string; name: string }[]
  skus: OrderSkuOption[]
}

export type OrderItemOut = {
  id: number
  tenant_id: number
  order_id: number
  line_no: number
  sku_id: number
  qty: number
  remark: string | null
  created_at: string
  updated_at: string
  sku: {
    id: number
    code: string
    name: string
    product_id?: number
    product_name?: string
    sku_name?: string
    display_label?: string
  } | null
  locked?: boolean
  lock_reason?: string | null
}

export type OrderOut = {
  id: number
  tenant_id: number
  customer_id: number
  opportunity_id?: number | null
  opportunity_code?: string | null
  code: string
  status: string
  due_date: string | null
  remark: string | null
  confirmed_at: string | null
  confirmed_by: number | null
  created_at: string
  updated_at: string
  customer: { id: number; name: string; code: string } | null
}

export type OrderDetailOut = OrderOut & { items: OrderItemOut[]; order_plan_locked?: boolean }

export type OrderImportResult = {
  orders_created: number
  lines_success: number
  errors: { row: number; message: string }[]
  warnings: { row: number; message: string }[]
  created_orders: { id: number; code: string }[]
}

export type OrderItemCreateIn = {
  line_no: number
  sku_id: number
  qty: number
  remark?: string | null
}

export type OrderCreateIn = {
  customer_id: number
  code: string
  due_date?: string | null
  remark?: string | null
  opportunity_id?: number | null
  items: OrderItemCreateIn[]
}

export type OrderItemUpsertIn = {
  id?: number | null
  line_no: number
  sku_id: number
  qty: number
  remark?: string | null
}

export type OrderUpdateIn = {
  customer_id?: number | null
  code?: string | null
  due_date?: string | null
  remark?: string | null
  status?: string | null
  items?: OrderItemUpsertIn[]
}

export const orderApi = {
  // 订单
  listOrders(params: any) {
    return http.request<ListResp<OrderOut>>({ url: '/admin/production/orders', method: 'GET', params })
  },
  getOrder(id: number) {
    return http.request<OrderDetailOut>({ url: `/admin/production/orders/${id}`, method: 'GET' })
  },
  /** 新建订单下拉：仅需 order.manage（后端需已部署 meta/form-options） */
  getOrderFormOptions() {
    return http.request<OrderFormOptions>({ url: '/admin/production/orders/meta/form-options', method: 'GET' })
  },
  /** 优先 meta/form-options；404 时回退客户/型号列表（需 customer.manage、sku.manage） */
  async fetchOrderFormOptions(): Promise<OrderFormOptions> {
    try {
      return await this.getOrderFormOptions()
    } catch (e: unknown) {
      const status = axios.isAxiosError(e) ? e.response?.status : undefined
      if (status !== 404) throw e
      const [cRes, sRes, pRes] = await Promise.all([
        customerApi.listCustomers({ keyword: '', offset: 0, limit: 200, include_inactive: false }),
        masterApi.listSkus({ offset: 0, limit: 200, include_inactive: false }),
        masterApi.listProducts({ offset: 0, limit: 500, include_inactive: false }),
      ])
      const pmap = new Map((pRes.items || []).map((p) => [p.id, p]))
      return {
        customers: (cRes.items || []).map((c) => ({ id: c.id, code: c.code, name: c.name })),
        skus: (sRes.items || [])
          .filter((s) => {
            const code = (s.code || '').toUpperCase()
            const p = pmap.get(s.product_id)
            if (code.startsWith('MAT-')) return false
            if (p?.code === '__MATERIAL__' || p?.category === 'material') return false
            return true
          })
          .map((s) => {
            const p = pmap.get(s.product_id)
            const product_name = (p?.display_name || p?.name || '').trim()
            const sku_name = (s.name || '').trim()
            const display_label = product_name && sku_name ? `${product_name} · ${sku_name}` : sku_name || product_name
            return {
              id: s.id,
              code: s.code,
              product_id: s.product_id,
              product_name,
              sku_name,
              display_label,
            }
          }),
      }
    }
  },
  rejectOrder(id: number, reason: string) {
    return http.request<OrderDetailOut>({
      url: `/admin/production/orders/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },
  confirmOrder(id: number) {
    return http.request<{
      order_id: number
      work_order_count: number
      automation_plan_id?: number | null
      automation_pipeline_ran?: boolean
    }>({ url: `/admin/production/orders/${id}/confirm`, method: 'POST' })
  },
  createOrder(data: OrderCreateIn) {
    return http.request<OrderDetailOut>({ url: '/admin/production/orders', method: 'POST', data })
  },
  updateOrder(id: number, data: OrderUpdateIn) {
    return http.request<OrderDetailOut>({ url: `/admin/production/orders/${id}`, method: 'PUT', data })
  },
  downloadOrderImportTemplate() {
    return http.downloadBlob({
      url: '/admin/production/orders/import-template',
      method: 'GET',
    })
  },
  importOrdersExcel(payload: {
    file: File
    customer_id: number
    order_name: string
    due_date?: string
    remark?: string
    order_code?: string
    auto_create_product?: boolean
    auto_create_sku?: boolean
    default_unit_price?: number
  }) {
    const form = new FormData()
    form.append('file', payload.file)
    form.append('customer_id', String(payload.customer_id))
    form.append('order_name', payload.order_name)
    if (payload.due_date) form.append('due_date', payload.due_date)
    if (payload.remark) form.append('remark', payload.remark)
    if (payload.order_code) form.append('order_code', payload.order_code)
    form.append('auto_create_product', payload.auto_create_product !== false ? '1' : '0')
    form.append('auto_create_sku', payload.auto_create_sku !== false ? '1' : '0')
    const price = Number(payload.default_unit_price)
    form.append('default_unit_price', String(Number.isFinite(price) && price >= 0 ? price : 1))
    return http.request<OrderImportResult>({
      url: '/admin/production/orders/import-excel',
      method: 'POST',
      data: form,
    })
  },
}
