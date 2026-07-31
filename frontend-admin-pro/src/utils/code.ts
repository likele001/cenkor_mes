import { systemApi } from '@/api/system'

/** 预览下一业务编号（不占用序号），失败时返回空串 */
export async function previewNextCode(bizType: string): Promise<string> {
  try {
    const res = await systemApi.nextCode(bizType)
    return res.code || ''
  } catch {
    return ''
  }
}

/** 提交用：空串视为留空由后端自动生成 */
export function codeForSubmit(raw: string | null | undefined): string | null {
  const s = (raw ?? '').trim()
  return s || null
}
