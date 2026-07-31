import { useI18n } from 'vue-i18n'

export function useCustomerLabels() {
  const { t } = useI18n()

  function orderStatusLabel(s: string) {
    const key = `customer.status.${s}` as const
    const mapped = t(key)
    return mapped !== key ? mapped : s || '—'
  }

  function statementStatusLabel(s: string) {
    const map: Record<string, string> = {
      draft: t('customer.statements.draft'),
      confirmed: t('customer.statements.confirmed'),
      paid: t('customer.statements.paid'),
    }
    return map[s] || s || '—'
  }

  function saleTypeLabel(s: string) {
    const map: Record<string, string> = {
      return: t('customer.afterSale.returnGoods'),
      exchange: t('customer.afterSale.exchange'),
      repair: t('customer.afterSale.repair'),
      other: t('customer.afterSale.other'),
    }
    return map[s] || s
  }

  function saleStatusLabel(s: string) {
    const map: Record<string, string> = {
      pending: t('customer.afterSale.pending'),
      processing: t('customer.afterSale.processing'),
      done: t('customer.afterSale.done'),
      rejected: t('customer.afterSale.rejected'),
    }
    return map[s] || s
  }

  function toPercent(v: number | null | undefined) {
    if (typeof v !== 'number') return 0
    const p = Math.round(v * 10000) / 100
    return Math.min(100, Math.max(0, p))
  }

  return {
    orderStatusLabel,
    statementStatusLabel,
    saleTypeLabel,
    saleStatusLabel,
    toPercent,
  }
}
