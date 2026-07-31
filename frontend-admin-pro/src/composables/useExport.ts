import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/utils/http'
import type { ExportJobOut } from '@/api/production'

export function useExport() {
  const exporting = ref(false)

  async function doExport(
    createJob: () => Promise<ExportJobOut>,
    filename: string,
  ) {
    if (exporting.value) return
    exporting.value = true
    try {
      const job = await createJob()
      const result = await pollExportJob(job.id)
      if (result.status === 'failed') {
        ElMessage.error(result.error_msg || '导出失败')
        return
      }
      const blob = await http.downloadBlob({
        url: `/files/${result.result_attachment_id}?download=true`,
        method: 'GET',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    } catch {
      /* http 已提示 */
    } finally {
      exporting.value = false
    }
  }

  return { exporting, doExport }
}

async function pollExportJob(jobId: number, maxRetries = 60): Promise<ExportJobOut> {
  for (let i = 0; i < maxRetries; i++) {
    const job = await http.request<ExportJobOut>({
      url: `/admin/export-jobs/${jobId}`,
      method: 'GET',
    })
    if (job.status === 'success' || job.status === 'failed') return job
    await new Promise((r) => setTimeout(r, 2000))
  }
  throw new Error('导出超时')
}
