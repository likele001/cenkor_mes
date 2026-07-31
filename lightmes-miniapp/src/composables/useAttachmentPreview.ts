import { ref, watch } from 'vue'
import { getToken } from '@/api/request'
import { fileUrl } from '@/api/files'

export function useAttachmentPreview() {
  const previewMap = ref<Record<number, string>>({})
  const loadingIds = ref<Set<number>>(new Set())

  async function loadPreview(id: number) {
    if (previewMap.value[id] || loadingIds.value.has(id)) return
    loadingIds.value.add(id)
    try {
      const token = getToken()
      const res = await uni.downloadFile({
        url: fileUrl(id),
        header: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.statusCode === 200 && res.tempFilePath) {
        previewMap.value[id] = res.tempFilePath
      }
    } catch (e) {
      console.error('[preview] download failed:', id, e)
    } finally {
      loadingIds.value.delete(id)
    }
  }

  function loadPreviews(ids: number[]) {
    for (const id of ids) {
      if (!previewMap.value[id]) loadPreview(id)
    }
  }

  function clearPreviews() {
    previewMap.value = {}
  }

  return { previewMap, loadPreview, loadPreviews, clearPreviews }
}
