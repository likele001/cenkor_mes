// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

const P = '/admin/production'

export type BasicOption = { id: number; code: string; name: string; label: string }
export type BasicList<T = any> = { items: T[]; total: number }
export type BasicParams = Record<string, unknown>

const get = <T>(url: string, params?: BasicParams) =>
  http.request<T>({ url: `${P}${url}`, method: 'GET', params })
const post = <T>(url: string, data?: unknown) =>
  http.request<T>({ url: `${P}${url}`, method: 'POST', data: data ?? {} })
const put = <T>(url: string, data?: unknown) =>
  http.request<T>({ url: `${P}${url}`, method: 'PUT', data: data ?? {} })
const del = <T>(url: string) =>
  http.request<T>({ url: `${P}${url}`, method: 'DELETE' })

export const basicsApi = {
  // 通用下拉：设备 / 物料 / 供应商 / 工序 / BOM
  options(type: string, keyword?: string) {
    return get<BasicOption[]>('/options', { type, keyword })
  },

  // ── 返工单 ──
  reworkStats() { return get<any>('/reworks/stats') },
  reworkMeta() { return get<any>('/reworks/meta') },
  listReworks(params: BasicParams) { return get<BasicList>('/reworks', params) },
  getRework(id: number) { return get<any>(`/reworks/${id}`) },
  reworksByDisposition(id: number) { return get<any[]>(`/reworks/by-disposition/${id}`) },
  startRework(id: number, data: { assigned_user_id?: number } = {}) {
    return post<any>(`/reworks/${id}/start`, data)
  },
  completeRework(id: number, data: { done_qty?: number } = {}) {
    return post<any>(`/reworks/${id}/complete`, data)
  },
  cancelRework(id: number, data: { reason?: string } = {}) {
    return post<any>(`/reworks/${id}/cancel`, data)
  },

  // ── 物料替代 ──
  listSubstitutes(params: BasicParams) { return get<BasicList>('/substitutes', params) },
  suggestSubstitutes(params: BasicParams) { return get<any[]>('/substitutes/suggest', params) },
  createSubstitute(data: unknown) { return post<any>('/substitutes', data) },
  updateSubstitute(id: number, data: unknown) { return put<any>(`/substitutes/${id}`, data) },
  deleteSubstitute(id: number) { return del<any>(`/substitutes/${id}`) },

  // ── 工程变更 ECN ──
  ecnStats() { return get<any>('/ecn/stats') },
  ecnMeta() { return get<any>('/ecn/meta') },
  listEcn(params: BasicParams) { return get<BasicList>('/ecn', params) },
  createEcn(data: unknown) { return post<any>('/ecn', data) },
  updateEcn(id: number, data: unknown) { return put<any>(`/ecn/${id}`, data) },
  deleteEcn(id: number) { return del<any>(`/ecn/${id}`) },
  ecnAction(id: number, action: string, data: unknown = {}) {
    return post<any>(`/ecn/${id}/${action}`, data)
  },

  // ── 设备停机记录 ──
  downtimeStats(params: BasicParams = {}) { return get<any>('/downtimes/stats', params) },
  downtimeMeta() { return get<any>('/downtimes/meta') },
  listDowntimes(params: BasicParams) { return get<BasicList>('/downtimes', params) },
  createDowntime(data: unknown) { return post<any>('/downtimes', data) },
  updateDowntime(id: number, data: unknown) { return put<any>(`/downtimes/${id}`, data) },
  closeDowntime(id: number, data: { ended_at?: string } = {}) {
    return post<any>(`/downtimes/${id}/close`, data)
  },
  deleteDowntime(id: number) { return del<any>(`/downtimes/${id}`) },

  // ── 供应商评分 ──
  scoreStats(params: BasicParams = {}) { return get<any>('/supplier-scores/stats', params) },
  scoreMeta() { return get<any>('/supplier-scores/meta') },
  listScores(params: BasicParams) { return get<BasicList>('/supplier-scores', params) },
  createScore(data: unknown) { return post<any>('/supplier-scores', data) },
  updateScore(id: number, data: unknown) { return put<any>(`/supplier-scores/${id}`, data) },
  deleteScore(id: number) { return del<any>(`/supplier-scores/${id}`) },

  // ── 检验单联动（③ 终审依据 / ④ OQC·FAI 来源）──
  reportInspections(reportId: number) {
    return get<BasicList>(`/reports/${reportId}/inspections`)
  },
  inspectionReportOptions(params: BasicParams = {}) {
    return get<any[]>('/inspections/report-options', params)
  },
  createInspectionFromReport(data: unknown) {
    return post<any>('/inspections/from-report', data)
  },
  inspectionSourceSummary(params: BasicParams) {
    return get<any>('/inspections/source-summary', params)
  },
}
