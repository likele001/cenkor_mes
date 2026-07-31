import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

/** 与 frontend-admin-pro/src/layouts/AppMenu.vue 对齐，path 为小程序分包路径 */
export type AdminMenuItem = {
  title: string
  path: string
  icon: string
  tone?: 'blue' | 'green' | 'orange' | 'violet' | 'rose' | 'slate'
  permissions?: string[]
}

export type AdminMenuGroup = {
  key: string
  title: string
  items: AdminMenuItem[]
}

export const ADMIN_MENU_GROUPS: AdminMenuGroup[] = [
  {
    key: 'dashboard',
    title: '数据大屏',
    items: [
      { title: '进度看板', path: '/pages-admin/dashboard/kanban/index', icon: '📊', tone: 'blue', permissions: ['dashboard.view'] },
      { title: '老板看板', path: '/pages-admin/dashboard/exec/index', icon: '👔', tone: 'rose', permissions: ['exec_dashboard.view'] },
      { title: '车间大屏', path: '/pages-admin/dashboard/screen/index', icon: '🖥', tone: 'violet', permissions: ['dashboard.view'] },
    ],
  },
  {
    key: 'data',
    title: '数据中心',
    items: [
      { title: '综合报表', path: '/pages-admin/reports/charts/index', icon: '📈', tone: 'blue', permissions: ['report.view'] },
      { title: '采购统计', path: '/pages-admin/reports/purchase/index', icon: '📉', tone: 'green', permissions: ['report.view'] },
    ],
  },
  {
    key: 'master',
    title: '主数据',
    items: [
      { title: '产品', path: '/pages-admin/master/products/index', icon: '📦', tone: 'blue', permissions: ['product.manage'] },
      { title: '型号', path: '/pages-admin/master/skus/index', icon: '🏷', tone: 'blue', permissions: ['sku.manage'] },
      { title: '批量型号工价', path: '/pages-admin/master/skus/batch', icon: '📋', tone: 'green', permissions: ['sku.manage', 'price.manage'] },
      { title: '供应商', path: '/pages-admin/master/suppliers/index', icon: '🚚', tone: 'slate', permissions: ['supplier.manage'] },
      { title: '物料', path: '/pages-admin/master/materials/index', icon: '🧱', tone: 'slate', permissions: ['material.manage'] },
      { title: 'BOM', path: '/pages-admin/master/boms/index', icon: '🔗', tone: 'violet', permissions: ['bom.manage'] },
      { title: '工序', path: '/pages-admin/master/processes/index', icon: '⚙', tone: 'orange', permissions: ['process.manage'] },
      { title: '工艺路线', path: '/pages-admin/master/process-routes/index', icon: '🔀', tone: 'orange', permissions: ['product.manage'] },
      { title: '工价', path: '/pages-admin/master/process-prices/index', icon: '💰', tone: 'green', permissions: ['price.manage'] },
    ],
  },
  {
    key: 'production',
    title: '生产管理',
    items: [
      { title: '客户', path: '/pages-admin/production/customers/index', icon: '👥', tone: 'blue', permissions: ['customer.manage', 'crm.sales'] },
      { title: 'CRM公海', path: '/pages-admin/crm/pool/index', icon: '🌊', tone: 'blue', permissions: ['customer.manage', 'crm.sales'] },
      { title: '机会统计', path: '/pages-admin/crm/opportunity-stats/index', icon: '🎯', tone: 'violet', permissions: ['customer.manage', 'crm.sales'] },
      { title: '客户标签', path: '/pages-admin/crm/tags/index', icon: '🏷', tone: 'slate', permissions: ['customer.manage'] },
      { title: '订单', path: '/pages-admin/production/orders/index', icon: '📋', tone: 'blue', permissions: ['order.manage'] },
      { title: '工单', path: '/pages-admin/production/work-orders/index', icon: '📝', tone: 'blue', permissions: ['work.manage'] },
      { title: '生产计划', path: '/pages-admin/plans/list/index', icon: '📅', tone: 'orange', permissions: ['plan.manage'] },
      { title: '产能设置', path: '/pages-admin/plans/capacity/index', icon: '📊', tone: 'orange', permissions: ['plan.manage'] },
      { title: '任务列表', path: '/pages-admin/production/tasks/index', icon: '☰', tone: 'orange', permissions: ['task.manage', 'dispatch.manage'] },
      { title: '分工派工', path: '/pages-admin/production/task-assign/index', icon: '👷', tone: 'orange', permissions: ['dispatch.manage'] },
      { title: '任务二维码', path: '/pages-admin/production/task-qrcode/index', icon: '▣', tone: 'slate', permissions: ['dispatch.manage'] },
      { title: '件次审核', path: '/pages-admin/audit/unit-list/index', icon: '✓', tone: 'rose', permissions: ['report.audit'] },
      { title: '批量审核', path: '/pages-admin/audit/batch-list/index', icon: '✔', tone: 'rose', permissions: ['report.audit'] },
      { title: '工资管理', path: '/pages-admin/production/salary/index', icon: '💵', tone: 'green', permissions: ['salary.manage'] },
      { title: '工资条', path: '/pages-admin/production/salary-slips/index', icon: '🧾', tone: 'green', permissions: ['salary.manage'] },
      { title: '库存', path: '/pages-admin/warehouse/stocks/index', icon: '📦', tone: 'slate', permissions: ['warehouse.manage'] },
      { title: '仓库', path: '/pages-admin/warehouse/warehouses/index', icon: '🏭', tone: 'slate', permissions: ['warehouse.manage'] },
      { title: '设备', path: '/pages-admin/equipment/list/index', icon: '🔧', tone: 'violet', permissions: ['equipment.manage'] },
      { title: '模具管理', path: '/pages-admin/equipment/molds/index', icon: '🔩', tone: 'violet', permissions: ['equipment.manage'] },
      { title: '质检模板', path: '/pages-admin/quality/templates/index', icon: '📋', tone: 'rose', permissions: ['report.audit'] },
      { title: '缺陷代码', path: '/pages-admin/quality/defect-codes/index', icon: '⚠', tone: 'rose', permissions: ['report.audit'] },
      { title: '溯源', path: '/pages-admin/production/trace/index', icon: '🔍', tone: 'blue', permissions: ['trace.query'] },
    ],
  },
  {
    key: 'purchase',
    title: '采购管理',
    items: [
      { title: '采购单', path: '/pages-admin/purchase/orders/index', icon: '🛒', tone: 'orange', permissions: ['purchase.manage'] },
      { title: '采购对账', path: '/pages-admin/purchase/statements/index', icon: '📄', tone: 'slate', permissions: ['purchase.manage'] },
    ],
  },
  {
    key: 'finance',
    title: '财务管理',
    items: [
      { title: '客户对账', path: '/pages-admin/finance/statements/index', icon: '📑', tone: 'green', permissions: ['finance.manage'] },
      { title: '收支流水', path: '/pages-admin/finance/ledgers/index', icon: '💳', tone: 'blue', permissions: ['finance.manage'] },
      { title: '成本毛利', path: '/pages-admin/finance/profit/index', icon: '📊', tone: 'violet', permissions: ['finance.manage'] },
    ],
  },
  {
    key: 'ai',
    title: '智能中心',
    items: [
      { title: '工厂助手', path: '/pages-admin/ai/assistant/index', icon: '🤖', tone: 'violet', permissions: ['ai.use'] },
      { title: '智能帮助', path: '/pages/shared/help/index', icon: '💡', tone: 'blue' },
      { title: 'AI 深度分析', path: '/pages-admin/ai/deep/index', icon: '📊', tone: 'violet', permissions: ['ai.use'] },
      { title: 'AI 调用统计', path: '/pages-admin/ai/stats/index', icon: '📈', tone: 'green', permissions: ['ai.use'] },
      { title: '生产自动化', path: '/pages-admin/system/automation/index', icon: '⚙', tone: 'orange', permissions: ['setting.manage'] },
    ],
  },
  {
    key: 'system',
    title: '系统管理',
    items: [
      { title: '用户管理', path: '/pages-admin/system/users/index', icon: '👤', tone: 'blue', permissions: ['user.manage'] },
      { title: '角色管理', path: '/pages-admin/system/roles/index', icon: '🔑', tone: 'violet', permissions: ['role.manage'] },
      { title: '权限点', path: '/pages-admin/system/permissions/index', icon: '🔒', tone: 'slate', permissions: ['permission.manage'] },
      { title: '部门', path: '/pages-admin/system/departments/index', icon: '🏢', tone: 'slate', permissions: ['department.manage'] },
      { title: '系统设置', path: '/pages-admin/system/settings/index', icon: '⚙', tone: 'orange', permissions: ['setting.manage'] },
      { title: '打印模板', path: '/pages-admin/system/print-templates/index', icon: '🖨', tone: 'slate', permissions: ['print_template.manage'] },
      { title: '消息通知', path: '/pages-admin/notification/list/index', icon: '🔔', tone: 'blue', permissions: ['notification.view'] },
      { title: '考勤记录', path: '/pages-admin/system/attendance/index', icon: '🕐', tone: 'green', permissions: ['attendance.manage'] },
      { title: '技能标签', path: '/pages-admin/system/skills/index', icon: '⭐', tone: 'orange', permissions: ['skill.manage'] },
      { title: '字典', path: '/pages-admin/system/dictionary/index', icon: '📚', tone: 'slate', permissions: ['dict.manage'] },
      { title: '操作日志', path: '/pages-admin/system/operation-logs/index', icon: '📜', tone: 'slate', permissions: ['operation_log.view'] },
    ],
  },
]

/** PC 首页快捷入口（与 HomePage.vue 一致） */
export const ADMIN_SHORTCUTS: AdminMenuItem[] = [
  { title: '工厂助手', path: '/pages-admin/ai/assistant/index', icon: '🤖', tone: 'violet', permissions: ['ai.use'] },
  { title: '智能帮助', path: '/pages/shared/help/index', icon: '💡', tone: 'blue' },
  { title: '产能设置', path: '/pages-admin/plans/capacity/index', icon: '📊', tone: 'orange', permissions: ['plan.manage'] },
  { title: '用户管理', path: '/pages-admin/system/users/index', icon: '👤', tone: 'blue', permissions: ['user.manage'] },
  { title: '角色管理', path: '/pages-admin/system/roles/index', icon: '🔑', tone: 'violet', permissions: ['role.manage'] },
  { title: '产品', path: '/pages-admin/master/products/index', icon: '📦', tone: 'blue', permissions: ['product.manage'] },
  { title: '型号', path: '/pages-admin/master/skus/index', icon: '🏷', tone: 'blue', permissions: ['sku.manage'] },
  { title: '工序', path: '/pages-admin/master/processes/index', icon: '⚙', tone: 'orange', permissions: ['process.manage'] },
  { title: '工价', path: '/pages-admin/master/process-prices/index', icon: '💰', tone: 'green', permissions: ['price.manage'] },
  { title: '订单', path: '/pages-admin/production/orders/index', icon: '📋', tone: 'blue', permissions: ['order.manage'] },
  { title: '报工审核', path: '/pages-admin/audit/batch-list/index', icon: '✔', tone: 'rose', permissions: ['report.audit'] },
  { title: '工资', path: '/pages-admin/production/salary/index', icon: '💵', tone: 'green', permissions: ['salary.manage'] },
]

export const ADMIN_AUDIT_ITEMS: AdminMenuItem[] = [
  { title: '批量报工审核', path: '/pages-admin/audit/batch-list/index', icon: '✔', tone: 'rose', permissions: ['report.audit'] },
  { title: '件次报工审核', path: '/pages-admin/audit/unit-list/index', icon: '✓', tone: 'violet', permissions: ['report.audit'] },
]

function filterItems(items: AdminMenuItem[], hasAny: (codes?: string[]) => boolean): AdminMenuItem[] {
  return items.filter((it) => hasAny(it.permissions))
}

/** 管理端菜单权限过滤与导航（合并到 constants，避免小程序 tab 组件加载 composables 失败） */
export function useAdminMenu() {
  const auth = useAuthStore()

  function hasAnyPermission(codes?: string[]): boolean {
    if (!codes?.length) return true
    if (auth.userInfo?.is_superuser) return true
    return codes.some((c) => auth.permissions.includes(c))
  }

  const menuGroups = computed<AdminMenuGroup[]>(() =>
    ADMIN_MENU_GROUPS.map((g) => ({
      ...g,
      items: filterItems(g.items, hasAnyPermission),
    })).filter((g) => g.items.length > 0),
  )

  const shortcuts = computed(() => filterItems(ADMIN_SHORTCUTS, hasAnyPermission))
  const auditItems = computed(() => filterItems(ADMIN_AUDIT_ITEMS, hasAnyPermission))
  const productionGroup = computed(() => menuGroups.value.find((g) => g.key === 'production'))
  const canDashboard = computed(() => hasAnyPermission(['dashboard.view']))

  function navigate(path: string) {
    uni.navigateTo({ url: path })
  }

  return {
    menuGroups,
    shortcuts,
    auditItems,
    productionGroup,
    canDashboard,
    hasAnyPermission,
    navigate,
  }
}
