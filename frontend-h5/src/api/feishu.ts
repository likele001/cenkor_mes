// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { apiGet, apiPost } from '@/utils/http'

export type ChannelStatus = {
  available: boolean
  bound: boolean
  bound_at?: string | null
  userid?: string
}

export type BindStatusOut = {
  feishu: ChannelStatus & { free?: boolean; enabled?: boolean; bot_open_link?: string }
  wecom: ChannelStatus
  dingtalk: ChannelStatus
}

/** 飞书（核心免费）+ 企微/钉钉（付费扩展开关）绑定状态 */
export function getBindStatus() {
  return apiGet<BindStatusOut>('/h5/feishu/bind-status')
}

/** 飞书 OAuth 绑定地址（未配置飞书应用时后端返回 400） */
export function getFeishuBindUrl() {
  return apiPost<{ authorize_url: string }>('/h5/feishu/bind-url')
}

/** 自助绑定企微/钉钉 userid（扩展未开通时后端返回 403） */
export function bindImUser(channel: 'wecom' | 'dingtalk', userid: string) {
  return apiPost<{ bound: boolean }>('/h5/im/bind', { channel, userid })
}
