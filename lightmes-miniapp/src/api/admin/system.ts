import { apiGet, apiPost, apiPostQuery, apiPut } from '../request'

export const systemAdminApi = {
  listDictTypes: () => apiGet<{ items: { id: number; code: string; name: string; is_active?: boolean }[] }>('/admin/dictionary/types', undefined, true),
  createDictType: (code: string, name: string) => apiPostQuery('/admin/dictionary/types', { code, name }, true),
  listDictItems: (typeId: number) =>
    apiGet<{ items: { id: number; label: string; value: string; sort_order?: number; is_active?: boolean }[] }>(
      `/admin/dictionary/types/${typeId}/items`,
      undefined,
      true,
    ),
  createDictItem: (typeId: number, label: string, value: string, sort_order = 0) =>
    apiPostQuery(`/admin/dictionary/types/${typeId}/items`, { label, value, sort_order }, true),
  listUsers: (p?: Record<string, unknown>) => apiGet<{ items: UserRow[] }>('/admin/system/users', p, true),
  getUser: (id: number) => apiGet<UserRow>(`/admin/system/users/${id}`, undefined, true),
  createUser: (data: object) => apiPost<UserRow>('/admin/system/users', data, true),
  updateUser: (id: number, data: object) => apiPut<UserRow>(`/admin/system/users/${id}`, data, true),
  listRoles: () => apiGet<{ items: { id: number; code: string; name: string }[] }>('/admin/system/roles', { limit: 200 }, true),
  listDepartments: () => apiGet<{ items: { id: number; code: string; name: string }[] }>('/admin/system/departments', { limit: 200 }, true),
  getWechatMiniapp: () => apiGet<{ app_id?: string; app_secret_masked?: string; configured?: boolean }>('/admin/system/wechat-miniapp', undefined, true),
  saveWechatMiniapp: (data: { app_id?: string; app_secret?: string | null; clear_app_id?: boolean }) =>
    apiPut('/admin/system/wechat-miniapp', data, true),
}

export type UserRow = {
  id: number
  username: string
  full_name?: string | null
  department_id?: number | null
  is_active?: boolean
  roles?: { id: number; code: string; name: string }[]
}
