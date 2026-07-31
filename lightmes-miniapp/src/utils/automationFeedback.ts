export function formatAutomationFeedback(res: {
  automation_plan_id?: number | null
  automation_pipeline_ran?: boolean
  pipeline_queued?: boolean
}): string | null {
  const parts: string[] = []
  if (res.automation_plan_id) {
    parts.push(`已自动创建计划 ID ${res.automation_plan_id}`)
  }
  if (res.automation_pipeline_ran) {
    parts.push('流水线已同步执行')
  }
  if (res.pipeline_queued) {
    parts.push('流水线已入队，请确保 Celery 已运行')
  }
  return parts.length ? parts.join('；') : null
}
