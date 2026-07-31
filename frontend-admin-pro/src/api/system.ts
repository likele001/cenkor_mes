import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type RoleOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  permission_codes: string[]
}

export type PermissionOut = { id: number; code: string; name: string }

export type DepartmentOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  parent_id: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type UserOut = {
  id: number
  tenant_id: number
  department_id: number | null
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  salary_type: string
  hourly_rate: number | null
  created_at: string
  roles: { id: number; code: string; name: string }[]
  department: { id: number; code: string; name: string } | null
}

export type SettingOut = { id: number; tenant_id: number; key: string; value: any; updated_at: string }

export type AttachmentOut = {
  id: number
  tenant_id: number
  uploader_id: number
  storage_driver: string
  storage_key: string
  original_filename: string
  content_type: string
  size: number
  sha256: string
  created_at: string
  url?: string
  play_url?: string
}

export type OperationLogOut = {
  id: number
  tenant_id: number
  user_id: number
  username: string
  module: string
  action: string
  object_type: string | null
  object_id: number | null
  detail: string | null
  method: string
  path: string
  ip: string | null
  user_agent: string | null
  created_at: string
}

export type PrintTemplateOut = {
  id: number
  tenant_id: number
  code: string
  name: string
  template_type: string
  content: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export const systemApi = {
  listUsers(params: any) {
    return http.request<ListResp<UserOut>>({ url: '/admin/system/users', method: 'GET', params })
  },
  createUser(data: any) {
    return http.request<UserOut>({ url: '/admin/system/users', method: 'POST', data })
  },
  updateUser(id: number, data: any) {
    return http.request<UserOut>({ url: `/admin/system/users/${id}`, method: 'PUT', data })
  },
  disableUser(id: number) {
    return http.request<void>({ url: `/admin/system/users/${id}`, method: 'DELETE' })
  },

  listRoles(params: any) {
    return http.request<ListResp<RoleOut>>({ url: '/admin/system/roles', method: 'GET', params })
  },
  createRole(data: any) {
    return http.request<RoleOut>({ url: '/admin/system/roles', method: 'POST', data })
  },
  updateRole(id: number, data: any) {
    return http.request<RoleOut>({ url: `/admin/system/roles/${id}`, method: 'PUT', data })
  },
  deleteRole(id: number) {
    return http.request<void>({ url: `/admin/system/roles/${id}`, method: 'DELETE' })
  },
  setRolePermissions(id: number, data: any) {
    return http.request<RoleOut>({ url: `/admin/system/roles/${id}/permissions`, method: 'PUT', data })
  },

  listPermissions(params: any) {
    return http.request<ListResp<PermissionOut>>({ url: '/admin/system/permissions', method: 'GET', params })
  },
  createPermission(data: any) {
    return http.request<PermissionOut>({ url: '/admin/system/permissions', method: 'POST', data })
  },
  updatePermission(id: number, data: any) {
    return http.request<PermissionOut>({ url: `/admin/system/permissions/${id}`, method: 'PUT', data })
  },
  deletePermission(id: number) {
    return http.request<void>({ url: `/admin/system/permissions/${id}`, method: 'DELETE' })
  },

  listDepartments(params: any) {
    return http.request<ListResp<DepartmentOut>>({ url: '/admin/system/departments', method: 'GET', params })
  },
  createDepartment(data: any) {
    return http.request<DepartmentOut>({ url: '/admin/system/departments', method: 'POST', data })
  },
  updateDepartment(id: number, data: any) {
    return http.request<DepartmentOut>({ url: `/admin/system/departments/${id}`, method: 'PUT', data })
  },
  disableDepartment(id: number) {
    return http.request<void>({ url: `/admin/system/departments/${id}`, method: 'DELETE' })
  },

  getReportMediaSettings() {
    return http.request<{
      max_video_seconds: number
      max_video_mb: number
      max_video_count: number
      max_photo_count: number
      camera_only: boolean
    }>({ url: '/admin/system/report-media', method: 'GET' })
  },
  getReportModeSettings() {
    return http.request<{
      default_mode: string
      default_mode_label: string
      modes: { value: string; label: string; help: string; enabled: boolean }[]
    }>({ url: '/admin/system/report-mode', method: 'GET' })
  },
  saveReportModeSettings(data: { default_mode: string }) {
    return http.request({ url: '/admin/system/report-mode', method: 'PUT', data })
  },
  saveReportMediaSettings(data: {
    max_video_seconds: number
    max_video_mb: number
    max_video_count: number
    max_photo_count: number
    camera_only: boolean
  }) {
    return http.request({ url: '/admin/system/report-media', method: 'PUT', data })
  },
  getWechatMiniappSettings() {
    return http.request<{
      app_id: string
      app_secret_configured: boolean
      app_secret_masked: string
      env_fallback_app_id: string | null
    }>({ url: '/admin/system/wechat-miniapp', method: 'GET' })
  },
  saveWechatMiniappSettings(data: { app_id: string; app_secret?: string }) {
    return http.request({ url: '/admin/system/wechat-miniapp', method: 'PUT', data })
  },
  listSettings(params: any) {
    return http.request<ListResp<SettingOut>>({ url: '/admin/system/settings', method: 'GET', params })
  },
  getSetting(key: string) {
    return http.request<SettingOut | null>({ url: `/admin/system/settings/${encodeURIComponent(key)}`, method: 'GET' })
  },
  upsertSetting(key: string, data: any) {
    return http.request<SettingOut>({ url: `/admin/system/settings/${encodeURIComponent(key)}`, method: 'PUT', data })
  },
  deleteSetting(key: string) {
    return http.request<void>({ url: `/admin/system/settings/${encodeURIComponent(key)}`, method: 'DELETE' })
  },

  listPrintTemplates(params: any) {
    return http.request<ListResp<PrintTemplateOut>>({ url: '/admin/system/print-templates', method: 'GET', params })
  },
  createPrintTemplate(data: any) {
    return http.request<PrintTemplateOut>({ url: '/admin/system/print-templates', method: 'POST', data })
  },
  updatePrintTemplate(id: number, data: any) {
    return http.request<PrintTemplateOut>({ url: `/admin/system/print-templates/${id}`, method: 'PUT', data })
  },
  disablePrintTemplate(id: number) {
    return http.request<void>({ url: `/admin/system/print-templates/${id}`, method: 'DELETE' })
  },
  renderPrintTemplate(id: number, data: any) {
    return http.request<{ html: string }>({ url: `/admin/system/print-templates/${id}/render`, method: 'POST', data })
  },
  renderPrintTemplatePdf(id: number, data: any) {
    return http.request<{ attachment_id: number; filename: string; url: string }>({
      url: `/admin/system/print-templates/${id}/render-pdf`,
      method: 'POST',
      data,
    })
  },

  listAttachments(params: any) {
    return http.request<ListResp<AttachmentOut>>({ url: '/admin/system/attachments', method: 'GET', params })
  },
  uploadAttachment(file: File) {
    const form = new FormData()
    form.append('file', file)
    return http.request<AttachmentOut>({
      url: '/admin/system/attachments/upload',
      method: 'POST',
      data: form,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getAttachment(id: number) {
    return http.request<AttachmentOut>({ url: `/admin/system/attachments/${id}`, method: 'GET' })
  },
  getAttachmentUrl(id: number, expires?: number) {
    return http.request<{ url: string; play_url: string; expires: number }>({
      url: `/admin/system/attachments/${id}/url`,
      method: 'GET',
      params: expires ? { expires } : undefined,
    })
  },
  deleteAttachment(id: number) {
    return http.request<void>({ url: `/admin/system/attachments/${id}`, method: 'DELETE' })
  },

  listOperationLogs(params: any) {
    return http.request<ListResp<OperationLogOut>>({ url: '/admin/system/operation-logs', method: 'GET', params })
  },

  listNotifications(params: any) {
    return http.request<ListResp<any>>({ url: '/admin/system/notifications', method: 'GET', params })
  },
  markNotificationRead(notification_id: number) {
    return http.request<{ updated: number }>({ url: '/admin/system/notifications/read', method: 'POST', params: { notification_id } })
  },
  markAllNotificationsRead() {
    return http.request<{ updated: number }>({ url: '/admin/system/notifications/read-all', method: 'POST' })
  },
  getUnreadNotificationCount() {
    return http.request<{ count: number }>({ url: '/admin/system/notifications/unread-count', method: 'GET' })
  },

  listAttendanceRecords(params: any) {
    return http.request<ListResp<any>>({ url: '/admin/system/attendance-records', method: 'GET', params })
  },
  createAttendanceRecord(data: any) {
    return http.request<any>({ url: '/admin/system/attendance-records', method: 'POST', data })
  },
  updateAttendanceRecord(id: number, data: any) {
    return http.request<any>({ url: `/admin/system/attendance-records/${id}`, method: 'PUT', data })
  },
  getAttendanceGeofence() {
    return http.request<{ enabled: boolean; lat: number | null; lng: number | null; radius_m: number }>({
      url: '/admin/system/attendance-records/geofence',
      method: 'GET',
    })
  },
  setAttendanceGeofence(data: { enabled: boolean; lat?: number | null; lng?: number | null; radius_m?: number | null }) {
    return http.request<{ saved: boolean }>({
      url: '/admin/system/attendance-records/geofence',
      method: 'PUT',
      data,
    })
  },

  listSkills(params: any) {
    return http.request<ListResp<any>>({ url: '/admin/system/skills', method: 'GET', params })
  },
  createSkill(data: any) {
    return http.request<any>({ url: '/admin/system/skills', method: 'POST', data })
  },
  updateSkill(id: number, data: any) {
    return http.request<any>({ url: `/admin/system/skills/${id}`, method: 'PUT', data })
  },
  disableSkill(id: number) {
    return http.request<void>({ url: `/admin/system/skills/${id}`, method: 'DELETE' })
  },
  listSkillUsers(params: any) {
    return http.request<ListResp<any>>({ url: '/admin/system/skills/users', method: 'GET', params })
  },
  getUserSkills(userId: number) {
    return http.request<any>({ url: `/admin/system/skills/users/${userId}/skills`, method: 'GET' })
  },
  setUserSkills(userId: number, skill_ids: number[]) {
    return http.request<any>({ url: `/admin/system/skills/users/${userId}/skills`, method: 'PUT', data: { skill_ids } })
  },
  exportUsers(params?: any) {
    return http.downloadBlob({ url: '/admin/system/users/export', method: 'GET', params })
  },
  exportRoles(params?: any) {
    return http.downloadBlob({ url: '/admin/system/roles/export', method: 'GET', params })
  },
  /** 预览下一业务编号（不占用序号） */
  nextCode(bizType: string) {
    return http.request<{ code: string; biz_type: string }>({
      url: '/admin/system/codes/next',
      method: 'GET',
      params: { biz_type: bizType },
    })
  },
}
