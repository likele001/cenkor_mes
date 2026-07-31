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

export const cronJobsApi = {
  list() {
    return http.request<{ data: { items: CronJobOut[] } }>({
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
}
