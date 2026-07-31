import { apiDel, apiGet, apiPost, apiPut } from '../request'

export type BomItem = { id?: number; material_id: number; qty_per: number; remark?: string | null }
export type BomOut = {
  id: number
  scope: string
  scope_label?: string
  sku_id?: number | null
  product_id?: number | null
  name?: string | null
  version?: number
  remark?: string | null
  is_active?: boolean
  items?: BomItem[]
}

export type ProcessRouteStep = { seq: number; process_id: number }
export type ProcessRouteOut = {
  id: number
  product_id: number
  name: string
  is_default?: boolean
  is_active?: boolean
  steps?: ProcessRouteStep[]
}

export const masterAdminApi = {
  listBoms: (p?: Record<string, unknown>) => apiGet<{ items: BomOut[] }>('/admin/master/boms', p, true),
  getBom: (id: number) => apiGet<BomOut>(`/admin/master/boms/${id}`, undefined, true),
  bomFormOptions: () =>
    apiGet<{ skus?: { id: number; display_label?: string; name?: string; code?: string }[]; products?: { id: number; name: string; code?: string }[] }>(
      '/admin/master/boms/meta/form-options',
      undefined,
      true,
    ),
  createBom: (data: object) => apiPost<BomOut>('/admin/master/boms', data, true),
  updateBom: (id: number, data: object) => apiPut<BomOut>(`/admin/master/boms/${id}`, data, true),
  disableBom: (id: number) => apiDel(`/admin/master/boms/${id}`, true),
  listMaterials: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/master/materials', { limit: 300 }, true),
  listProducts: () => apiGet<{ items: { id: number; name: string; code?: string; display_name?: string }[] }>('/admin/master/products', { limit: 200 }, true),
  listProcesses: () => apiGet<{ items: { id: number; name: string; code?: string }[] }>('/admin/master/processes', { limit: 200 }, true),
  listProcessRoutes: (p?: Record<string, unknown>) => apiGet<{ items: ProcessRouteOut[] }>('/admin/master/process-routes', p, true),
  getProcessRoute: (id: number) => apiGet<ProcessRouteOut>(`/admin/master/process-routes/${id}`, undefined, true),
  createProcessRoute: (data: object) => apiPost<ProcessRouteOut>('/admin/master/process-routes', data, true),
  updateProcessRoute: (id: number, data: object) => apiPut<ProcessRouteOut>(`/admin/master/process-routes/${id}`, data, true),
  disableProcessRoute: (id: number) => apiDel(`/admin/master/process-routes/${id}`, true),
}
