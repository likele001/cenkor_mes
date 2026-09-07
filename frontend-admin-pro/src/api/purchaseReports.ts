// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { http } from '@/utils/http'

export type PurchaseStatisticsOut = {
  total_orders: number
  total_amount: number
  pending_count: number
  completed_count: number
}

export const purchaseReportsApi = {
  statistics: () => http.request<PurchaseStatisticsOut>({ url: '/purchase/reports/statistics', method: 'GET' }),
}
