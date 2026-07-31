import { useI18n } from 'vue-i18n'

export type StatusDomain =
  | 'order'
  | 'work_order'
  | 'task'
  | 'report'
  | 'report_unit'
  | 'purchase_order'
  | 'purchase_statement'
  | 'customer_statement'
  | 'crm_opportunity'
  | 'equipment'
  | 'shipment'
  | 'plan'
  | 'assignment'
  | 'mrp_run'
  | 'quotation'
  | 'subcontract'

export type TagType = '' | 'primary' | 'success' | 'warning' | 'danger' | 'info'

interface StatusDef {
  label: string
  type: TagType
}

const DOMAIN_CONFIG: Record<StatusDomain, Record<string, StatusDef>> = {
  order: {
    draft:           { label: 'production.orders.draft',           type: 'info' },
    pending_confirm: { label: 'production.orders.pendingConfirm',   type: 'warning' },
    confirmed:       { label: 'production.orders.confirmed',        type: 'warning' },
    producing:       { label: 'production.orders.producing',        type: 'primary' },
    completed:       { label: 'dashboard.kanban.completed',        type: 'success' },
    shipped:         { label: 'dashboard.kanban.shipped',          type: 'primary' },
    cancelled:       { label: 'dashboard.kanban.cancelled',        type: 'danger' },
  },
  work_order: {
    open:        { label: 'production.workOrders.statusOpen',      type: 'warning' },
    in_progress: { label: 'production.workOrders.statusInProgress', type: 'primary' },
    done:        { label: 'production.workOrders.statusDone',      type: 'success' },
    cancelled:   { label: 'production.workOrders.statusCancelled', type: 'danger' },
  },
  task: {
    pending: { label: 'production.tasks.pending', type: 'info' },
    working: { label: 'production.tasks.working', type: 'warning' },
    done:    { label: 'production.tasks.done',    type: 'success' },
  },
  report: {
    submitted:       { label: 'production.reports.pendingLeader',  type: 'warning' },
    leader_approved: { label: 'production.reports.pendingQc',     type: 'primary' },
    qc_approved:     { label: 'production.reports.passed',        type: 'success' },
    rejected:        { label: 'production.reports.rejected',      type: 'danger' },
  },
  report_unit: {
    draft:           { label: 'production.reportUnits.pendingReport', type: 'info' },
    submitted:       { label: 'production.reportUnits.pendingLeader', type: 'warning' },
    leader_approved: { label: 'production.reportUnits.pendingQc',    type: 'primary' },
    qc_approved:     { label: 'production.reportUnits.passed',       type: 'success' },
    rejected:        { label: 'production.common.rejected',           type: 'danger' },
  },
  purchase_order: {
    draft:             { label: 'purchase.orders.statusDraft',            type: 'info' },
    confirmed:         { label: 'purchase.orders.statusConfirmed',        type: 'warning' },
    partial_received:  { label: 'purchase.orders.statusPartialReceived', type: 'primary' },
    received:          { label: 'purchase.orders.statusReceived',         type: 'success' },
    canceled:          { label: 'purchase.orders.statusCanceled',         type: 'danger' },
  },
  purchase_statement: {
    draft:     { label: 'purchase.statements.statusDraft',     type: 'info' },
    confirmed: { label: 'purchase.statements.statusConfirmed', type: 'warning' },
    paid:      { label: 'purchase.statements.statusPaid',      type: 'success' },
  },
  customer_statement: {
    draft:     { label: 'finance.statements.draft',     type: 'info' },
    confirmed: { label: 'finance.statements.confirmed', type: 'warning' },
    paid:      { label: 'finance.statements.paid',      type: 'success' },
  },
  crm_opportunity: {
    open: { label: 'production.customers.statusOpen', type: 'warning' },
    won:  { label: 'production.customers.stageWon',  type: 'success' },
    lost: { label: 'production.customers.stageLost', type: 'danger' },
  },
  equipment: {
    active:  { label: 'production.equipment.normal',    type: 'success' },
    repair:  { label: 'production.equipment.repairing', type: 'warning' },
    retired: { label: 'production.equipment.retired',   type: 'info' },
  },
  shipment: {
    pending: { label: 'warehouse.shipments.statusPending', type: 'warning' },
    shipped: { label: 'warehouse.shipments.statusShipped', type: 'primary' },
    signed:  { label: 'warehouse.shipments.statusSigned',  type: 'success' },
  },
  plan: {
    planned:     { label: 'production.plans.planned',    type: 'info' },
    in_progress: { label: 'production.plans.inProgress', type: 'warning' },
    done:        { label: 'production.plans.done',       type: 'success' },
    canceled:    { label: 'production.plans.canceled',   type: 'danger' },
  },
  assignment: {
    pending: { label: 'production.assignments.pending', type: 'info' },
    working: { label: 'production.assignments.working', type: 'warning' },
    done:    { label: 'production.assignments.done',    type: 'success' },
  },
  mrp_run: {
    running: { label: 'mrp.statusRunning', type: 'warning' },
    done:    { label: 'mrp.statusDone',    type: 'success' },
    failed:  { label: 'mrp.statusFailed',  type: 'danger' },
  },
  quotation: {
    draft:     { label: 'quotation.statusDraft',     type: 'info' },
    submitted: { label: 'quotation.statusSubmitted', type: 'warning' },
    approved:  { label: 'quotation.statusApproved',  type: 'success' },
    rejected:  { label: 'quotation.statusRejected',  type: 'danger' },
    converted: { label: 'quotation.statusConverted', type: 'primary' },
  },
  subcontract: {
    draft:             { label: 'subcontract.statusDraft',            type: 'info' },
    sent:              { label: 'subcontract.statusSent',             type: 'warning' },
    partial_received:  { label: 'subcontract.statusPartialReceived', type: 'primary' },
    received:          { label: 'subcontract.statusReceived',         type: 'success' },
    settled:           { label: 'subcontract.statusSettled',          type: 'success' },
  },
}

export function useStatus(domain: StatusDomain) {
  const { t } = useI18n()
  const config = DOMAIN_CONFIG[domain]

  function label(status: string): string {
    const def = config[status]
    if (!def) return status || '-'
    return t(def.label)
  }

  function type(status: string): TagType {
    const def = config[status]
    if (!def) return 'info'
    return def.type
  }

  function options(): { value: string; label: string }[] {
    return Object.entries(config).map(([value, def]) => ({
      value,
      label: t(def.label),
    }))
  }

  /**
   * 返回一个 el-tag 渲染函数，直接用于 template
   * 用法: <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
   *
   * 可简化为:
   *   const { tagProps } = useStatus('order')
   *   <el-tag v-bind="tagProps(row.status)" />
   */
  function tagProps(status: string): { type: TagType; label: string } {
    const def = config[status]
    return {
      type: def?.type ?? 'info',
      label: def ? t(def.label) : status || '-',
    }
  }

  return { label, type, options, tagProps }
}
