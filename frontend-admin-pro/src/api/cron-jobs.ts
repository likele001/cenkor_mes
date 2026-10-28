// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type CronJobOut = {
  id: number
  name: string
  task_name: string
  description: string | null
  enabled: boolean
  is_system: boolean
  cron_minute: string
  cron_hour: string
  cron_day_of_month: string
  cron_month_of_year: string
  cron_day_of_week: string
  last_run_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type CronJobListOut = {
  items: CronJobOut[]
  /** SaaS 模式下 Worker/Beat 重启收敛平台运维 */
  saas_mode?: boolean
}

export type WorkerStatusOut = {
  ok: boolean
  workers: Array<{
    hostname: string
    active_count: number
    active_tasks: Array<{ name: string | null; time_start: number | null }>
  }>
  /** 托管的主机名前缀（CELERY_WORKER_PREFIX）；空 = 未启用管理 */
  prefix?: string
  configured?: boolean
  /** systemd 单元名，用于离线提示 */
  service?: string
  server_time?: string
  error?: string
}

export type BeatStatusOut = {
  /** ActiveState === 'active' */
  active: boolean
  /** systemd ActiveState：active / inactive / failed / unknown / disabled */
  state: string
  started_at: string | null
  uptime_seconds: number | null
  /** systemd 单元名（BEAT_SERVICE_NAME） */
  unit: string
  configured?: boolean
  /** 单元是否已安装（LoadState != not-found）；systemctl 异常时为 null */
  installed?: boolean | null
  load_state?: string
}

export const cronJobsApi = {
  list() {
    return http.request<CronJobListOut>({
      url: '/admin/cron-jobs',
      method: 'GET',
    })
  },
  update(id: number, payload: Partial<CronJobOut>) {
    return http.request<{ data: CronJobOut; msg: string }>({
      url: `/admin/cron-jobs/${id}`,
      method: 'PUT',
      data: payload,
    })
  },
  reload() {
    return http.request<{ msg: string }>({
      url: '/admin/cron-jobs/reload',
      method: 'POST',
    })
  },
  workerStatus() {
    return http.request<WorkerStatusOut>({
      url: '/admin/cron-jobs/worker/status',
      method: 'GET',
    })
  },
  workerRestart() {
    return http.request<{ ok: boolean; hosts: string[] }>({
      url: '/admin/cron-jobs/worker/restart',
      method: 'POST',
    })
  },
  beatStatus() {
    return http.request<BeatStatusOut>({
      url: '/admin/cron-jobs/beat/status',
      method: 'POST',
    })
  },
  beatRestart() {
    return http.request<{ ok: boolean; unit: string; started_at?: string }>({
      url: '/admin/cron-jobs/beat/restart',
      method: 'POST',
      // 后端写信号后轮询等待新进程上线（最多约 60s），放长客户端超时避免误报
      timeout: 90000,
    })
  },
}
