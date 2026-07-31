import { ref } from 'vue'
import { uploadFile } from '@/api/files'
import { chooseMediaCompat } from '@/utils/chooseMedia'
import { apiGet } from '@/api/request'

export type ReportMediaSettings = {
  max_count?: number
  allow_video?: boolean
}

export function useUpload() {
  const uploading = ref(false)
  const attachmentIds = ref<number[]>([])
  const attachmentUrls = ref<Record<number, string>>({})

  async function loadMediaSettings() {
    try {
      return await apiGet<ReportMediaSettings>('/h5/settings/report-media')
    } catch {
      return { max_count: 5, allow_video: true }
    }
  }

  async function pickAndUpload(max = 5): Promise<number[]> {
    const remaining = max - attachmentIds.value.length
    if (remaining <= 0) {
      uni.showToast({ title: `最多上传 ${max} 个文件`, icon: 'none' })
      return attachmentIds.value
    }

    uploading.value = true
    try {
      console.log('[useUpload] picking media, remaining:', remaining)
      const res = await chooseMediaCompat({
        count: remaining,
        mediaType: ['image'],
        sourceType: ['camera', 'album'],
      })

      console.log('[useUpload] got files:', res.tempFiles.length)
      const ids: number[] = []
      for (const f of res.tempFiles) {
        console.log('[useUpload] uploading:', f.tempFilePath)
        const up = await uploadFile(f.tempFilePath, 'report_media')
        const id = up.id ?? up.file_id
        if (id) {
          ids.push(Number(id))
          if (up.play_url) {
            attachmentUrls.value[Number(id)] = up.play_url
          }
          console.log('[useUpload] uploaded, id:', id, 'play_url:', up.play_url)
        }
      }
      attachmentIds.value.push(...ids)
      uni.showToast({ title: `上传成功 ${ids.length} 张`, icon: 'success' })
      return ids
    } catch (e: any) {
      console.error('[useUpload] upload error:', e)
      if (e?.errMsg?.includes('cancel')) {
        // 用户取消，不提示
      } else {
        uni.showToast({ title: e?.errMsg || e?.message || '选择/上传失败', icon: 'none' })
      }
      throw e
    } finally {
      uploading.value = false
    }
  }

  function clearAttachments() {
    attachmentIds.value = []
    attachmentUrls.value = {}
  }

  function attachmentIdsStr(): string {
    return attachmentIds.value.join(',')
  }

  return { uploading, attachmentIds, attachmentUrls, loadMediaSettings, pickAndUpload, clearAttachments, attachmentIdsStr }
}
