/**
 * CenkorMES 单用户版 tenant 兼容层
 * SaaS 版有完整的多租户路由逻辑，单用户版不需要租户前缀
 * 保留这些导出以避免各页面 import 报错
 */

export function getStoredTenantCode(): string {
  return ''
}

export function setStoredTenantCode(_code: string): void {
  // no-op for single-user
}

export function parseTenantFromPath(_path: string): string | null {
  return null
}

export function stripTenantPrefix(path: string): string {
  return path
}

export function tenantH5Path(path: string, _tenantCode?: string): string {
  return path.startsWith('/') ? path : `/${path}`
}

export function fixDuplicateH5Path(_path: string): string | null {
  return null
}
