// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
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

/** 留痕覆盖的单据类型（与后端 approval_records.biz_type 一致） */
export const TRAIL_BIZ_TYPES: Record<string, string> = {
  order: '订单',
  purchase_order: '采购单',
  warehouse_entry: '入库单',
  statement: '客户对账单',
  supplier_statement: '供应商对账单',
  salary_slip: '工资条',
  mrp_plan: 'MRP 计划',
}

export const TRAIL_ACTIONS: Record<string, string> = {
  submit: '提交',
  confirm: '确认',
  reject: '驳回',
  cancel: '作废',
  receive: '收货',
  return: '退货',
  pay: '核销/发放',
  unpay: '撤销发放',
  reverse: '冲销',
  sign: '签收',
  reset: '重置',
  claim: '客户声明已付',
  ack: '客户确认',
  compute: '需求计算',
  convert: '转采购',
}

export type ApprovalRecordOut = {
  id: number
  biz_type: string
  biz_id: number
  biz_code: string | null
  action: string
  from_status: string | null
  to_status: string | null
  operator_id: number | null
  operator_name: string | null
  channel: string
  reason: string | null
  detail: Record<string, any> | null
  created_at: string
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
  listRecords(params: {
    biz_type?: string
    biz_id?: number
    action?: string
    operator_id?: number
    offset?: number
    limit?: number
  }) {
    return http.request<{ items: ApprovalRecordOut[]; total: number }>({
      url: '/admin/approval/records', method: 'GET', params,
    })
  },
}
