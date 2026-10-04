function u(t,a){const l=(a==null?void 0:a.title)||"print",n=!!(a!=null&&a.autoPrint),d=/<html[\s>]/i.test(t),c=/@page\s*\{/i.test(t),i=`
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
`,s=c?"":"@page{size:A4;margin:12mm}";let r=t;d?/<style[\s>]/i.test(t)?r=t:r=t.replace(/<\/head>/i,`<style>${s}${i}</style></head>`):r=`<!doctype html><html><head><meta charset="utf-8" /><title>${l}</title><style>${s}${i}</style></head><body>`+t+"</body></html>";const e=window.open("","_blank");if(!e)return null;if(e.document.open(),e.document.write(r),e.document.close(),e.focus(),n){const o=()=>{try{e.print()}catch{}};e.addEventListener("load",()=>setTimeout(o,50),{once:!0}),e.addEventListener("afterprint",()=>{try{e.close()}catch{}}),setTimeout(o,200)}return e}export{u as o};
