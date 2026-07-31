import { apiGet } from '@/utils/http'

export type ReportMediaSettings = {
  max_video_seconds: number
  max_video_mb: number
  max_video_count: number
  max_photo_count: number
  camera_only: boolean
  max_video_bytes: number
}

export function getReportMediaSettings() {
  return apiGet<ReportMediaSettings>('/h5/settings/report-media')
}
