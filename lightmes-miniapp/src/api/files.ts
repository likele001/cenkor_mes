import { getToken } from './request'

export type UploadResult = { id: number; url?: string; file_id?: number; play_url?: string }

export function uploadFile(filePath: string, purpose = 'report_media'): Promise<UploadResult> {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const token = getToken()
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${base.replace(/\/$/, '')}/files/upload?purpose=${encodeURIComponent(purpose)}`,
      filePath,
      name: 'file',
      header: token ? { Authorization: `Bearer ${token}`, token } : {},
      success(res) {
        try {
          const body = JSON.parse(res.data) as { code: number; msg: string; data: UploadResult }
          if (body.code === 200) {
            resolve(body.data)
            return
          }
          reject(new Error(body.msg || '上传失败'))
        } catch {
          reject(new Error('上传响应解析失败'))
        }
      },
      fail: (e) => reject(new Error(e.errMsg || '上传失败')),
    })
  })
}

export function fileUrl(id: number | string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${base.replace(/\/$/, '')}/files/${id}`
}
