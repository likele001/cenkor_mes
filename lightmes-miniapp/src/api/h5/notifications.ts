import { apiGet, apiPostQuery } from '../request'

export function getNotifications(params?: { unread?: boolean; offset?: number; limit?: number }) {
  return apiGet<{ items: unknown[] }>('/h5/notifications', params as Record<string, unknown>)
}

export function getUnreadCount() {
  return apiGet<{ count: number }>('/h5/notifications/unread-count')
}

export function markRead(notificationId: number) {
  return apiPostQuery('/h5/notifications/read', { notification_id: notificationId })
}

export function markAllRead() {
  return apiPostQuery('/h5/notifications/read-all')
}
