import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { i18n } from '@/locales'
import { tryRecoverStaleChunk } from '@/utils/chunk-reload'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: () => import('@/pages/LoginPage.vue'), meta: { public: true, title: () => i18n.global.t('menu.login') } },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/home',
    children: [
      { path: '', redirect: 'home' },
      { path: 'home', name: 'home', component: () => import('@/pages/HomePage.vue'), meta: { title: () => i18n.global.t('menu.home'), permissions: ['dashboard.view'] } },
      {
        path: 'dashboard/kanban',
        name: 'dashboard-kanban',
        component: () => import('@/pages/dashboard/KanbanOrdersPage.vue'),
        meta: { title: () => i18n.global.t('menu.kanban'), permissions: ['dashboard.view'] },
      },
      {
        path: 'dashboard/kanban/orders/:id',
        name: 'dashboard-kanban-order',
        component: () => import('@/pages/dashboard/KanbanOrderDetailPage.vue'),
        meta: { title: () => i18n.global.t('menu.orderProgress'), permissions: ['dashboard.view'] },
      },
      {
        path: 'dashboard/screen',
        name: 'dashboard-screen',
        component: () => import('@/pages/dashboard/DashboardScreenPage.vue'),
        meta: { title: () => i18n.global.t('menu.screen'), permissions: ['dashboard.view'] },
      },
      { path: 'reports', name: 'reports', component: () => import('@/pages/reports/DataReportsPage.vue'), meta: { title: () => i18n.global.t('menu.reportsOverview'), permissions: ['report.view'] } },
      { path: 'dashboard', redirect: '/dashboard/kanban' },

      { path: 'system/users', name: 'system-users', component: () => import('@/pages/system/UsersPage.vue'), meta: { title: () => i18n.global.t('menu.users'), permissions: ['user.manage'] } },
      { path: 'system/roles', name: 'system-roles', component: () => import('@/pages/system/RolesPage.vue'), meta: { title: () => i18n.global.t('menu.roles'), permissions: ['role.manage'] } },
      { path: 'system/permissions', name: 'system-permissions', component: () => import('@/pages/system/PermissionsPage.vue'), meta: { title: () => i18n.global.t('menu.permissions'), permissions: ['permission.manage'] } },
      { path: 'system/departments', name: 'system-departments', component: () => import('@/pages/system/DepartmentsPage.vue'), meta: { title: () => i18n.global.t('menu.departments'), permissions: ['department.manage'] } },
      { path: 'system/settings', name: 'system-settings', component: () => import('@/pages/system/SettingsPage.vue'), meta: { title: () => i18n.global.t('menu.settings'), permissions: ['setting.manage'] } },
      { path: 'system/cron-jobs', name: 'system-cron-jobs', component: () => import('@/pages/system/CronJobsPage.vue'), meta: { title: () => i18n.global.t('menu.cronJobs'), permissions: ['setting.manage'] } },
      { path: 'system/print-templates', name: 'system-print-templates', component: () => import('@/pages/system/PrintTemplatesPage.vue'), meta: { title: () => i18n.global.t('menu.printTemplates'), permissions: ['print_template.manage'] } },
      { path: 'system/notifications', name: 'system-notifications', component: () => import('@/pages/system/NotificationsPage.vue'), meta: { title: () => i18n.global.t('menu.notifications'), permissions: ['notification.view'] } },
      { path: 'system/attendance-records', name: 'system-attendance-records', component: () => import('@/pages/system/AttendanceRecordsPage.vue'), meta: { title: () => i18n.global.t('menu.attendanceRecords'), permissions: ['attendance.manage'] } },
      { path: 'system/skills', name: 'system-skills', component: () => import('@/pages/system/SkillsPage.vue'), meta: { title: () => i18n.global.t('menu.skills'), permissions: ['skill.manage'] } },
      { path: 'system/dictionary', name: 'system-dictionary', component: () => import('@/pages/system/DictionaryPage.vue'), meta: { title: () => i18n.global.t('menu.dictionary'), permissions: ['dict.manage'] } },
      { path: 'system/attachments', name: 'system-attachments', component: () => import('@/pages/system/AttachmentsPage.vue'), meta: { title: () => i18n.global.t('menu.attachments'), permissions: ['attachment.view'] } },
      { path: 'system/operation-logs', name: 'system-operation-logs', component: () => import('@/pages/system/OperationLogsPage.vue'), meta: { title: () => i18n.global.t('menu.operationLogs'), permissions: ['operation_log.view'] } },
      { path: 'system/about', name: 'system-about', component: () => import('@/pages/system/SystemAboutPage.vue'), meta: { title: () => i18n.global.t('menu.systemAbout'), permissions: ['setting.manage'] } },
      { path: 'system/crm-adapter', name: 'system-crm-adapter', component: () => import('@/pages/system/CrmAdapterPage.vue'), meta: { title: () => i18n.global.t('menu.crmAdapter'), permissions: ['setting.manage'] } },
      { path: 'system/crm-orders', name: 'system-crm-orders', component: () => import('@/pages/system/CrmOrdersPage.vue'), meta: { title: () => i18n.global.t('menu.crmOrders'), permissions: ['setting.manage'] } },
      { path: 'system/approval-flows', name: 'system-approval-flows', component: () => import('@/pages/system/ApprovalFlowsPage.vue'), meta: { title: () => i18n.global.t('menu.approvalFlows'), permissions: ['setting.manage'] } },
      { path: 'system/feishu-notify', name: 'system-feishu-notify', component: () => import('@/pages/system/FeishuNotifyPage.vue'), meta: { title: () => i18n.global.t('menu.feishuNotify'), permissions: ['setting.manage'] } },
      { path: 'system/wecom-notify', name: 'system-wecom-notify', component: () => import('@/pages/system/WecomNotifyPage.vue'), meta: { title: () => i18n.global.t('menu.wecomNotify'), permissions: ['setting.manage'] } },
      { path: 'system/dingtalk-notify', name: 'system-dingtalk-notify', component: () => import('@/pages/system/DingtalkNotifyPage.vue'), meta: { title: () => i18n.global.t('menu.dingtalkNotify'), permissions: ['setting.manage'] } },
      { path: 'system/message-center', name: 'system-message-center', component: () => import('@/pages/system/MessageCenterPage.vue'), meta: { title: () => i18n.global.t('menu.messageCenter'), permissions: ['notification.view'] } },
      { path: 'system/push-monitor', name: 'system-push-monitor', component: () => import('@/pages/system/PushMonitorPage.vue'), meta: { title: () => i18n.global.t('menu.pushMonitor'), permissions: ['setting.manage'] } },
      { path: 'account/profile', name: 'account-profile', component: () => import('@/pages/account/ProfilePage.vue'), meta: { title: () => i18n.global.t('menu.profile') } },

      { path: 'master/products', name: 'master-products', component: () => import('@/pages/master/ProductsPage.vue'), meta: { title: () => i18n.global.t('menu.products'), permissions: ['product.manage'] } },
      { path: 'master/skus', name: 'master-skus', component: () => import('@/pages/master/SkusPage.vue'), meta: { title: () => i18n.global.t('menu.skus'), permissions: ['sku.manage'] } },
      { path: 'master/skus/batch', name: 'master-skus-batch', component: () => import('@/pages/master/SkuBatchWithPricesPage.vue'), meta: { title: () => i18n.global.t('menu.skusBatch'), permissions: ['sku.manage', 'price.manage'] } },
      { path: 'master/suppliers', name: 'master-suppliers', component: () => import('@/pages/master/SuppliersPage.vue'), meta: { title: () => i18n.global.t('menu.suppliers'), permissions: ['supplier.manage'] } },
      { path: 'master/materials', name: 'master-materials', component: () => import('@/pages/master/MaterialsPage.vue'), meta: { title: () => i18n.global.t('menu.materials'), permissions: ['material.manage'] } },
      { path: 'master/boms', name: 'master-boms', component: () => import('@/pages/master/BomsPage.vue'), meta: { title: () => i18n.global.t('menu.boms'), permissions: ['bom.manage'] } },
      { path: 'master/processes', name: 'master-processes', component: () => import('@/pages/master/ProcessesPage.vue'), meta: { title: () => i18n.global.t('menu.processes'), permissions: ['process.manage'] } },
      { path: 'master/process-routes', name: 'master-process-routes', component: () => import('@/pages/master/ProcessRoutesPage.vue'), meta: { title: () => i18n.global.t('menu.processRoutes'), permissions: ['product.manage'] } },
      { path: 'master/process-prices', name: 'master-process-prices', component: () => import('@/pages/master/ProcessPricesPage.vue'), meta: { title: () => i18n.global.t('menu.processPrices'), permissions: ['price.manage'] } },

      { path: 'production/shifts', name: 'production-shifts', component: () => import('@/pages/production/ShiftsPage.vue'), meta: { title: () => i18n.global.t('menu.shifts'), permissions: ['attendance.manage'] } },
      {
        path: 'production/customers',
        name: 'production-customers',
        component: () => import('@/pages/production/CustomersPage.vue'),
        meta: { title: () => i18n.global.t('menu.customers'), permissions: ['customer.manage', 'crm.sales'] },
      },
      {
        path: 'production/customers/:id',
        name: 'production-customer-detail',
        component: () => import('@/pages/production/CustomerDetailPage.vue'),
        meta: { title: () => i18n.global.t('menu.customerDetail'), permissions: ['customer.manage', 'crm.sales'] },
      },
      {
        path: 'production/orders',
        name: 'production-orders',
        component: () => import('@/pages/production/OrdersPage.vue'),
        meta: { title: () => i18n.global.t('menu.orders'), permissions: ['order.manage'] },
      },
      {
        path: 'production/orders/import',
        name: 'production-orders-import',
        component: () => import('@/pages/production/OrderImportPage.vue'),
        meta: { title: () => i18n.global.t('menu.orderImport'), permissions: ['order.manage'] },
      },
      {
        path: 'production/work-orders',
        name: 'production-work-orders',
        component: () => import('@/pages/production/WorkOrdersPage.vue'),
        meta: { title: () => i18n.global.t('menu.workOrders'), permissions: ['work.manage'] },
      },
      {
        path: 'production/tasks',
        name: 'production-tasks',
        component: () => import('@/pages/production/TasksPage.vue'),
        meta: { title: () => i18n.global.t('menu.tasks'), permissions: ['task.manage', 'dispatch.manage'] },
      },
      {
        path: 'production/assignments',
        name: 'production-assignments',
        component: () => import('@/pages/production/AssignmentsPage.vue'),
        meta: { title: () => i18n.global.t('menu.assignments'), permissions: ['dispatch.manage'] },
      },
      {
        path: 'production/inspection-templates',
        name: 'production-inspection-templates',
        component: () => import('@/pages/production/InspectionTemplatesPage.vue'),
        meta: { title: () => i18n.global.t('menu.inspectionTemplates'), permissions: ['report.audit'] },
      },
      {
        path: 'production/defect-codes',
        name: 'production-defect-codes',
        component: () => import('@/pages/production/DefectCodesPage.vue'),
        meta: { title: () => i18n.global.t('menu.defectCodes'), permissions: ['report.audit'] },
      },
      {
        path: 'production/report-units',
        name: 'production-report-units',
        component: () => import('@/pages/production/ReportUnitsPage.vue'),
        meta: { title: () => i18n.global.t('menu.reportUnits'), permissions: ['report.audit'] },
      },
      {
        path: 'production/reports',
        name: 'production-reports',
        component: () => import('@/pages/production/ReportsPage.vue'),
        meta: { title: () => i18n.global.t('menu.reports'), permissions: ['report.audit'] },
      },
      {
        path: 'production/salary',
        name: 'production-salary',
        component: () => import('@/pages/production/SalaryPage.vue'),
        meta: { title: () => i18n.global.t('menu.salary'), permissions: ['salary.manage'] },
      },
      {
        path: 'production/salary-slips',
        name: 'production-salary-slips',
        component: () => import('@/pages/production/SalarySlipsPage.vue'),
        meta: { title: () => i18n.global.t('menu.salarySlips'), permissions: ['salary.manage'] },
      },
      {
        path: 'production/equipment',
        name: 'production-equipment',
        component: () => import('@/pages/production/EquipmentPage.vue'),
        meta: { title: () => i18n.global.t('menu.equipment'), permissions: ['equipment.manage'] },
      },
      {
        path: 'production/trace',
        name: 'production-trace',
        component: () => import('@/pages/production/TracePage.vue'),
        meta: { title: () => i18n.global.t('menu.trace'), permissions: ['trace.query'] },
      },
      {
        path: 'production/trace-tree',
        name: 'production-trace-tree',
        component: () => import('@/pages/production/TraceTreePage.vue'),
        meta: { title: () => i18n.global.t('menu.traceTree'), permissions: ['trace.query'] },
      },
      {
        path: 'production/mrp',
        name: 'production-mrp',
        component: () => import('@/pages/production/MrpPage.vue'),
        meta: { title: () => i18n.global.t('menu.mrp'), permissions: ['work.manage'] },
      },
      { path: 'plans', name: 'plans', component: () => import('@/pages/production/PlansPage.vue'), meta: { title: () => i18n.global.t('menu.plans'), permissions: ['plan.manage'] } },
      { path: 'plans/new', name: 'plans-new', component: () => import('@/pages/production/PlanFormPage.vue'), meta: { title: () => i18n.global.t('menu.planNew'), permissions: ['plan.manage'] } },
      { path: 'plans/:id/edit', name: 'plans-edit', component: () => import('@/pages/production/PlanFormPage.vue'), meta: { title: () => i18n.global.t('menu.planEdit'), permissions: ['plan.manage'] } },

      { path: 'warehouse/warehouses', name: 'warehouse-warehouses', component: () => import('@/pages/warehouse/WarehousesPage.vue'), meta: { title: () => i18n.global.t('menu.warehouses'), permissions: ['warehouse.manage'] } },
      { path: 'warehouse/stocks', name: 'warehouse-stocks', component: () => import('@/pages/warehouse/StocksPage.vue'), meta: { title: () => i18n.global.t('menu.stocks'), permissions: ['warehouse.manage'] } },
      { path: 'warehouse/material-issues', name: 'warehouse-material-issues', component: () => import('@/pages/warehouse/MaterialIssuesPage.vue'), meta: { title: () => i18n.global.t('menu.materialIssues'), permissions: ['warehouse.manage'] } },
      { path: 'warehouse/material-returns', name: 'warehouse-material-returns', component: () => import('@/pages/warehouse/MaterialReturnsPage.vue'), meta: { title: () => i18n.global.t('menu.materialReturns'), permissions: ['warehouse.manage'] } },
      { path: 'warehouse/entries', name: 'warehouse-entries', component: () => import('@/pages/warehouse/WarehouseEntriesPage.vue'), meta: { title: () => i18n.global.t('menu.warehouseEntries'), permissions: ['warehouse.manage'] } },
      { path: 'warehouse/shipments', name: 'warehouse-shipments', component: () => import('@/pages/warehouse/ShipmentsPage.vue'), meta: { title: () => i18n.global.t('menu.shipments'), permissions: ['order.manage'] } },

      { path: 'purchase/orders', name: 'purchase-orders', component: () => import('@/pages/purchase/PurchaseOrdersPage.vue'), meta: { title: () => i18n.global.t('menu.purchaseOrders'), permissions: ['purchase.manage'] } },
      { path: 'purchase/orders/:id', name: 'purchase-order-detail', component: () => import('@/pages/purchase/PurchaseOrderDetailPage.vue'), meta: { title: () => i18n.global.t('menu.purchaseOrderDetail'), permissions: ['purchase.manage'] } },
      { path: 'purchase/subcontract', name: 'purchase-subcontract', component: () => import('@/pages/purchase/SubcontractOrdersPage.vue'), meta: { title: () => i18n.global.t('menu.subcontractOrders'), permissions: ['purchase.manage'] } },

      { path: 'finance/supplier-statements', name: 'finance-supplier-statements', component: () => import('@/pages/finance/SupplierStatementsPage.vue'), meta: { title: () => i18n.global.t('menu.supplierStatements'), permissions: ['finance.manage'] } },
      { path: 'finance/supplier-statements/:id', name: 'finance-supplier-statement-detail', component: () => import('@/pages/finance/SupplierStatementDetailPage.vue'), meta: { title: () => i18n.global.t('menu.supplierStatementDetail'), permissions: ['finance.manage'] } },
      { path: 'finance/payables', name: 'finance-payables', component: () => import('@/pages/finance/PayablesPage.vue'), meta: { title: () => i18n.global.t('menu.payables'), permissions: ['finance.manage'] } },
      { path: 'finance/statements', name: 'finance-statements', component: () => import('@/pages/finance/CustomerStatementsPage.vue'), meta: { title: () => i18n.global.t('menu.financeStatements'), permissions: ['finance.manage'] } },
      { path: 'finance/statements/:id', name: 'finance-statement-detail', component: () => import('@/pages/finance/CustomerStatementDetailPage.vue'), meta: { title: () => i18n.global.t('menu.financeStatementDetail'), permissions: ['finance.manage'] } },
      { path: 'finance/ledgers', name: 'finance-ledgers', component: () => import('@/pages/finance/LedgersPage.vue'), meta: { title: () => i18n.global.t('menu.financeLedgers'), permissions: ['finance.manage'] } },
      { path: 'finance/profit', name: 'finance-profit', component: () => import('@/pages/finance/ProfitPage.vue'), meta: { title: () => i18n.global.t('menu.financeProfit'), permissions: ['finance.manage'] } },

      { path: ':pathMatch(.*)*', name: 'adminNotFound', redirect: '/home' },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'notFound',
    redirect: '/home',
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true

  if (!auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!auth.me) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  const need = to.meta.permissions as string[] | undefined
  const optional = new Set(['dashboard.view'])
  const required = need?.filter((x) => !optional.has(x))
  if (required && required.length > 0 && !auth.hasAnyPermission(required)) {
    ElMessage.error('无权限访问')
    return '/home'
  }
  return true
})

router.onError((error) => {
  tryRecoverStaleChunk(error)
})

export default router
