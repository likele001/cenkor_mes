export function openPrintWindow(html: string, options?: { title?: string; autoPrint?: boolean }) {
  const title = options?.title || 'print'
  const autoPrint = Boolean(options?.autoPrint)

  const hasHtml = /<html[\s>]/i.test(html)
  const hasPageRule = /@page\s*\{/i.test(html)

  const commonCss = `
*{box-sizing:border-box}
html,body{padding:0;margin:0;color:#000;font-family:Arial,Helvetica,sans-serif;font-size:12px}
img,svg{max-width:100%}
table{width:100%;border-collapse:collapse}
thead{display:table-header-group}
tfoot{display:table-footer-group}
tr{page-break-inside:avoid}
.print-pagebreak{page-break-after:always}
@media print{
  body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
`

  const pageCss = hasPageRule ? '' : '@page{size:A4;margin:12mm}'

  let fullHtml = html
  if (!hasHtml) {
    fullHtml =
      '<!doctype html><html><head><meta charset="utf-8" />' +
      `<title>${title}</title>` +
      `<style>${pageCss}${commonCss}</style>` +
      '</head><body>' +
      html +
      '</body></html>'
  } else if (!/<style[\s>]/i.test(html)) {
    fullHtml = html.replace(/<\/head>/i, `<style>${pageCss}${commonCss}</style></head>`)
  } else {
    fullHtml = html
  }

  const w = window.open('', '_blank')
  if (!w) return null
  w.document.open()
  w.document.write(fullHtml)
  w.document.close()
  w.focus()

  if (autoPrint) {
    const doPrint = () => {
      try {
        w.print()
      } catch {}
    }
    w.addEventListener('load', () => setTimeout(doPrint, 50), { once: true })
    w.addEventListener('afterprint', () => {
      try {
        w.close()
      } catch {}
    })
    setTimeout(doPrint, 200)
  }
  return w
}
