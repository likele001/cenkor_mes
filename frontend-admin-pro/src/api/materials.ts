import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type SupplierOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  contact_name: string | null
  phone: string | null
  address: string | null
  remark: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type MaterialOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  unit: string | null
  spec: string | null
  remark: string | null
  supplier_id: number | null
  sku_id: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export type BomItemOut = {
  id: number
  material_id: number
  material_code: string | null
  material_name: string | null
  qty_per: number
  remark: string | null
}

export type BomScope = 'sku' | 'product' | 'global'

export type BomProductOption = {
  id: number
  code: string
  name: string
  display_name: string
}

export type BomSkuOption = {
  id: number
  product_id: number
  code: string
  name: string
  color?: string | null
  material?: string | null
  spec?: string | null
  product_name?: string
  sku_display_name?: string
  display_label?: string
}

export type BomFormOptions = {
  skus: BomSkuOption[]
  products: BomProductOption[]
}

export type BomOut = {
  id: number
  tenant_id: number
  scope: BomScope
  scope_label?: string
  sku_id: number | null
  product_id: number | null
  sku_code: string | null
  sku_name: string | null
  product_code: string | null
  product_name: string | null
  name: string | null
  version: number
  remark: string | null
  is_default: boolean
  is_active: boolean
  created_by: number | null
  created_at: string
  updated_at: string
  items: BomItemOut[]
}

export type BomItemIn = {
  material_id: number
  qty_per: number
  remark?: string | null
}

export type BomCreateIn = {
  scope?: BomScope
  sku_id?: number
  product_id?: number
  name?: string | null
  version?: number
  remark?: string | null
  is_default?: boolean
  items?: BomItemIn[]
}

export type BomUpdateIn = {
  version?: number | null
  remark?: string | null
  name?: string | null
  is_active?: boolean | null
  is_default?: boolean | null
  items?: BomItemIn[] | null
}

export const materialsApi = {
  listSuppliers(params: any) {
    return http.request<ListResp<SupplierOut>>({ url: '/admin/master/suppliers', method: 'GET', params })
  },
  createSupplier(data: any) {
    return http.request<SupplierOut>({ url: '/admin/master/suppliers', method: 'POST', data })
  },
  updateSupplier(id: number, data: any) {
    return http.request<SupplierOut>({ url: `/admin/master/suppliers/${id}`, method: 'PUT', data })
  },
  disableSupplier(id: number) {
    return http.request<void>({ url: `/admin/master/suppliers/${id}`, method: 'DELETE' })
  },

  listMaterials(params: any) {
    return http.request<ListResp<MaterialOut>>({ url: '/admin/master/materials', method: 'GET', params })
  },
  createMaterial(data: any) {
    return http.request<MaterialOut>({ url: '/admin/master/materials', method: 'POST', data })
  },
  updateMaterial(id: number, data: any) {
    return http.request<MaterialOut>({ url: `/admin/master/materials/${id}`, method: 'PUT', data })
  },
  disableMaterial(id: number) {
    return http.request<void>({ url: `/admin/master/materials/${id}`, method: 'DELETE' })
  },

  getBomFormOptions() {
    return http.request<BomFormOptions>({ url: '/admin/master/boms/meta/form-options', method: 'GET' })
  },
  listBoms(params: any) {
    return http.request<ListResp<BomOut>>({ url: '/admin/master/boms', method: 'GET', params })
  },
  createBom(data: BomCreateIn) {
    return http.request<BomOut>({ url: '/admin/master/boms', method: 'POST', data })
  },
  getBom(id: number) {
    return http.request<BomOut>({ url: `/admin/master/boms/${id}`, method: 'GET' })
  },
  updateBom(id: number, data: BomUpdateIn) {
    return http.request<BomOut>({ url: `/admin/master/boms/${id}`, method: 'PUT', data })
  },
  disableBom(id: number) {
    return http.request<void>({ url: `/admin/master/boms/${id}`, method: 'DELETE' })
  },
  copyBomToSku(bomId: number, skuId: number) {
    return http.request<BomOut>({
      url: `/admin/master/boms/${bomId}/copy-to-sku`,
      method: 'POST',
      data: { sku_id: skuId },
    })
  },
  resolveBomForSku(skuId: number) {
    return http.request<{ sku_id: number; source: string; bom: BomOut | null }>({
      url: `/admin/master/boms/resolve/${skuId}`,
      method: 'GET',
    })
  },

  exportSuppliers(params?: any) {
    return http.downloadBlob({ url: '/admin/master/suppliers/export', method: 'GET', params })
  },
  exportMaterials(params?: any) {
    return http.downloadBlob({ url: '/admin/master/materials/export', method: 'GET', params })
  },
  exportBoms(params?: any) {
    return http.downloadBlob({ url: '/admin/master/boms/export', method: 'GET', params })
  },
}

