// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
// 平台 AI 配置层 API（波次 0）：网关 / 模型 / 总开关 / Prompt / 连通性测试。
// 后端挂载于 /api/ai（匹配 ai.ts 契约），非 /admin 前缀。
import { http } from '@/utils/http'

export type AiGatewaySettings = {
  enabled: boolean
  base_url: string
  api_key_configured: boolean
  api_key_masked: string
  timeout_seconds: number
}

export type AiGatewayOut = {
  id: number
  code: string
  display_name: string
  base_url: string
  api_key_configured: boolean
  api_key_masked: string
  enabled: boolean
  is_default: boolean
  timeout_seconds: number
  sort_order: number
}

export type AiModelOut = {
  id: number
  gateway_id: number
  code: string
  display_name: string
  model_id: string
  is_vision: boolean
  is_default: boolean
  is_active: boolean
  sort_order: number
}

export const aiConfigApi = {
  getSettings: () => http.request<AiGatewaySettings>({ url: '/ai/gateway-settings', method: 'GET' }),
  saveSettings: (data: Partial<AiGatewaySettings>) =>
    http.request<AiGatewaySettings>({ url: '/ai/gateway-settings', method: 'PUT', data }),

  listGateways: () => http.request<{ items: AiGatewayOut[] }>({ url: '/ai/gateways', method: 'GET' }),
  createGateway: (data: Record<string, unknown>) =>
    http.request<AiGatewayOut>({ url: '/ai/gateways', method: 'POST', data }),
  updateGateway: (id: number, data: Record<string, unknown>) =>
    http.request<AiGatewayOut>({ url: `/ai/gateways/${id}`, method: 'PUT', data }),
  deleteGateway: (id: number) => http.request<void>({ url: `/ai/gateways/${id}`, method: 'DELETE' }),
  setDefaultGateway: (id: number) =>
    http.request<AiGatewayOut>({ url: `/ai/gateways/${id}/set-default`, method: 'POST' }),

  // 管理页用：完整模型条目（含 vision/停用），可按网关过滤
  listModels: (gatewayId?: number) =>
    http.request<{ items: AiModelOut[] }>({
      url: '/ai/model-entries',
      method: 'GET',
      params: gatewayId ? { gateway_id: gatewayId } : undefined,
    }),
  createModel: (data: Record<string, unknown>) =>
    http.request<AiModelOut>({ url: '/ai/models', method: 'POST', data }),
  updateModel: (id: number, data: Record<string, unknown>) =>
    http.request<AiModelOut>({ url: `/ai/models/${id}`, method: 'PUT', data }),
  deleteModel: (id: number) => http.request<void>({ url: `/ai/models/${id}`, method: 'DELETE' }),
  setDefaultModel: (id: number) =>
    http.request<AiModelOut>({ url: `/ai/models/${id}/set-default`, method: 'POST' }),

  getPromptSettings: () =>
    http.request<{ prompt: string; max_length: number }>({ url: '/ai/prompt-settings', method: 'GET' }),
  savePromptSettings: (prompt: string) =>
    http.request<{ prompt: string; max_length: number }>({ url: '/ai/prompt-settings', method: 'PUT', data: { prompt } }),

  testConnection: (data: { gateway_id?: number; model_code?: string }) =>
    http.request<{ ok: boolean; reply: string; tokens_in: number | null; tokens_out: number | null }>({
      url: '/ai/test-connection',
      method: 'POST',
      data,
    }),
}
