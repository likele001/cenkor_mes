import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type ProductOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  display_name?: string
  category: string | null
  unit: string | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type SkuOut = {
  id: number
  tenant_id: number
  product_id: number
  code: string
  name: string
  color: string | null
  material: string | null
  spec: string | null
  remark: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  /** 后端拼接：产品展示名 · 型号说明 */
  product_name?: string | null
  sku_display_name?: string | null
  display_label?: string | null
}

export type ProcessOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  display_name?: string | null
  workshop: string | null
  std_minutes: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type ProcessRouteOut = {
  id: number
  tenant_id: number
  product_id: number
  name: string
  is_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  steps: { id: number; tenant_id: number; route_id: number; seq: number; process_id: number }[]
}

export type ProcessPriceRef = {
  id: number
  code: string
  name: string
  display_name?: string
  product_id?: number
}

export type ProcessPriceOut = {
  id: number
  tenant_id: number
  sku_id: number
  process_id: number
  unit_price: string
  is_active: boolean
  created_at: string
  updated_at: string
  sku?: (ProcessPriceRef & { display_label?: string; product_name?: string }) | null
  product?: ProcessPriceRef | null
  process?: { id: number; code: string; name: string; display_name?: string } | null
}

export type ProcessPriceMatrixRow = {
  process_id: number
  process_code: string
  process_name: string
  process_display_name?: string
  price_id: number | null
  unit_price: number | null
  is_active: boolean
}

export type ProcessPriceMatrixOut = {
  sku: { id: number; code: string; name: string; display_label?: string; product_id: number } | null
  product: { id: number; code: string; name: string; display_name?: string } | null
  route_name: string | null
  route_source: string
  rows: ProcessPriceMatrixRow[]
}

export type SkuBatchProcessOut = {
  process_id: number
  process_code: string
  process_name: string
  process_display_name?: string
}

export type SkuBatchTemplateOut = {
  product: { id: number; code: string; name: string; display_name?: string } | null
  route_name: string | null
  route_source: string
  processes: SkuBatchProcessOut[]
  existing_names: string[]
}

export type SkuBatchWithPricesResult = {
  added: number
  skipped: number
  prices_created: number
  prices_updated: number
  items: { id: number; code: string; name: string }[]
}

export const masterApi = {
  listProducts(params: any) {
    return http.request<ListResp<ProductOut>>({ url: '/admin/master/products', method: 'GET', params })
  },
  createProduct(data: any) {
    return http.request<ProductOut>({ url: '/admin/master/products', method: 'POST', data })
  },
  updateProduct(id: number, data: any) {
    return http.request<ProductOut>({ url: `/admin/master/products/${id}`, method: 'PUT', data })
  },
  disableProduct(id: number) {
    return http.request<void>({ url: `/admin/master/products/${id}`, method: 'DELETE' })
  },

  listSkus(params: any) {
    return http.request<ListResp<SkuOut>>({ url: '/admin/master/skus', method: 'GET', params })
  },
  createSku(data: any) {
    return http.request<SkuOut>({ url: '/admin/master/skus', method: 'POST', data })
  },
  updateSku(id: number, data: any) {
    return http.request<SkuOut>({ url: `/admin/master/skus/${id}`, method: 'PUT', data })
  },
  disableSku(id: number) {
    return http.request<void>({ url: `/admin/master/skus/${id}`, method: 'DELETE' })
  },
  importSkus(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.request<{ total: number; success: number; errors: { row: number; message: string }[] }>({
      url: '/admin/master/skus/import-excel',
      method: 'POST',
      data: form,
    })
  },
  getSkuBatchTemplate(productId: number) {
    return http.request<SkuBatchTemplateOut>({
      url: '/admin/master/skus/batch-template',
      method: 'GET',
      params: { product_id: productId },
    })
  },
  batchCreateSkusWithPrices(data: {
    product_id: number
    items: {
      code?: string | null
      name: string
      color?: string | null
      material?: string | null
      spec?: string | null
      remark?: string | null
      is_active?: boolean
      prices: { process_id: number; unit_price: string | number | null; is_active?: boolean }[]
    }[]
  }) {
    return http.request<SkuBatchWithPricesResult>({
      url: '/admin/master/skus/batch-with-prices',
      method: 'POST',
      data,
    })
  },

  listProcesses(params: any) {
    return http.request<ListResp<ProcessOut>>({ url: '/admin/master/processes', method: 'GET', params })
  },
  createProcess(data: any) {
    return http.request<ProcessOut>({ url: '/admin/master/processes', method: 'POST', data })
  },
  updateProcess(id: number, data: any) {
    return http.request<ProcessOut>({ url: `/admin/master/processes/${id}`, method: 'PUT', data })
  },
  disableProcess(id: number) {
    return http.request<void>({ url: `/admin/master/processes/${id}`, method: 'DELETE' })
  },
  getProcessSkills(processId: number) {
    return http.request<{ items: Array<{ id: number; code: string; name: string }> }>({
      url: `/admin/master/processes/${processId}/skills`,
      method: 'GET',
    })
  },
  setProcessSkills(processId: number, skill_ids: number[]) {
    return http.request<{ skill_ids: number[]; items: Array<{ id: number; code: string; name: string }> }>({
      url: `/admin/master/processes/${processId}/skills`,
      method: 'PUT',
      data: { skill_ids },
    })
  },

  listRoutes(params: any) {
    return http.request<ListResp<ProcessRouteOut>>({ url: '/admin/master/process-routes', method: 'GET', params })
  },
  createRoute(data: any) {
    return http.request<ProcessRouteOut>({ url: '/admin/master/process-routes', method: 'POST', data })
  },
  updateRoute(id: number, data: any) {
    return http.request<ProcessRouteOut>({ url: `/admin/master/process-routes/${id}`, method: 'PUT', data })
  },
  disableRoute(id: number) {
    return http.request<void>({ url: `/admin/master/process-routes/${id}`, method: 'DELETE' })
  },

  listPrices(params: any) {
    return http.request<ListResp<ProcessPriceOut>>({ url: '/admin/master/process-prices', method: 'GET', params })
  },
  getPriceMatrix(skuId: number) {
    return http.request<ProcessPriceMatrixOut>({
      url: '/admin/master/process-prices/matrix',
      method: 'GET',
      params: { sku_id: skuId },
    })
  },
  batchSavePrices(data: { sku_id: number; items: { process_id: number; unit_price: string | number | null; is_active?: boolean }[] }) {
    return http.request<{ created: number; updated: number; sku_id: number }>({
      url: '/admin/master/process-prices/batch',
      method: 'POST',
      data,
    })
  },
  createPrice(data: any) {
    return http.request<ProcessPriceOut>({ url: '/admin/master/process-prices', method: 'POST', data })
  },
  updatePrice(id: number, data: any) {
    return http.request<ProcessPriceOut>({ url: `/admin/master/process-prices/${id}`, method: 'PUT', data })
  },
  disablePrice(id: number) {
    return http.request<void>({ url: `/admin/master/process-prices/${id}`, method: 'DELETE' })
  },

  exportProducts(params?: any) {
    return http.downloadBlob({ url: '/admin/master/products/export', method: 'GET', params })
  },
  exportSkus(params?: any) {
    return http.downloadBlob({ url: '/admin/master/skus/export', method: 'GET', params })
  },
  exportProcesses(params?: any) {
    return http.downloadBlob({ url: '/admin/master/processes/export', method: 'GET', params })
  },
  exportProcessPrices(params?: any) {
    return http.downloadBlob({ url: '/admin/master/process-prices/export', method: 'GET', params })
  },

}

