import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type DictTypeOut = { id: number; code: string; name: string; is_active: boolean }

export type DictItemOut = { id: number; dict_type_id: number; label: string; value: string; sort_order: number; is_active: boolean }

export const dictionaryApi = {
  /** 字典类型列表 */
  listTypes(params?: { keyword?: string; offset?: number; limit?: number }) {
    return http.request<ListResp<DictTypeOut>>({ url: '/admin/dictionary/types', method: 'GET', params })
  },
  /** 新增字典类型 */
  createType(data: { code: string; name: string }) {
    return http.request<DictTypeOut>({ url: '/admin/dictionary/types', method: 'POST', data })
  },
  /** 字典项列表 */
  listItems(dictTypeId: number, params?: { offset?: number; limit?: number }) {
    return http.request<ListResp<DictItemOut>>({ url: `/admin/dictionary/types/${dictTypeId}/items`, method: 'GET', params })
  },
  /** 新增字典项 */
  createItem(dictTypeId: number, data: { label: string; value: string; sort_order: number }) {
    return http.request<DictItemOut>({ url: `/admin/dictionary/types/${dictTypeId}/items`, method: 'POST', data })
  },
  /** 删除字典项 */
  deleteItem(dictTypeId: number, itemId: number) {
    return http.request<void>({ url: `/admin/dictionary/types/${dictTypeId}/items/${itemId}`, method: 'DELETE' })
  },
}
