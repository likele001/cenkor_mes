import { request } from '../request'
import { fileUrl } from '@/api/files'

const AI_TIMEOUT_MS = 120_000

export type ReportAiCheckOut = {
  ok?: boolean
  hints?: string[]
  suggest_remark?: string
  reply?: string
}

export type AiHelpOut = {
  answer: string
  sources: Array<{ source: string; title: string; snippet?: string }>
}

export type AiChatOut = {
  conversation_id: number
  reply: string
}

export type PhotoCountOut = {
  ok: boolean
  count: number
  confidence: 'high' | 'medium' | 'low'
  per_image: number[]
  note?: string | null
  image_count: number
  reply?: string
  error?: string
}

export type DefectClassifyOut = {
  ok: boolean
  defect_code_id: number | null
  defect_code?: string | null
  defect_name?: string | null
  severity?: string | null
  confidence: 'high' | 'medium' | 'low'
  description?: string | null
  image_count: number
  reply?: string
  error?: string
}

export type VoiceParseOut = {
  good_qty: number | null
  bad_qty: number | null
  result_type: 'good' | 'bad' | 'mixed' | string
  remark?: string | null
  defect_keywords: string[]
  summary?: string
  reply?: string
}

export function reportAiCheck(data: {
  task_id: number
  result_type: string
  remark?: string
  good_qty?: number
  bad_qty?: number
}) {
  return request<ReportAiCheckOut>('/h5/ai/report/check', {
    method: 'POST',
    data,
    timeout: AI_TIMEOUT_MS,
  })
}

export function aiHelp(question: string) {
  return request<AiHelpOut>('/h5/ai/help', {
    method: 'POST',
    data: { question },
    timeout: AI_TIMEOUT_MS,
  })
}

export function aiChat(data: { message: string; conversation_id?: number }) {
  return request<AiChatOut>('/h5/ai/chat', {
    method: 'POST',
    data: { scene: 'boss_qa', ...data },
    admin: true,
    timeout: AI_TIMEOUT_MS,
  })
}

export function photoAiCount(data: { image_urls: string[]; task_id?: number; hint?: string }) {
  return request<PhotoCountOut>('/h5/ai/report/photo-count', {
    method: 'POST',
    data,
    timeout: AI_TIMEOUT_MS,
  })
}

export function defectAiClassify(data: { image_urls: string[]; task_id?: number; remark?: string }) {
  return request<DefectClassifyOut>('/h5/ai/report/defect-classify', {
    method: 'POST',
    data,
    timeout: AI_TIMEOUT_MS,
  })
}

export function voiceParseReport(data: { text: string; task_id?: number }) {
  return request<VoiceParseOut>('/h5/ai/report/voice-parse', {
    method: 'POST',
    data,
    timeout: AI_TIMEOUT_MS,
  })
}

/** 将 attachment id 转换为后端可访问的图片 URL（用于 AI 调用） */
export function attachmentIdToUrl(id: number): string {
  return fileUrl(id) + '?download=true'
}
