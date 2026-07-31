import { apiDel, apiGet, apiPost, apiPostQuery } from '../request'

export const adminApi = {
  dashboardSummary: () => apiGet<Record<string, unknown>>('/dashboard/summary', undefined, true),
  kanbanOrders: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/dashboard/kanban/orders', p, true),
  kanbanOrderDetail: (id: number) => apiGet<Record<string, unknown>>(`/dashboard/kanban/orders/${id}`, undefined, true),
  charts: (days?: number) => apiGet<Record<string, unknown>>('/dashboard/charts', days ? { days } : undefined, true),

  listOrders: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/orders', p, true),
  getOrder: (id: number) => apiGet<Record<string, unknown>>(`/admin/production/orders/${id}`, undefined, true),
  confirmOrder: (id: number) =>
    apiPost<{
      order_id?: number
      automation_plan_id?: number | null
      automation_pipeline_ran?: boolean
    }>(`/admin/production/orders/${id}/confirm`, {}, true),
  rejectOrder: (id: number, reason: string) =>
    apiPostQuery<{ id: number; status: string }>(`/admin/production/orders/${id}/reject`, { reason }, true),
  deleteOrder: (id: number) => apiDel<null>(`/admin/production/orders/${id}`, true),
  listWorkOrders: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/work-orders', p, true),
  listTasks: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/tasks', p, true),
  listReports: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/reports', p, true),
  getReport: (id: number) => apiGet<Record<string, unknown>>(`/admin/production/reports/${id}`, undefined, true),
  approveReport: (id: number) => apiPost(`/admin/production/reports/${id}/leader-approve`, {}, true),
  qcApproveReport: (id: number) => apiPost(`/admin/production/reports/${id}/qc-approve`, {}, true),
  rejectReport: (id: number, reason: string) => apiPost(`/admin/production/reports/${id}/reject`, { reason }, true),
  listReportUnits: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/report-units', p, true),
  listCustomers: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/production/customers', p, true),
  getCustomer: (id: number) => apiGet<Record<string, unknown>>(`/admin/production/customers/${id}`, undefined, true),
  listProducts: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/products', p, true),
  listSkus: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/skus', p, true),
  getSkuBatchTemplate: (productId: number) =>
    apiGet<{
      product: Record<string, unknown> | null
      route_name: string | null
      route_source: string
      processes: unknown[]
      existing_names: string[]
    }>('/admin/master/skus/batch-template', { product_id: productId }, true),
  batchCreateSkusWithPrices: (data: {
    product_id: number
    items: {
      code?: string | null
      name: string
      color?: string | null
      material?: string | null
      spec?: string | null
      remark?: string | null
      is_active?: boolean
      prices: { process_id: number; unit_price: string | number | null; is_active?: boolean }[]
    }[]
  }) =>
    apiPost<{ added: number; skipped: number; prices_created: number; prices_updated: number }>(
      '/admin/master/skus/batch-with-prices',
      data,
      true,
    ),
  listSuppliers: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/suppliers', p, true),
  listMaterials: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/materials', p, true),
  listBoms: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/boms', p, true),
  listProcesses: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/processes', p, true),
  listProcessRoutes: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/process-routes', p, true),
  listProcessPrices: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/master/process-prices', p, true),
  getPriceMatrix: (skuId: number) =>
    apiGet<{ sku: Record<string, unknown>; route_name: string | null; rows: unknown[] }>(
      '/admin/master/process-prices/matrix',
      { sku_id: skuId },
      true,
    ),
  batchSavePrices: (data: { sku_id: number; items: { process_id: number; unit_price: string | number | null; is_active?: boolean }[] }) =>
    apiPost<{ created: number; updated: number }>('/admin/master/process-prices/batch', data, true),
  listPlans: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/plans', p, true),
  listEquipment: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/equipment', p, true),
  listStocks: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/warehouse/stocks', p, true),
  listWarehouses: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/warehouse/warehouses', p, true),
  listPurchaseOrders: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/purchase/orders', p, true),
  listPurchaseStatements: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/purchase/statements', p, true),
  listFinanceStatements: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/finance/statements', p, true),
  listLedgers: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/finance/ledgers', p, true),
  getProfit: () => apiGet<Record<string, unknown>>('/admin/finance/profit', undefined, true),
  listUsers: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/users', p, true),
  listRoles: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/roles', p, true),
  listPermissions: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/permissions', p, true),
  listDepartments: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/departments', p, true),
  listDictionary: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/dictionary', p, true),
  listAttendanceRecords: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/attendance-records', p, true),
  listSkills: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/skills', p, true),
  getSettings: () => apiGet<Record<string, unknown>>('/admin/system/settings', undefined, true),
  listPrintTemplates: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/print-templates', p, true),
  listOperationLogs: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/admin/system/operation-logs', p, true),
  listNotifications: (p?: Record<string, unknown>) => apiGet<{ items: unknown[] }>('/h5/notifications', p, true),
  salarySummary: (p?: Record<string, unknown>) => apiGet('/admin/production/reports/salary/summary', p, true),
  salarySlips: (p?: Record<string, unknown>) => apiGet('/admin/production/reports/salary-slips', p, true),
  crmPool: (p?: Record<string, unknown>) => apiGet('/admin/production/crm/public-pool', p, true),
  crmOpportunityStats: () => apiGet('/admin/production/crm/opportunities/stats', undefined, true),
  crmTags: (p?: Record<string, unknown>) => apiGet('/admin/production/crm/tags', p, true),
  traceQuery: (code: string) => apiGet(`/admin/trace/query`, { code }, true),
  reportsSummary: (p?: Record<string, unknown>) => apiGet('/admin/reports/summary', p, true),
  reportsPurchase: (p?: Record<string, unknown>) => apiGet('/admin/reports/purchase', p, true),
}
