import { i18n } from '@/locales'

/** 规范化 SVG，便于浏览器以图片方式渲染 */
export function normalizeQrSvg(svg: string): string {
  let s = (svg || '').trim()
  s = s.replace(/<\?xml[^?]*\?>\s*/gi, '')
  if (s && !/\sxmlns=/.test(s)) {
    s = s.replace(/<svg\b/i, '<svg xmlns="http://www.w3.org/2000/svg"')
  }
  return s
}

export function svgToDataUrl(svg: string): string {
  const s = normalizeQrSvg(svg)
  if (!s) return ''
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(s)}`
}

export function downloadSvgFile(svg: string, filename: string) {
  const blob = new Blob([normalizeQrSvg(svg)], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.svg') ? filename : `${filename}.svg`
  a.click()
  URL.revokeObjectURL(url)
}

/** 将 SVG 二维码导出为 PNG（弹窗展示、下载用） */
export async function downloadSvgAsPng(svg: string, filename: string, size = 400): Promise<void> {
  const src = svgToDataUrl(svg)
  if (!src) throw new Error(i18n.global.t('utils.qr.emptyData'))
  const img = new Image()
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error(i18n.global.t('utils.qr.imageLoadFailed')))
    img.src = src
  })
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error(i18n.global.t('utils.qr.canvasFailed'))
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, size, size)
  ctx.drawImage(img, 0, 0, size, size)
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob((b) => resolve(b), 'image/png'))
  if (!blob) throw new Error(i18n.global.t('utils.qr.exportPngFailed'))
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.png') ? filename : `${filename}.png`
  a.click()
  URL.revokeObjectURL(url)
}
