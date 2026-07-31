import { apiPostForm } from '@/utils/http'

export type UploadRespData = {
  id?: number
  url?: string
  content_type?: string
  size?: number
  original_filename?: string
  file_id?: number
  mime_type?: string
}

export async function uploadFile(file: File, purpose?: 'report_media') {
  const form = new FormData()
  form.append('file', file)
  const q = purpose ? `?purpose=${purpose}` : ''
  return apiPostForm<UploadRespData>(`/files/upload${q}`, form)
}

/** 报工/审核现场拍摄（受平台时长、大小限制） */
export function uploadReportMedia(file: File) {
  return uploadFile(file, 'report_media')
}
