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
