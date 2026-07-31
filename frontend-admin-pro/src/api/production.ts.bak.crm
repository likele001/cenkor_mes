import axios from 'axios'
import { masterApi } from '@/api/master'
import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type OrderSkuOption = {
  id: number
  code: string
  product_id?: number
  product_name?: string
  sku_name?: string
  display_label?: string
}

export type OrderFormOptions = {
  customers: { id: number; code: string; name: string }[]
  skus: OrderSkuOption[]
}

export type CustomerOut = {
  id: number
  tenant_id: number
  user_id: number | null
  owner_user_id?: number | null
  owner_name?: string | null
  login_username?: string | null
  product_count?: number
  code: string
  name: string
  contact_name: string | null
  contact_phone: string | null
  address: string | null
  remark: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type CustomerContactOut = {
  id: number
  tenant_id: number
  customer_id: number
  name: string
  phone: string | null
  email: string | null
  title: string | null
  is_primary: boolean
  remark: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type CustomerContactIn = {
  name: string
  phone?: string | null
  email?: string | null
  title?: string | null
  is_primary?: boolean
  remark?: string | null
  is_active?: boolean
}

export type OpportunityOut = {
  id: number
  tenant_id: number
  customer_id: number
  code: string
  title: string
  stage: string
  status: string
  amount: number | null
  probability: number | null
  expected_close_date: string | null
  owner_user_id: number | null
  owner_name: string | null
  converted_order_id?: number | null
  converted_order_code?: string | null
  remark: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type OpportunityIn = {
  code?: string | null
  title: string
  stage?: string
  status?: string
  amount?: number | null
  probability?: number | null
  expected_close_date?: string | null
  owner_user_id?: number | null
  remark?: string | null
  is_active?: boolean
}

export type OpportunityActivityOut = {
  id: number
  tenant_id: number
  opportunity_id: number
  action_type: string
  content: string
  created_by: number | null
  created_by_name: string | null
  next_follow_up_at?: string | null
  created_at: string
}

export type CustomerTagOut = {
  id: number
  tenant_id: number
  name: string
  color: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type OrderItemOut = {
  id: number
  tenant_id: number
  order_id: number
  line_no: number
  sku_id: number
  qty: number
  remark: string | null
  created_at: string
  updated_at: string
  sku: {
    id: number
    code: string
    name: string
    product_id?: number
    product_name?: string
    sku_name?: string
    display_label?: string
  } | null
  locked?: boolean
  lock_reason?: string | null
}

export type OrderOut = {
  id: number
  tenant_id: number
  customer_id: number
  opportunity_id?: number | null
  opportunity_code?: string | null
  code: string
  status: string
  due_date: string | null
  remark: string | null
  confirmed_at: string | null
  confirmed_by: number | null
  created_at: string
  updated_at: string
  customer: { id: number; name: string; code: string } | null
}

export type OrderDetailOut = OrderOut & { items: OrderItemOut[]; order_plan_locked?: boolean }

export type OrderImportResult = {
  orders_created: number
  lines_success: number
  errors: { row: number; message: string }[]
  warnings: { row: number; message: string }[]
  created_orders: { id: number; code: string }[]
}

export type OrderItemCreateIn = {
  line_no: number
  sku_id: number
  qty: number
  remark?: string | null
}

export type OrderCreateIn = {
  customer_id: number
  code: string
  due_date?: string | null
  remark?: string | null
  opportunity_id?: number | null
  items: OrderItemCreateIn[]
}

export type OrderItemUpsertIn = {
  id?: number | null
  line_no: number
  sku_id: number
  qty: number
  remark?: string | null
}

export type OrderUpdateIn = {
  customer_id?: number | null
  code?: string | null
  due_date?: string | null
  remark?: string | null
  status?: string | null
  items?: OrderItemUpsertIn[]
}

export type WorkOrderOut = {
  id: number
  tenant_id: number
  order_id: number
  order_item_id: number
  product_id: number
  sku_id: number
  qty: number
  status: string
  created_at: string
  updated_at: string
  sku: {
    id: number
    code: string
    name: string
    product_id?: number
    product_name?: string
    sku_name?: string
    display_label?: string
  } | null
}

export type WorkOrderDetailOut = WorkOrderOut & {
  tasks: TaskOut[]
}

export type TaskAssignmentOut = {
  id: number
  user_id: number
  assigned_qty: number
  reported_qty?: number
  remaining_qty?: number
  assigned_at: string
  assigned_by: number | null
  user: { id: number; username: string; full_name: string | null } | null
}

/** 分工分配列表行（员工×任务） */
export type DispatchAssignmentOut = {
  id: number
  task_id: number
  task_code: string
  task_status: string
  order_id: number | null
  order_code: string | null
  product_id: number | null
  product_name: string | null
  sku_id: number | null
  sku_code: string | null
  sku_name: string | null
  process_id: number | null
  process_code: string | null
  process_name: string | null
  user_id: number
  username: string | null
  user_full_name: string | null
  assigned_qty: number
  reported_qty: number
  remaining_qty: number
  progress: number
  status: string
  assigned_at: string
  assigned_by: number | null
}

export type TaskOut = {
  id: number
  tenant_id: number
  work_order_id: number
  process_id: number
  seq: number
  task_code: string
  planned_qty: number
  status: string
  assigned_user_id: number | null
  assigned_at: string | null
  assigned_by: number | null
  equipment_id?: number | null
  assignments?: TaskAssignmentOut[]
  assigned_total_qty?: number
  unassigned_qty?: number
  created_at: string
  updated_at: string
  process: { id: number; code: string; name: string } | null
  equipment?: { id: number; code: string; name: string; workshop: string | null; status: string } | null
  order?: {
    id: number
    code: string
    status: string
    customer_id: number
    customer_name: string | null
    customer_code: string | null
  } | null
  sku?: {
    id: number
    code: string
    name: string
    display_label?: string
    sku_display_name?: string
    product_name?: string
  } | null
  product?: { id: number; code: string; name: string; display_name?: string } | null
  work_order: {
    id: number
    order_id: number
    sku_id: number
    qty: number
    sku_display_label?: string | null
  } | null
}

export type ReportOut = {
  id: number
  task_id: number
  report_user_id: number
  good_qty: number
  bad_qty: number
  remark: string | null
  attachment_ids: string | null
  status: string
  created_at: string
  updated_at: string
  report_user: { id: number; full_name: string } | null
  task: { id: number; task_code: string; process_id: number } | null
}

export type ReportUnitOut = {
  id: number
  task_id: number
  task_assignment_id: number
  user_id: number
  unit_seq: number
  result_type: string | null
  employee_attachment_ids: string | null
  qc_attachment_ids: string | null
  remark: string | null
  status: string
  prescreen_level?: string | null
  prescreen_json?: string | null
  prescreen_at?: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  task: { id: number; task_code: string; process_id: number } | null
  report_user: { id: number; full_name: string } | null
}

export type AttachmentMetaOut = {
  id: number
  content_type?: string | null
  original_filename?: string | null
  size?: number
}

export type ReportUnitDetailOut = ReportUnitOut & {
  employee_attachments?: AttachmentMetaOut[]
  qc_attachments?: AttachmentMetaOut[]
  audits: {
    id: number
    auditor_id: number
    audit_level: string
    action: string
    attachment_ids: string | null
    reason: string | null
    created_at: string
  }[]
}

export type SalaryItemOut = {
  id: number
  report_id: number | null
  user_id: number
  sku_id: number
  process_id: number
  unit_price: number
  good_qty: number
  amount: number
  month: string
  created_at: string
}

/** 工资明细台账（对标 thinkmes 工资列表） */
export type SalaryLedgerOut = {
  id: number
  source: 'unit' | 'report'
  salary_id: number | null
  report_unit_id: number | null
  report_id: number | null
  user_id: number
  username: string | null
  user_full_name: string | null
  order_id: number | null
  order_code: string | null
  product_id: number | null
  product_name: string | null
  sku_id: number | null
  sku_code: string | null
  sku_name: string | null
  process_id: number | null
  process_code: string | null
  process_name: string | null
  unit_seq: number | null
  reported_qty: number
  unit_price: number
  amount: number
  status: string
  status_label: string
  reported_at: string | null
  month: string
  task_code: string | null
  result_type: string | null
}

export type SalarySlipOut = {
  id: number
  user_id: number
  user_name: string | null
  month: string
  total_qty: number
  item_amount: number
  hourly_amount: number
  hourly_hours: number
  bonus_amount: number
  deduction_amount: number
  net_amount: number
  signature_attachment_id: number | null
  signed_at: string | null
  is_signed: boolean
  confirm_status?: string
  reject_reason?: string | null
  rejected_at?: string | null
}

export type HourlyItemOut = {
  id: number
  user_id: number
  user_name: string | null
  item_type: string
  work_date: string | null
  work_hours: number
  hourly_rate: number
  amount: number
  month: string
  is_absent: boolean
}

export type ExportJobOut = {
  id: number
  job_type: string
  status: string
  params: any
  result_attachment_id: number | null
  error_msg: string | null
  created_by: number | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type UserOut = {
  id: number
  tenant_id: number
  department_id: number | null
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
  roles: { id: number; code: string; name: string }[]
  department: { id: number; code: string; name: string } | null
}

export const productionApi = {
  // 客户
  listCustomers(params: any) {
    return http.request<ListResp<CustomerOut>>({ url: '/admin/production/customers', method: 'GET', params })
  },
  getCustomer(id: number) {
    return http.request<CustomerOut>({ url: `/admin/production/customers/${id}`, method: 'GET' })
  },
  printCustomer(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; customer_id: number; code: string; template_id: number }>({
      url: `/admin/production/customers/${id}/print`,
      method: 'GET',
      params,
    })
  },
  exportCustomerPdf(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/production/customers/${id}/print-pdf`,
      method: 'GET',
      params,
    })
  },
  createCustomer(data: {
    code: string
    name: string
    contact_name?: string
    contact_phone?: string
    address?: string
    remark?: string
    is_active?: boolean
    user_id?: number
    login_username?: string
    login_password?: string
    owner_user_id?: number | null
  }) {
    return http.request<CustomerOut>({ url: '/admin/production/customers', method: 'POST', data })
  },
  updateCustomer(
    id: number,
    data: {
      code?: string
      name?: string
      contact_name?: string
      contact_phone?: string
      address?: string
      remark?: string
      is_active?: boolean
      user_id?: number
      login_username?: string
      login_password?: string
      owner_user_id?: number | null
    },
  ) {
    return http.request<CustomerOut>({ url: `/admin/production/customers/${id}`, method: 'PUT', data })
  },
  getCustomerProducts(customerId: number) {
    return http.request<{ product_ids: number[]; items: { id: number; code: string; name: string; category: string | null }[] }>({
      url: `/admin/production/customers/${customerId}/products`,
      method: 'GET',
    })
  },
  setCustomerProducts(customerId: number, product_ids: number[]) {
    return http.request<{ customer_id: number; product_ids: number[] }>({
      url: `/admin/production/customers/${customerId}/products`,
      method: 'PUT',
      data: { product_ids },
    })
  },
  listCustomerContacts(customerId: number, params?: any) {
    return http.request<ListResp<CustomerContactOut>>({ url: `/admin/production/customers/${customerId}/contacts`, method: 'GET', params })
  },
  createCustomerContact(customerId: number, data: CustomerContactIn) {
    return http.request<{ id: number }>({ url: `/admin/production/customers/${customerId}/contacts`, method: 'POST', data })
  },
  updateCustomerContact(customerId: number, contactId: number, data: Partial<CustomerContactIn>) {
    return http.request<{ id: number }>({ url: `/admin/production/customers/${customerId}/contacts/${contactId}`, method: 'PUT', data })
  },
  deleteCustomerContact(customerId: number, contactId: number) {
    return http.request<{ id: number }>({ url: `/admin/production/customers/${customerId}/contacts/${contactId}`, method: 'DELETE' })
  },
  listOpportunities(customerId: number, params?: any) {
    return http.request<ListResp<OpportunityOut>>({ url: `/admin/production/customers/${customerId}/opportunities`, method: 'GET', params })
  },
  createOpportunity(customerId: number, data: OpportunityIn) {
    return http.request<{ id: number; code: string }>({ url: `/admin/production/customers/${customerId}/opportunities`, method: 'POST', data })
  },
  updateOpportunity(customerId: number, opportunityId: number, data: Partial<OpportunityIn>) {
    return http.request<{ id: number }>({ url: `/admin/production/customers/${customerId}/opportunities/${opportunityId}`, method: 'PUT', data })
  },
  deleteOpportunity(customerId: number, opportunityId: number) {
    return http.request<{ id: number }>({ url: `/admin/production/customers/${customerId}/opportunities/${opportunityId}`, method: 'DELETE' })
  },
  listOpportunityActivities(customerId: number, opportunityId: number) {
    return http.request<ListResp<OpportunityActivityOut>>({
      url: `/admin/production/customers/${customerId}/opportunities/${opportunityId}/activities`,
      method: 'GET',
    })
  },
  createOpportunityActivity(
    customerId: number,
    opportunityId: number,
    data: { action_type?: string; content: string; next_follow_up_at?: string | null },
  ) {
    return http.request<{ id: number }>({
      url: `/admin/production/customers/${customerId}/opportunities/${opportunityId}/activities`,
      method: 'POST',
      data,
    })
  },
  convertOpportunityToOrder(
    customerId: number,
    opportunityId: number,
    data: { due_date?: string | null; remark?: string | null; items: OrderItemCreateIn[] },
  ) {
    return http.request<{ order_id: number; order_code: string; opportunity_id: number }>({
      url: `/admin/production/customers/${customerId}/opportunities/${opportunityId}/convert-to-order`,
      method: 'POST',
      data,
    })
  },

  listCrmOpportunities(params?: any) {
    return http.request<ListResp<OpportunityOut & { customer_name?: string }>>({
      url: '/admin/production/crm/opportunities',
      method: 'GET',
      params,
    })
  },
  getCrmDashboardSummary() {
    return http.request<{ open_opportunities: number; public_pool: number; due_followups: number }>({
      url: '/admin/production/crm/dashboard-summary',
      method: 'GET',
    })
  },
  getCrmSettings() {
    return http.request<{ recycle_days: number; followup_remind_enabled: boolean; followup_remind_days_before: number }>({
      url: '/admin/production/crm/settings',
      method: 'GET',
    })
  },
  updateCrmSettings(data: { recycle_days?: number; followup_remind_enabled?: boolean; followup_remind_days_before?: number }) {
    return http.request<{ updated: boolean }>({ url: '/admin/production/crm/settings', method: 'PUT', data })
  },
  listCrmAfterSales(params?: any) {
    return http.request<ListResp<any>>({ url: '/admin/production/crm/after-sales', method: 'GET', params })
  },
  updateCrmAfterSale(id: number, data: { status?: string; solution?: string }) {
    return http.request<{ id: number; status: string }>({ url: `/admin/production/crm/after-sales/${id}`, method: 'PUT', data })
  },

  listCrmTags(params?: any) {
    return http.request<ListResp<CustomerTagOut>>({ url: '/admin/production/crm/tags', method: 'GET', params })
  },
  createCrmTag(data: { name: string; color?: string | null; is_active?: boolean }) {
    return http.request<CustomerTagOut>({ url: '/admin/production/crm/tags', method: 'POST', data })
  },
  updateCrmTag(tagId: number, data: { name?: string; color?: string | null; is_active?: boolean }) {
    return http.request<CustomerTagOut>({ url: `/admin/production/crm/tags/${tagId}`, method: 'PUT', data })
  },
  deleteCrmTag(tagId: number) {
    return http.request<{ id: number }>({ url: `/admin/production/crm/tags/${tagId}`, method: 'DELETE' })
  },
  getCustomerTags(customerId: number) {
    return http.request<{ items: { tag_id: number; tag_name: string | null; tag_color: string | null }[] }>({
      url: `/admin/production/customers/${customerId}/tags`,
      method: 'GET',
    })
  },
  setCustomerTags(customerId: number, tag_ids: number[]) {
    return http.request<{ customer_id: number; tag_ids: number[] }>({ url: `/admin/production/customers/${customerId}/tags`, method: 'PUT', data: { tag_ids } })
  },
  listCrmPublicPoolOpportunities(params?: any) {
    return http.request<ListResp<any>>({ url: '/admin/production/crm/public-pool/opportunities', method: 'GET', params })
  },
  claimCrmPublicPoolOpportunity(id: number) {
    return http.request<{ id: number; owner_user_id: number }>({ url: `/admin/production/crm/public-pool/opportunities/${id}/claim`, method: 'POST' })
  },
  releaseCrmPublicPoolOpportunity(id: number) {
    return http.request<{ id: number; owner_user_id: number | null }>({ url: `/admin/production/crm/public-pool/opportunities/${id}/release`, method: 'POST' })
  },
  recycleCrmPublicPool(days?: number) {
    return http.request<{ recycled: number; days: number }>({ url: `/admin/production/crm/public-pool/recycle`, method: 'POST', params: { days } })
  },
  getCrmOpportunityStats(params?: any) {
    return http.request<{ items: any[]; total_count: number; total_amount: number }>({ url: '/admin/production/crm/opportunities/stats', method: 'GET', params })
  },

  // 订单
  listOrders(params: any) {
    return http.request<ListResp<OrderOut>>({ url: '/admin/production/orders', method: 'GET', params })
  },
  getOrder(id: number) {
    return http.request<OrderDetailOut>({ url: `/admin/production/orders/${id}`, method: 'GET' })
  },
  printOrder(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; order_id: number; code: string; template_id: number }>({
      url: `/admin/production/orders/${id}/print`,
      method: 'GET',
      params,
    })
  },
  exportOrderPdf(id: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/production/orders/${id}/print-pdf`,
      method: 'GET',
      params,
    })
  },
  /** 新建订单下拉：仅需 order.manage（后端需已部署 meta/form-options） */
  getOrderFormOptions() {
    return http.request<OrderFormOptions>({ url: '/admin/production/orders/meta/form-options', method: 'GET' })
  },
  /** 优先 meta/form-options；404 时回退客户/型号列表（需 customer.manage、sku.manage） */
  async fetchOrderFormOptions(): Promise<OrderFormOptions> {
    try {
      return await this.getOrderFormOptions()
    } catch (e: unknown) {
      const status = axios.isAxiosError(e) ? e.response?.status : undefined
      if (status !== 404) throw e
      const [cRes, sRes, pRes] = await Promise.all([
        this.listCustomers({ keyword: '', offset: 0, limit: 200, include_inactive: false }),
        masterApi.listSkus({ offset: 0, limit: 200, include_inactive: false }),
        masterApi.listProducts({ offset: 0, limit: 500, include_inactive: false }),
      ])
      const pmap = new Map((pRes.items || []).map((p) => [p.id, p]))
      return {
        customers: (cRes.items || []).map((c) => ({ id: c.id, code: c.code, name: c.name })),
        skus: (sRes.items || [])
          .filter((s) => {
            const code = (s.code || '').toUpperCase()
            const p = pmap.get(s.product_id)
            if (code.startsWith('MAT-')) return false
            if (p?.code === '__MATERIAL__' || p?.category === 'material') return false
            return true
          })
          .map((s) => {
            const p = pmap.get(s.product_id)
            const product_name = (p?.display_name || p?.name || '').trim()
            const sku_name = (s.name || '').trim()
            const display_label = product_name && sku_name ? `${product_name} · ${sku_name}` : sku_name || product_name
            return {
              id: s.id,
              code: s.code,
              product_id: s.product_id,
              product_name,
              sku_name,
              display_label,
            }
          }),
      }
    }
  },
  rejectOrder(id: number, reason: string) {
    return http.request<OrderDetailOut>({
      url: `/admin/production/orders/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },
  confirmOrder(id: number) {
    return http.request<{
      order_id: number
      work_order_count: number
      automation_plan_id?: number | null
      automation_pipeline_ran?: boolean
    }>({ url: `/admin/production/orders/${id}/confirm`, method: 'POST' })
  },
  createOrder(data: OrderCreateIn) {
    return http.request<OrderDetailOut>({ url: '/admin/production/orders', method: 'POST', data })
  },
  updateOrder(id: number, data: OrderUpdateIn) {
    return http.request<OrderDetailOut>({ url: `/admin/production/orders/${id}`, method: 'PUT', data })
  },
  downloadOrderImportTemplate() {
    return http.downloadBlob({
      url: '/admin/production/orders/import-template',
      method: 'GET',
    })
  },
  importOrdersExcel(payload: {
    file: File
    customer_id: number
    order_name: string
    due_date?: string
    remark?: string
    order_code?: string
    auto_create_product?: boolean
    auto_create_sku?: boolean
    default_unit_price?: number
  }) {
    const form = new FormData()
    form.append('file', payload.file)
    form.append('customer_id', String(payload.customer_id))
    form.append('order_name', payload.order_name)
    if (payload.due_date) form.append('due_date', payload.due_date)
    if (payload.remark) form.append('remark', payload.remark)
    if (payload.order_code) form.append('order_code', payload.order_code)
    form.append('auto_create_product', payload.auto_create_product !== false ? '1' : '0')
    form.append('auto_create_sku', payload.auto_create_sku !== false ? '1' : '0')
    const price = Number(payload.default_unit_price)
    form.append('default_unit_price', String(Number.isFinite(price) && price >= 0 ? price : 1))
    return http.request<OrderImportResult>({
      url: '/admin/production/orders/import-excel',
      method: 'POST',
      data: form,
    })
  },

  // 工单
  listWorkOrders(params: any) {
    return http.request<ListResp<WorkOrderOut>>({ url: '/admin/production/work-orders', method: 'GET', params })
  },
  getWorkOrder(id: number) {
    return http.request<WorkOrderDetailOut>({ url: `/admin/production/work-orders/${id}`, method: 'GET' })
  },
  printProductLabels(workOrderId: number, params?: { piece_no_from?: number; piece_no_to?: number }) {
    return http.request<{ html: string; count: number; work_order_id: number }>({
      url: `/admin/production/work-orders/${workOrderId}/print-product-labels`,
      method: 'GET',
      params,
    })
  },

  // 任务
  listTasks(params: any) {
    return http.request<ListResp<TaskOut>>({ url: '/admin/production/tasks', method: 'GET', params })
  },
  assignTask(taskId: number, data: { assigned_user_id: number | null; equipment_id?: number | null }) {
    return http.request<TaskOut>({ url: `/admin/production/tasks/${taskId}/assign`, method: 'POST', data })
  },
  getTaskAssignments(taskId: number) {
    return http.request<{
      task_id: number
      planned_qty: number
      assigned_total_qty: number
      items: TaskAssignmentOut[]
    }>({ url: `/admin/production/tasks/${taskId}/assignments`, method: 'GET' })
  },
  setTaskAssignments(
    taskId: number,
    data: { items: { user_id: number; assigned_qty: number }[]; equipment_id?: number | null },
  ) {
    return http.request<TaskOut>({ url: `/admin/production/tasks/${taskId}/assignments`, method: 'PUT', data })
  },
  listDispatchAssignments(params?: {
    keyword?: string
    order_id?: number
    user_id?: number
    process_id?: number
    offset?: number
    limit?: number
  }) {
    return http.request<{ items: DispatchAssignmentOut[]; total: number }>({
      url: '/admin/production/assignments',
      method: 'GET',
      params,
    })
  },
  getDispatchAssignmentQr(assignmentId: number) {
    return http.request<{ task_code: string; text: string; report_url: string; svg: string }>({
      url: `/admin/production/assignments/${assignmentId}/qr`,
      method: 'GET',
    })
  },
  deleteDispatchAssignment(assignmentId: number) {
    return http.request<void>({ url: `/admin/production/assignments/${assignmentId}`, method: 'DELETE' })
  },
  renderTaskLabel(taskId: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ html: string; task_id: number; task_code: string; template_id: number }>({
      url: `/admin/production/tasks/${taskId}/print-label`,
      method: 'GET',
      params,
    })
  },
  exportTaskLabelPdf(taskId: number, params?: { template_id?: number; template_code?: string }) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/production/tasks/${taskId}/print-label-pdf`,
      method: 'GET',
      params,
    })
  },
  renderTaskLabelBatch(data: { task_ids: number[]; template_id?: number; template_code?: string }) {
    return http.request<{ html: string; count: number; template_id: number }>({
      url: '/admin/production/tasks/print-label-batch',
      method: 'POST',
      data,
    })
  },
  listDispatchSkills(params?: any) {
    return http.request<ListResp<{ id: number; code: string; name: string }>>({ url: '/admin/production/tasks/dispatch-skills', method: 'GET', params })
  },
  listDispatchUsers(params: any) {
    return http.request<ListResp<UserOut>>({ url: '/admin/production/tasks/dispatch-users', method: 'GET', params })
  },

  // 报工审核
  listReports(params: any) {
    return http.request<ListResp<ReportOut>>({ url: '/admin/production/reports', method: 'GET', params })
  },
  getReport(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}`, method: 'GET' })
  },
  leaderApprove(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}/leader-approve`, method: 'POST' })
  },
  qcApprove(id: number) {
    return http.request<any>({ url: `/admin/production/reports/${id}/qc-approve`, method: 'POST' })
  },
  rejectReport(id: number, reason?: string) {
    return http.request<any>({
      url: `/admin/production/reports/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },

  listReportUnits(params: any) {
    return http.request<ListResp<ReportUnitOut>>({
      url: '/admin/production/report-units',
      method: 'GET',
      params,
    })
  },
  getReportUnit(id: number) {
    return http.request<ReportUnitDetailOut>({ url: `/admin/production/report-units/${id}`, method: 'GET' })
  },
  getApprovalSteps() {
    return http.request<{ steps: Array<{ step_order: number; approver_role: string; is_required: boolean; can_skip: boolean; label: string }> }>({
      url: '/admin/production/report-units/approval-steps',
      method: 'GET',
    })
  },
  approveReportUnit(id: number, data?: { qc_attachment_ids?: string; inspection_results?: Array<{
    template_item_id: number; result: string; measured_value?: string | null; defect_code_id?: number | null; remark?: string | null
  }> }) {
    return http.request<any>({ url: `/admin/production/report-units/${id}/approve`, method: 'POST', data })
  },
  leaderApproveReportUnit(id: number) {
    return http.request<any>({ url: `/admin/production/report-units/${id}/leader-approve`, method: 'POST' })
  },
  qcApproveReportUnit(id: number, data: { qc_attachment_ids: string; inspection_results?: Array<{
    template_item_id: number; result: string; measured_value?: string | null; defect_code_id?: number | null; remark?: string | null
  }> }) {
    return http.request<any>({ url: `/admin/production/report-units/${id}/qc-approve`, method: 'POST', data })
  },
  /** 获取该任务工序的质检检查项 */
  getInspectionForm(processId: number) {
    return http.request<{
      items: Array<{
        id: number
        seq: number
        item_name: string
        item_type: string
        standard_value: string | null
        upper_limit: string | null
        lower_limit: string | null
        unit: string | null
        is_required: boolean
        remark: string | null
      }>
    }>({ url: '/admin/production/inspection-templates', method: 'GET', params: { process_id: processId } })
  },
  /** 获取缺陷代码列表 */
  listDefectCodes() {
    return http.request<{
      items: Array<{ id: number; code: string; name: string; severity: string }>
    }>({ url: '/admin/production/defect-codes', method: 'GET' })
  },
  rejectReportUnit(id: number, reason?: string) {
    return http.request<any>({
      url: `/admin/production/report-units/${id}/reject`,
      method: 'POST',
      params: { reason },
    })
  },

  // 工资
  listSalaryLedger(params?: {
    month?: string
    user_id?: number
    status?: string
    keyword?: string
    offset?: number
    limit?: number
  }) {
    return http.request<{ items: SalaryLedgerOut[]; total: number }>({
      url: '/admin/production/reports/salary/ledger',
      method: 'GET',
      params,
    })
  },
  listSalaryItems(params: any) {
    return http.request<ListResp<SalaryItemOut>>({ url: '/admin/production/reports/salary/items', method: 'GET', params })
  },
  getSalarySummary(params: any) {
    return http.request<{ items: any[] }>({ url: '/admin/production/reports/salary/summary', method: 'GET', params })
  },
  listSalaryAllowances(params?: { user_id?: number; month?: string }) {
    return http.request<{ items: { id: number; user_id: number; allowance_type: string; amount: number; month: string; reason: string | null }[] }>({
      url: '/admin/production/reports/salary/allowances',
      method: 'GET',
      params,
    })
  },
  createSalaryAllowance(data: {
    user_id: number
    allowance_type: string
    amount: number
    month: string
    reason?: string
  }) {
    return http.request<{ id: number; allowance_type: string; amount: number }>({
      url: '/admin/production/reports/salary/allowances',
      method: 'POST',
      data,
    })
  },
  exportSalaryExcel(params: any) {
    return http.request<Blob>({ url: '/admin/production/reports/salary/export', method: 'GET', params, responseType: 'blob' })
  },
  createSalaryExportJob(params: any) {
    return http.request<ExportJobOut>({ url: '/admin/production/reports/salary/export-jobs', method: 'POST', params })
  },
  getSalaryExportJob(id: number) {
    return http.request<ExportJobOut>({ url: `/admin/production/reports/salary/export-jobs/${id}`, method: 'GET' })
  },
  listSalarySlips(params: any) {
    return http.request<ListResp<SalarySlipOut>>({ url: '/admin/production/reports/salary/slips', method: 'GET', params })
  },
  resetSalarySlipConfirm(id: number) {
    return http.request<any>({ url: `/admin/production/reports/salary/slips/${id}/reset-confirm`, method: 'POST' })
  },
  remindSalarySlips(month: string) {
    return http.request<{ month: string; sent: number; skipped: number }>({
      url: '/admin/production/reports/salary/slips/remind',
      method: 'POST',
      params: { month },
    })
  },

  // 计时工资
  listHourlyItems(params?: { month?: string; user_id?: number; offset?: number; limit?: number }) {
    return http.request<{ items: HourlyItemOut[]; total: number }>({
      url: '/admin/production/reports/salary/hourly-items',
      method: 'GET',
      params,
    })
  },
  generateTimeItems(params: { date_from: string; date_to?: string; user_id?: number }) {
    return http.request<{ generated: number; date_from: string; date_to: string }>({
      url: '/admin/production/reports/salary/generate-time-items',
      method: 'POST',
      params,
    })
  },
  getHourlySummary(params?: { month?: string; user_id?: number }) {
    return http.request<{ total_hours: number; total_amount: number }>({
      url: '/admin/production/reports/salary/hourly-summary',
      method: 'GET',
      params,
    })
  },
  listHourlyLedger(params?: { month?: string; user_id?: number; offset?: number; limit?: number }) {
    return http.request<{ items: any[]; total: number }>({
      url: '/admin/production/reports/salary/hourly-ledger',
      method: 'GET',
      params,
    })
  },

  // 用户（派工用）
  listUsers(params: any) {
    return http.request<ListResp<UserOut>>({ url: '/admin/system/users', method: 'GET', params })
  },

  exportCustomers(params?: any) {
    return http.downloadBlob({ url: '/admin/production/customers/export', method: 'GET', params })
  },
  exportOrders(params?: any) {
    return http.downloadBlob({ url: '/admin/production/orders/export', method: 'GET', params })
  },
  exportWorkOrders(params?: any) {
    return http.downloadBlob({ url: '/admin/production/work-orders/export', method: 'GET', params })
  },
  exportReportUnits(params?: any) {
    return http.downloadBlob({ url: '/admin/production/report-units/export', method: 'GET', params })
  },
  exportSalarySlips(params?: any) {
    return http.downloadBlob({ url: '/admin/production/reports/salary/slips/export', method: 'GET', params })
  },
}
