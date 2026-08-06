import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type ApprovalStep = {
  id: number; step_order: number; approver_role: string
  is_required: boolean; can_skip: boolean; label: string | null
}

export type ApprovalFlowOut = {
  id: number; name: string; biz_type: string
  is_active: boolean; steps: ApprovalStep[]
  created_at: string; updated_at: string
}

export const BIZ_TYPES: Record<string, string> = {
  report: '报工审核', order: '订单审批', purchase: '采购审批',
}

export const ROLE_LABELS: Record<string, string> = {
  leader: '班组长', qc: '质检员', manager: '经理',
}

export const approvalApi = {
  list(biz_type?: string) {
    return http.request<ListResp<ApprovalFlowOut>>({ url: '/admin/approval', method: 'GET', params: biz_type ? { biz_type } : {} })
  },
  create(data: { name: string; biz_type: string; is_active?: boolean }) {
    return http.request<{ id: number; name: string }>({ url: '/admin/approval', method: 'POST', data })
  },
  get(id: number) { return http.request<ApprovalFlowOut>({ url: `/admin/approval/${id}`, method: 'GET' }) },
  update(id: number, data: { name?: string; is_active?: boolean }) {
    return http.request<ApprovalFlowOut>({ url: `/admin/approval/${id}`, method: 'PUT', data })
  },
  delete(id: number) { return http.request<{ deleted: boolean }>({ url: `/admin/approval/${id}`, method: 'DELETE' }) },
  setSteps(id: number, steps: { approver_role: string; is_required?: boolean; can_skip?: boolean; label?: string }[]) {
    return http.request<{ count: number }>({ url: `/admin/approval/${id}/steps`, method: 'PUT', data: { steps } })
  },
}
