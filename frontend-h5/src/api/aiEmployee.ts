import { apiGet, apiPost } from '@/utils/http'

const AI_TIMEOUT_MS = 120_000

export type AiEmployeeItem = {
  id: number
  name: string
  avatar_url: string | null
  role_desc: string | null
  welcome_message: string | null
  status: string
}

export type AiEmployeeConversationItem = {
  id: number
  ai_employee_id: number
  channel: string
  title: string | null
  created_at: string
  updated_at: string
}

export type AiEmployeeChatOut = {
  conversation_id: number
  reply: string
  tool_calls_used: string[] | null
  tokens_in: number | null
  tokens_out: number | null
}

export function listAiEmployees() {
  return apiGet<{ items: AiEmployeeItem[] }>('/h5/ai-employees')
}

export function aiEmployeeChat(employeeId: number, data: { message: string; conversation_id?: number; model_code?: string }) {
  return apiPost<AiEmployeeChatOut>(`/h5/ai-employees/${employeeId}/chat`, data, { timeout: AI_TIMEOUT_MS })
}

export function listAiEmployeeConversations(employeeId: number) {
  return apiGet<{ items: AiEmployeeConversationItem[] }>(`/h5/ai-employees/${employeeId}/conversations`)
}

export function deleteAiEmployeeConversation(conversationId: number) {
  return apiPost<{ ok: boolean }>(`/h5/ai-employees/conversations/${conversationId}`, {})
}
