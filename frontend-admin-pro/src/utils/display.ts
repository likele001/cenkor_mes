import { i18n } from '@/locales'

/**
 * 下拉/列表展示规范：主标题用名称（产品名、型号名、工序名等），编码放副行。
 * 优先使用后端 display_label / display_name。
 */

export type OrderSkuOption = {
  id: number
  code: string
  product_id?: number
  product_name?: string
  sku_name?: string
  display_label?: string
}

export function orderSkuOptionLabel(s: OrderSkuOption): string {
  if (s.display_label) return s.display_label
  const pn = (s.product_name || '').trim()
  const sn = (s.sku_name || (s as { name?: string }).name || '').trim()
  if (pn && sn) return `${pn} · ${sn}`
  return sn || pn || s.code || i18n.global.t('utils.display.skuFallback', { id: s.id })
}

export type MasterSkuLike = {
  id: number
  code: string
  name: string
  product_id?: number
  product_name?: string | null
  display_label?: string | null
  color?: string | null
  material?: string | null
  spec?: string | null
}

export function masterSkuOptionLabel(s: MasterSkuLike, productName?: string | null): string {
  const dl = (s.display_label || '').trim()
  if (dl) return dl
  const pn = (productName || s.product_name || '').trim()
  const sn = (s.name || '').trim()
  if (pn && sn) return `${pn} · ${sn}`
  return sn || pn || s.code || i18n.global.t('utils.display.skuFallback', { id: s.id })
}

export function masterSkuOptionSubline(s: MasterSkuLike): string {
  const parts: string[] = [i18n.global.t('utils.display.codePrefix', { code: s.code })]
  const attrs = [s.color, s.spec, s.material].map((x) => (x || '').trim()).filter(Boolean)
  if (attrs.length) parts.push(attrs.join(' · '))
  return parts.join(' · ')
}

export type NamedEntity = {
  id?: number
  code?: string | null
  name?: string | null
  display_name?: string | null
}

/** 产品下拉/列表 */
export function productOptionLabel(p: NamedEntity): string {
  return (p.display_name || p.name || p.code || '').trim() || i18n.global.t('utils.display.productFallback', { id: p.id })
}

export function productOptionSubline(p: NamedEntity): string {
  const code = (p.code || '').trim()
  return code ? i18n.global.t('utils.display.codePrefix', { code }) : ''
}

/** 工序下拉/列表 */
export function processOptionLabel(p: NamedEntity): string {
  return (p.display_name || p.name || p.code || '').trim() || i18n.global.t('utils.display.processFallback', { id: p.id })
}

export function processOptionSubline(p: NamedEntity): string {
  const code = (p.code || '').trim()
  return code ? i18n.global.t('utils.display.codePrefix', { code }) : ''
}

/** 物料下拉/列表 */
export function materialOptionLabel(m: NamedEntity): string {
  return (m.display_name || m.name || m.code || '').trim() || i18n.global.t('utils.display.materialFallback', { id: m.id })
}

export function materialOptionSubline(m: NamedEntity): string {
  const code = (m.code || '').trim()
  return code ? i18n.global.t('utils.display.codePrefix', { code }) : ''
}

/** 客户/供应商/仓库等 */
export function partyOptionLabel(p: NamedEntity): string {
  return (p.display_name || p.name || p.code || '').trim() || i18n.global.t('utils.display.partyFallback', { id: p.id })
}

export function partyOptionSubline(p: NamedEntity): string {
  const code = (p.code || '').trim()
  return code ? i18n.global.t('utils.display.codePrefix', { code }) : ''
}

/** 设备 */
export function equipmentOptionLabel(e: NamedEntity): string {
  return (e.display_name || e.name || e.code || '').trim() || i18n.global.t('utils.display.equipmentFallback', { id: e.id })
}

/** 工单/行内型号展示 */
export function skuRowLabel(row: {
  display_label?: string | null
  sku_display_label?: string | null
  sku?: MasterSkuLike | null
  product_name?: string | null
  sku_name?: string | null
}): string {
  const dl = (row.display_label || row.sku_display_label || row.sku?.display_label || '').trim()
  if (dl) return dl
  if (row.sku) return masterSkuOptionLabel(row.sku, row.product_name)
  const pn = (row.product_name || '').trim()
  const sn = (row.sku_name || '').trim()
  if (pn && sn) return `${pn} · ${sn}`
  return sn || pn || '—'
}

export function processRowLabel(row: {
  process?: NamedEntity | null
  process_name?: string | null
}): string {
  if (row.process) return processOptionLabel(row.process)
  return (row.process_name || '').trim() || '—'
}

export function codeSubline(code?: string | null): string {
  const c = (code || '').trim()
  return c ? i18n.global.t('utils.display.codePrefix', { code: c }) : ''
}
