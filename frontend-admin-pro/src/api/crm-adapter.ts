import { http } from '@/utils/http'

export type CrmAdapterStatusMap = Record<string, string>

export type CrmAdapterConfig = {
  crm_base_url: string
  connection_id: string
  api_key: string
  status_map: CrmAdapterStatusMap
  enabled: boolean
  sign_window: number
  configured: boolean
}

export type CrmInboundOrderItem = {
  product_name: string
  spec?: string
  quantity: number
  unit_price?: number
}

export type CrmInboundOrder = {
  id: number
  order_code: string
  customer_name: string
  items: CrmInboundOrderItem[]
  delivery_date: string | null
  remark: string
  status: string
  mes_order_id: number | null
  created_at: string
  updated_at: string
}

export type UpdateStatusResult = {
  updated: boolean
  notified: boolean
  status: string
  order_code: string
}

export type CrmProductMap = {
  id: number
  crm_product_name: string
  crm_spec: string
  mes_product_id: number
  mes_sku_id: number
  created_at: string
}

export type SkuOption = {
  id: number
  code: string
  name: string
  spec: string | null
  product_id: number
  product_name?: string | null
}

export const crmAdapterApi = {
  getConfig() {
    return http.request<CrmAdapterConfig>({ url: '/crm-adapter/config', method: 'GET' })
  },
  saveConfig(data: Partial<CrmAdapterConfig>) {
    return http.request<{ saved: boolean }>({ url: '/crm-adapter/config', method: 'PUT', data })
  },
  listOrders() {
    return http.request<CrmInboundOrder[]>({ url: '/crm-adapter/orders', method: 'GET' })
  },
  updateOrderStatus(orderCode: string, status: string) {
    return http.request<UpdateStatusResult>({
      url: '/crm-adapter/orders/' + orderCode + '/status',
      method: 'POST',
      data: { status },
    })
  },
  listProductMaps() {
    return http.request<CrmProductMap[]>({ url: '/crm-adapter/product-maps', method: 'GET' })
  },
  createProductMap(data: { crm_product_name: string; crm_spec: string; mes_sku_id: number }) {
    return http.request<{ created: boolean; id: number }>({
      url: '/crm-adapter/product-maps',
      method: 'POST',
      data,
    })
  },
  deleteProductMap(id: number) {
    return http.request<{ deleted: boolean }>({
      url: '/crm-adapter/product-maps/' + id,
      method: 'DELETE',
    })
  },
  listSkus(keyword?: string) {
    const qs = keyword ? '&keyword=' + encodeURIComponent(keyword) : ''
    return http.request<{ items: SkuOption[] }>({
      url: '/admin/master/skus?limit=200' + qs,
      method: 'GET',
    })
  },
}
