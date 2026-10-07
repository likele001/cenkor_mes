import { http } from '@/utils/http'

/** 功能市场应用项（hub 目录 + 已购授权 + 本地已装 合并视图） */
export interface MarketApp {
  key: string
  name: string
  description: string
  icon: string
  category: string
  latest_version: string
  price: number | null
  licensed: boolean
  license_state: string
  license_expires_at: string | null
  bound_instances: number
  max_instances: number
  installed: boolean
  installed_version: string
  enabled: boolean
}

/** 连接状态（hub 地址 / 绑定账号） */
export interface MarketStatus {
  hub_url: string
  product: string
  bound: boolean
  account: string
  instance_uid: string
}

/** 设备码绑定：发起后返回给用户去门户确认的信息 */
export interface BindStartResult {
  user_code: string
  verification_uri: string
  verification_uri_complete?: string
  expires_in: number
  interval: number
}

/** 设备码轮询结果 */
export interface BindPollResult {
  status: 'idle' | 'pending' | 'approved' | 'expired' | 'denied' | 'consumed' | 'error'
  account?: string
  message?: string
}

/** 连接状态 */
export function getMarketStatus() {
  return http.get<MarketStatus>('/admin/market/status')
}

/** 保存 hub 地址 */
export function saveMarketHub(hubUrl: string) {
  return http.put<{ message: string; hub_url: string }>('/admin/market/hub', { hub_url: hubUrl })
}

/** 发起绑定：向 hub 申请一次性绑定码 */
export function bindStart() {
  return http.post<BindStartResult>('/admin/market/bind/start')
}

/** 轮询绑定结果 */
export function bindPoll() {
  return http.get<BindPollResult>('/admin/market/bind/poll')
}

/** 取消当前未完成的绑定 */
export function bindCancel() {
  return http.post<{ message: string }>('/admin/market/bind/cancel')
}

/** 解绑本实例（通知 hub 吊销令牌并清理本地凭证） */
export function bindUnbind() {
  return http.post<{ message: string }>('/admin/market/bind/unbind')
}

/** 应用列表（hub 目录 + 已购 + 本地已装） */
export function getMarketApps() {
  return http.get<{
    items: MarketApp[]
    hub_url: string
    bound: boolean
    account: string
  }>('/admin/market/apps')
}

/** 安装应用（需已持授权；热生效） */
export function installMarketApp(appKey: string) {
  return http.post<{ message: string; key: string; version: string; path: string; hot_loaded: boolean }>(
    '/admin/market/install',
    { app_key: appKey },
  )
}

/** 卸载应用（热生效） */
export function uninstallMarketApp(appKey: string) {
  return http.post<{ message: string; key: string }>('/admin/market/uninstall', { app_key: appKey })
}
