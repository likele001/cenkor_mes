import { apiGet, apiPost, apiPut, apiDel } from '@/api/request'

export type TemplateItem = {
  id?: number
  seq: number
  item_name: string
  item_type: string
  standard_value: string | null
  upper_limit: string | null
  lower_limit: string | null
  unit: string | null
  is_required: boolean
  remark: string | null
}

export type TemplateOut = {
  id: number
  code: string
  name: string
  description: string | null
  process_id: number | null
  product_id: number | null
  is_active: boolean
  items: TemplateItem[]
  created_at: string
  updated_at: string
}

export type DefectCodeOut = {
  id: number
  code: string
  name: string
  severity: string
  description: string | null
  is_active: boolean
}

export const SEVERITY_LABELS: Record<string, string> = {
  critical: '致命', major: '主要', minor: '次要',
}

export const ITEM_TYPE_LABELS: Record<string, string> = {
  pass_fail: '合格/不合格', measure: '测量值', text: '文本描述',
}

const TMPL_BASE = '/admin/production/inspection-templates'
const DEFECT_BASE = '/admin/production/defect-codes'

export const qualityApi = {
  listTemplates(params?: { process_id?: number; offset?: number; limit?: number }) {
    return apiGet<{ items: TemplateOut[] }>(TMPL_BASE, params as Record<string, unknown>, true)
  },
  getTemplate(id: number) {
    return apiGet<TemplateOut>(`${TMPL_BASE}/${id}`, undefined, true)
  },
  createTemplate(data: Record<string, unknown>) {
    return apiPost<TemplateOut>(TMPL_BASE, data, true)
  },
  updateTemplate(id: number, data: Record<string, unknown>) {
    return apiPut<TemplateOut>(`${TMPL_BASE}/${id}`, data, true)
  },
  deleteTemplate(id: number) {
    return apiDel<{ deleted: boolean }>(`${TMPL_BASE}/${id}`, true)
  },
  listDefectCodes(params?: { offset?: number; limit?: number }) {
    return apiGet<{ items: DefectCodeOut[] }>(DEFECT_BASE, params as Record<string, unknown>, true)
  },
  createDefectCode(data: Record<string, unknown>) {
    return apiPost<{ id: number }>(DEFECT_BASE, data, true)
  },
  updateDefectCode(id: number, data: Record<string, unknown>) {
    return apiPut<{ id: number }>(`${DEFECT_BASE}/${id}`, data, true)
  },
  deleteDefectCode(id: number) {
    return apiDel<{ deleted: boolean }>(`${DEFECT_BASE}/${id}`, true)
  },
}
