/**
 * 复制文本到剪贴板。
 * H5 常在 http 内网地址下运行（navigator.clipboard 不可用），故保留 execCommand 兜底。
 * 返回是否成功，调用方自行决定提示文案。
 */
export async function copyText(text: string): Promise<boolean> {
  if (!text) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 非安全上下文或权限被拒，走兜底
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const done = document.execCommand('copy')
    document.body.removeChild(ta)
    return done
  } catch {
    return false
  }
}
