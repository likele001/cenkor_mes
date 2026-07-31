import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

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

export const customerApi = {
  // 客户
  listCustomers(params: any) {
    return http.request<ListResp<CustomerOut>>({ url: '/admin/production/customers', method: 'GET', params })
  },
  getCustomer(id: number) {
    return http.request<CustomerOut>({ url: `/admin/production/customers/${id}`, method: 'GET' })
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
    data: { due_date?: string | null; remark?: string | null; items: { line_no: number; sku_id: number; qty: number; remark?: string | null }[] },
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
}

// ============================================================
// CRM Domain Types
// ============================================================

export type LeadOut = {
  id: number
  tenant_id: number
  code: string
  contact_name: string
  company?: string
  email?: string
  phone?: string
  mobile?: string
  wechat?: string
  position?: string
  industry?: string
  country?: string
  province?: string
  city?: string
  address?: string
  website?: string
  source?: string
  status: string
  score?: number
  grade?: string
  last_follow_up_at?: string
  next_follow_up_at?: string
  owner_user_id?: number
  owner_name?: string | null
  is_public_pool: boolean
  customer_id?: number
  opportunity_id?: number
  converted_at?: string
  remark?: string
  created_at: string
}

export type LeadCreateIn = {
  contact_name: string
  company?: string
  email?: string
  phone?: string
  mobile?: string
  wechat?: string
  position?: string
  industry?: string
  country?: string
  province?: string
  city?: string
  address?: string
  website?: string
  source?: string
  status?: string
  owner_user_id?: number
  remark?: string
}

export type LeadUpdateIn = {
  contact_name?: string
  company?: string
  email?: string
  phone?: string
  mobile?: string
  wechat?: string
  position?: string
  industry?: string
  country?: string
  province?: string
  city?: string
  address?: string
  website?: string
  source?: string
  status?: string
  owner_user_id?: number | null
  remark?: string
}

export type LeadConvertIn = {
  convert_to_customer?: boolean
  convert_to_opportunity?: boolean
  opportunity_title?: string
  opportunity_stage?: string
  opportunity_amount?: number
}

export type LeadActivityOut = {
  id: number
  lead_id: number
  action_type: string
  content: string
  created_by?: number
  created_by_name?: string | null
  next_follow_up_at?: string
  created_at: string
}

export type LeadActivityCreateIn = {
  action_type?: string
  content: string
  next_follow_up_at?: string
}

export type LeadSummary = {
  total: number
  by_status: Record<string, number>
  by_grade: Record<string, number>
  by_source: Record<string, number>
  public_pool: number
  converted: number
}

export type QuotationItemIn = {
  product_id?: number
  sku_id?: number
  product_name: string
  spec?: string
  quantity: number
  unit_price: number
  discount_rate?: number
  tax_rate?: number
  delivery_date?: string
  remark?: string
}

export type QuotationItemOut = {
  id: number
  product_name: string
  spec?: string
  quantity: number
  unit_price: number
  discount_rate: number
  tax_rate: number
  amount: number
  delivery_date?: string
  remark?: string
}

export type QuotationOut = {
  id: number
  code: string
  title: string
  customer_id: number
  opportunity_id?: number
  version: number
  status: string
  valid_from: string
  valid_until: string
  currency: string
  tax_rate: number
  discount_rate: number
  subtotal: number
  tax_amount: number
  total_amount: number
  payment_terms?: string
  delivery_terms?: string
  owner_user_id?: number
  sent_at?: string
  accepted_at?: string
  rejected_at?: string
  reject_reason?: string
  converted_order_id?: number
  remark?: string
  created_at: string
}

export type QuotationCreateIn = {
  title: string
  customer_id: number
  opportunity_id?: number
  valid_from?: string
  valid_until?: string
  currency?: string
  tax_rate?: number
  discount_rate?: number
  payment_terms?: string
  delivery_terms?: string
  owner_user_id?: number
  remark?: string
  items: QuotationItemIn[]
}

export type QuotationUpdateIn = {
  title?: string
  valid_from?: string
  valid_until?: string
  currency?: string
  tax_rate?: number
  discount_rate?: number
  payment_terms?: string
  delivery_terms?: string
  owner_user_id?: number | null
  remark?: string
  items?: QuotationItemIn[]
}

export type QuotationRejectIn = {
  reason?: string
}

export type ContractOut = {
  id: number
  code: string
  name: string
  customer_id: number
  opportunity_id?: number
  quotation_id?: number
  order_id?: number
  type: string
  status: string
  sign_date?: string
  start_date?: string
  end_date?: string
  auto_renewal: boolean
  renewal_notice_days: number
  total_amount: number
  currency: string
  payment_terms?: string
  owner_user_id?: number
  owner_name?: string | null
  parent_contract_id?: number
  renewal_count: number
  remark?: string
  created_at: string
}

export type PaymentPlanOut = {
  id: number
  contract_id: number
  phase: string
  phase_name: string
  due_date: string
  amount: number
  actual_amount: number
  actual_date?: string
  status: string
  invoice_no?: string
  remark?: string
}

export type ContractCreateIn = {
  name: string
  customer_id: number
  opportunity_id?: number
  quotation_id?: number
  order_id?: number
  type?: string
  status?: string
  sign_date?: string
  start_date?: string
  end_date?: string
  auto_renewal?: boolean
  renewal_notice_days?: number
  currency?: string
  payment_terms?: string
  owner_user_id?: number
  remark?: string
  plan_items: PaymentPlanIn[]
}

export type PaymentPlanIn = {
  phase: string
  phase_name: string
  due_date: string
  amount: number
  actual_amount?: number
  actual_date?: string
  status?: string
  invoice_no?: string
  remark?: string
}

export type PaymentRecordIn = {
  actual_amount: number
  actual_date?: string
  invoice_no?: string
}

export type WinLossReasonOut = {
  id: number
  type: string
  category: string
  code: string
  name: string
  description?: string
  sort_order: number
}

export type WinLossReasonCreateIn = {
  type: string
  category: string
  code: string
  name: string
  description?: string
  sort_order?: number
}

export type WinLossReasonUpdateIn = {
  type?: string
  category?: string
  code?: string
  name?: string
  description?: string
  sort_order?: number
}

export type CampaignOut = {
  id: number
  code: string
  name: string
  type: string
  objective?: string
  target_audience?: string
  channel?: string
  status: string
  start_date: string
  end_date: string
  budget: number
  actual_cost: number
  expected_revenue: number
  actual_revenue: number
  currency: string
  target_leads_count?: number
  landing_url?: string
  utm_source?: string
  utm_campaign?: string
  owner_user_id?: number
  remark?: string
  created_at: string
}

export type CampaignCreateIn = {
  name: string
  type: string
  start_date: string
  end_date: string
  budget?: number
  currency?: string
  objective?: string
  target_audience?: string
  channel?: string
  status?: string
  expected_revenue?: number
  target_leads_count?: number
  landing_url?: string
  utm_source?: string
  utm_campaign?: string
  owner_user_id?: number
  remark?: string
}

export type CampaignUpdateIn = Omit<Partial<CampaignCreateIn>, 'name' | 'type'> & {
  name?: string
  type?: string
}

export type SalesTargetOut = {
  id: number
  period_type: string
  period_start: string
  period_end: string
  dimension: string
  dimension_id?: number
  metric: string
  target_value: number
  actual_value?: number
  achievement_pct?: number
  currency: string
  owner_user_id?: number
  created_at: string
}

export type SalesTargetCreateIn = {
  period_type: string
  period_start: string
  period_end: string
  dimension: string
  dimension_id?: number
  metric: string
  target_value: number
  currency?: string
  owner_user_id?: number
}

export type SalesTargetUpdateIn = Partial<SalesTargetCreateIn>

export type CustomerProfileOut = {
  customer: {
    id: number
    code: string
    name: string
    contact?: string
    phone?: string
    industry?: string
    level?: string
  }
  profile: {
    health_score: number
    health_level: string
    risk_flag: string
    lifecycle_stage: string
    total_lifetime_value: number
    last_order_at?: string
    last_order_amount: number
    open_opportunity_count: number
    open_opportunity_amount: number
    active_contract_count: number
    overdue_payment_amount: number
  }
  timeline: any[]
}

// ============================================================
// CRM API Client
// ============================================================

export const crmApi = {
  // ==== Leads ====
  listCrmLeads(params: any) {
    return http.request<{ items: LeadOut[] }>({ url: '/admin/production/crm/leads', method: 'GET', params })
  },
  createCrmLead(data: LeadCreateIn) {
    return http.request<{ id: number; code: string }>({ url: '/admin/production/crm/leads', method: 'POST', data })
  },
  getCrmLead(id: number) {
    return http.request<LeadOut>({ url: `/admin/production/crm/leads/${id}`, method: 'GET' })
  },
  updateCrmLead(id: number, data: LeadUpdateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/leads/${id}`, method: 'PUT', data })
  },
  deleteCrmLead(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/leads/${id}`, method: 'DELETE' })
  },
  convertLead(id: number, data: LeadConvertIn) {
    return http.request<any>({ url: `/admin/production/crm/leads/${id}/convert`, method: 'POST', data })
  },
  claimCrmLeadFromPool(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/leads/${id}/claim`, method: 'POST' })
  },
  releaseCrmLeadToPool(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/leads/${id}/release`, method: 'POST' })
  },
  recycleLeadsToPool(days: number) {
    return http.request<{ count: number }>({ url: '/admin/production/crm/leads/public-pool/recycle', method: 'POST', params: { days } })
  },
  listLeadActivities(id: number) {
    return http.request<{ items: LeadActivityOut[] }>({ url: `/admin/production/crm/leads/${id}/activities`, method: 'GET' })
  },
  createLeadActivity(id: number, data: LeadActivityCreateIn) {
    return http.request<{ id: number }>({ url: `/admin/production/crm/leads/${id}/activities`, method: 'POST', data })
  },
  getLeadsSummary() {
    return http.request<LeadSummary>({ url: '/admin/production/crm/leads/stats/summary', method: 'GET' })
  },

  // ==== Leads aliases (compatibility with page naming) ====
  listLeads: (params: any) => crmApi.listCrmLeads(params),
  getLead: (id: number) => crmApi.getCrmLead(id),
  createLead: (data: LeadCreateIn) => crmApi.createCrmLead(data),
  updateLead: (id: number, data: LeadUpdateIn) => crmApi.updateCrmLead(id, data),
  deleteLead: (id: number) => crmApi.deleteCrmLead(id),
  claimLead: (id: number) => crmApi.claimCrmLeadFromPool(id),
  releaseLead: (id: number) => crmApi.releaseCrmLeadToPool(id),
  leadsSummary: () => crmApi.getLeadsSummary(),

  // ==== Quotations ====
  listCrmQuotations(params: any) {
    return http.request<{ items: QuotationOut[] }>({ url: '/admin/production/crm/quotations', method: 'GET', params })
  },
  createCrmQuotation(data: QuotationCreateIn) {
    return http.request<{ id: number; code: string }>({ url: '/admin/production/crm/quotations', method: 'POST', data })
  },
  getCrmQuotation(id: number) {
    return http.request<QuotationOut & { items: QuotationItemOut[] }>({
      url: `/admin/production/crm/quotations/${id}`,
      method: 'GET',
    })
  },
  updateCrmQuotation(id: number, data: QuotationUpdateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/quotations/${id}`, method: 'PUT', data })
  },
  createCrmQuotationNewVersion(id: number) {
    return http.request<{ id: number; code: string; version: number }>({
      url: `/admin/production/crm/quotations/${id}/new-version`,
      method: 'POST',
    })
  },
  sendCrmQuotation(id: number) {
    return http.request<{ ok: boolean; status: string }>({ url: `/admin/production/crm/quotations/${id}/send`, method: 'POST' })
  },
  rejectCrmQuotation(id: number, data: QuotationRejectIn) {
    return http.request<{ ok: boolean; status: string }>({ url: `/admin/production/crm/quotations/${id}/reject`, method: 'POST', data })
  },
  convertCrmQuotationToOrder(id: number) {
    return http.request<{ order_id: number; order_code: string }>({
      url: `/admin/production/crm/quotations/${id}/convert-to-order`,
      method: 'POST',
    })
  },

  // ==== Contracts ====
  listCrmContracts(params: any) {
    return http.request<{ items: ContractOut[] }>({ url: '/admin/production/crm/contracts', method: 'GET', params })
  },
  createCrmContract(data: ContractCreateIn) {
    return http.request<{ id: number; code: string }>({ url: '/admin/production/crm/contracts', method: 'POST', data })
  },
  getCrmContract(id: number) {
    return http.request<ContractOut & { payment_plans: PaymentPlanOut[] }>({
      url: `/admin/production/crm/contracts/${id}`,
      method: 'GET',
    })
  },
  updateCrmContract(id: number, data: ContractCreateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/contracts/${id}`, method: 'PUT', data })
  },
  renewCrmContract(id: number) {
    return http.request<{ id: number; code: string }>({ url: `/admin/production/crm/contracts/${id}/renew`, method: 'POST' })
  },
  terminateCrmContract(id: number) {
    return http.request<{ ok: boolean; status: string }>({ url: `/admin/production/crm/contracts/${id}/terminate`, method: 'POST' })
  },
  deleteCrmContract(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/contracts/${id}`, method: 'DELETE' })
  },
  recordCrmContractPayment(id: number, planId: number, data: PaymentRecordIn) {
    return http.request<{ ok: boolean }>({
      url: `/admin/production/crm/contracts/${id}/payment-plans/${planId}/record`,
      method: 'POST',
      data,
    })
  },

  // ==== Win/Loss Reasons ====
  listCrmWinLossReasons(params: any) {
    return http.request<{ items: WinLossReasonOut[] }>({ url: '/admin/production/crm/win-loss-reasons', method: 'GET', params })
  },
  createCrmWinLossReason(data: WinLossReasonCreateIn) {
    return http.request<{ id: number; code: string }>({ url: '/admin/production/crm/win-loss-reasons', method: 'POST', data })
  },
  updateCrmWinLossReason(id: number, data: WinLossReasonUpdateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/win-loss-reasons/${id}`, method: 'PUT', data })
  },
  deleteCrmWinLossReason(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/win-loss-reasons/${id}`, method: 'DELETE' })
  },

  // ==== Campaigns ====
  listCrmCampaigns(params: any) {
    return http.request<{ items: CampaignOut[] }>({ url: '/admin/production/crm/campaigns', method: 'GET', params })
  },
  createCrmCampaign(data: CampaignCreateIn) {
    return http.request<{ id: number; code: string }>({ url: '/admin/production/crm/campaigns', method: 'POST', data })
  },
  getCrmCampaign(id: number) {
    return http.request<CampaignOut>({ url: `/admin/production/crm/campaigns/${id}`, method: 'GET' })
  },
  updateCrmCampaign(id: number, data: CampaignUpdateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/campaigns/${id}`, method: 'PUT', data })
  },
  addCrmCampaignMembers(id: number, members: any[]) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/campaigns/${id}/members`, method: 'POST', data: { members } })
  },
  listCrmCampaignMembers(id: number) {
    return http.request<{ items: any[] }>({ url: `/admin/production/crm/campaigns/${id}/members`, method: 'GET' })
  },
  removeCrmCampaignMember(id: number, memberType: string, memberId: number) {
    return http.request<{ ok: boolean }>({
      url: `/admin/production/crm/campaigns/${id}/members/${memberType}/${memberId}`,
      method: 'DELETE',
    })
  },
  recalculateCrmCampaignRoi(id: number) {
    return http.request<any>({ url: `/admin/production/crm/campaigns/${id}/recalculate-roi`, method: 'POST' })
  },

  // ==== Campaign aliases (compatibility with page naming) ====
  createCrmCampaignMember: (id: number, member: any) => crmApi.addCrmCampaignMembers(id, [member]),
  deleteCrmCampaignMember: (id: number, memberType: string, memberId: number) => crmApi.removeCrmCampaignMember(id, memberType, memberId),
  deleteCrmCampaign: (id: number) => http.request<{ ok: boolean }>({ url: `/admin/production/crm/campaigns/${id}`, method: 'DELETE' }),

  // ==== Sales Targets ====
  listCrmSalesTargets(params: any) {
    return http.request<{ items: SalesTargetOut[] }>({ url: '/admin/production/crm/sales-targets', method: 'GET', params })
  },
  createCrmSalesTarget(data: SalesTargetCreateIn) {
    return http.request<{ id: number }>({ url: '/admin/production/crm/sales-targets', method: 'POST', data })
  },
  getCrmSalesTarget(id: number) {
    return http.request<SalesTargetOut>({ url: `/admin/production/crm/sales-targets/${id}`, method: 'GET' })
  },
  updateCrmSalesTarget(id: number, data: SalesTargetUpdateIn) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/sales-targets/${id}`, method: 'PUT', data })
  },
  deleteCrmSalesTarget(id: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/crm/sales-targets/${id}`, method: 'DELETE' })
  },
  dashboardCrmSalesTargets(periodType: string) {
    return http.request<any>({ url: '/admin/production/crm/dashboard/sales-targets', method: 'GET', params: { period_type: periodType } })
  },

  // ==== Customer profile ====
  getCustomerProfile(customerId: number) {
    return http.request<CustomerProfileOut>({ url: `/admin/production/customers/${customerId}/profile`, method: 'GET' })
  },
  recalculateCustomerProfile(customerId: number) {
    return http.request<{ ok: boolean }>({ url: `/admin/production/customers/${customerId}/profile/recalculate`, method: 'POST' })
  },
  listCustomerContracts(customerId: number) {
    return http.request<{ items: ContractOut[] }>({ url: `/admin/production/crm/customers/${customerId}/contracts`, method: 'GET' })
  },
  listCustomerQuotations(customerId: number) {
    return http.request<{ items: QuotationOut[] }>({ url: `/admin/production/crm/customers/${customerId}/quotations`, method: 'GET' })
  },
}
