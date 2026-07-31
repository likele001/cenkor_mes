import { apiDel, apiGet, apiPost, apiPut, apiPutQuery } from '../request'

export async function crudList(path: string, params?: Record<string, unknown>) {
  const r = await apiGet<{ items?: unknown[] } | unknown[]>(path, params, true)
  if (Array.isArray(r)) return r
  return (r as { items?: unknown[] })?.items ?? []
}

export async function crudGet(path: string) {
  return apiGet<Record<string, unknown>>(path, undefined, true)
}

export async function crudCreate(path: string, data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>(path, data, true)
}

export async function crudUpdate(path: string, data: Record<string, unknown>, asQuery = false) {
  if (asQuery) return apiPutQuery<Record<string, unknown>>(path, data, true)
  return apiPut<Record<string, unknown>>(path, data, true)
}

export async function crudRemove(path: string) {
  return apiDel<void>(path, true)
}
