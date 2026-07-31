import { i18n } from '@/locales'

/** 解析订单/计划自动化 API 返回，生成用户提示文案 */
export function formatAutomationFeedback(res: {
  automation_plan_id?: number | null
  automation_pipeline_ran?: boolean
  pipeline_queued?: boolean
}): string | null {
  const t = i18n.global.t
  const parts: string[] = []
  if (res.automation_plan_id) {
    parts.push(t('utils.automation.autoCreatedPlan', { id: res.automation_plan_id }))
  }
  if (res.automation_pipeline_ran) {
    parts.push(t('utils.automation.pipelineSynced'))
  }
  if (res.pipeline_queued) {
    parts.push(t('utils.automation.pipelineQueued'))
  }
  return parts.length ? parts.join('；') : null
}
