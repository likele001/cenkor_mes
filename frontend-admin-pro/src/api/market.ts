import { http } from '@/utils/http'

/** 功能市场应用项（hub 目录 + 已购授权 + 本地已装 合并视图） */
export interface MarketApp {
  key: string
  name: string
  description: string
  icon: string
  category: string
  latest_version: string
  /** 更新弹窗展示用：本版更新日志 / 最低宿主版本 / 包内 schema_version */
  changelog?: string
  min_core_version?: string
  schema_version?: number | null
  price: number | null
  licensed: boolean
  license_state: string
  license_expires_at: string | null
  bound_instances: number
  max_instances: number
  installed: boolean
  installed_version: string
  enabled: boolean
  /** 生命周期登记（registry.json）字段 */
  status?: string
  health?: string
  previous_version?: string
  last_operation?: string
  last_error?: string
  data_policy?: string
  worker_restart_required?: boolean
  multi_worker?: boolean
  has_backup?: boolean
}

/** 连接状态（hub 地址 / 绑定账号 / 已购概况） */
export interface MarketStatus {
  hub_url: string
  product: string
  bound: boolean
  account: string
  instance_uid: string
  /** 最近一次授权快照同步时 hub 是否可达；null = 还没同步过（未绑定或刚重启） */
  hub_reachable?: boolean | null
  /** 已购且仍在有效期内的扩展数（含未安装的） */
  purchased_count?: number
  /** 已装、且 hub 上有更新版本的扩展数；hub 未给版本号时不计入 */
  updatable_count?: number
  /** 最早到期的授权（ISO 字符串）；全部为买断则 null */
  nearest_expiry?: string | null
  /** 以上统计所依据的快照时间 */
  snapshot_synced_at?: string
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

/** 卸载应用（热生效）。purge=true 时要求 confirmKey 与 key 一致（彻底清除不可逆） */
export function uninstallMarketApp(
  appKey: string,
  opts: { purge?: boolean; confirmKey?: string } = {},
) {
  return http.post<{ message: string; key: string; policy: string; trash?: string }>(
    '/admin/market/uninstall',
    { app_key: appKey, purge: Boolean(opts.purge), confirm_key: opts.confirmKey || '' },
  )
}

/** 软插：清 override，跑迁移/补权限，重新挂载 */
export function enableMarketApp(appKey: string) {
  return http.post<{ message: string; key: string }>(`/admin/market/apps/${appKey}/enable`)
}

/** 软拔：停门禁、摘路由/事件/任务，保留文件与数据 */
export function disableMarketApp(appKey: string) {
  return http.post<{ message: string; key: string }>(`/admin/market/apps/${appKey}/disable`)
}

/** 回滚到最近备份版本 */
export function rollbackMarketApp(appKey: string) {
  return http.post<{ message: string; from_version: string; to_version: string }>(
    `/admin/market/apps/${appKey}/rollback`,
  )
}

/** 修复：目录丢失/迁移中断/权限丢失 */
export function repairMarketApp(appKey: string) {
  return http.post<{ message: string; key: string }>(`/admin/market/apps/${appKey}/repair`)
}

/** 生命周期审计（谁、何时、版本变化、结果、耗时、包 SHA） */
export interface LifecycleLog {
  at: string
  operation: string
  key: string
  from_version?: string
  to_version?: string
  result?: string
  error?: string
  actor?: string
  elapsed_ms?: number
  sha256?: string
}

export function getLifecycleLogs(params: { limit?: number; key?: string } = {}) {
  return http.get<{ items: LifecycleLog[] }>('/admin/market/lifecycle/logs', { params })
}
