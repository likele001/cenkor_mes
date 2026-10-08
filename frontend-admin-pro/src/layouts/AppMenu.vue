<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <el-menu
    class="admin-sider-menu border-0"
    :class="menuRootClass"
    :default-active="active"
    :collapse="layout === 'sider' && collapse"
    router
  >
    <el-menu-item index="/home">
      <el-icon><House /></el-icon>
      <span>{{ t('menu.home') }}</span>
    </el-menu-item>

    <el-menu-item v-if="hasMarketPermission" index="/market">
      <el-icon><Shop /></el-icon>
      <span>{{ t('menu.market') }}</span>
    </el-menu-item>

    <el-sub-menu v-for="g in visibleGroups" :key="g.key" :index="g.key">
      <template #title>
        <el-icon><component :is="g.icon" /></el-icon>
        <span>{{ t(g.i18nKey) }}</span>
      </template>

      <!-- 单项分组直接平铺，只有系统管理需要二级目录 -->
      <template v-if="g.sections.length === 1">
        <el-menu-item v-for="it in g.sections[0].items" :key="it.path" :index="it.path">
          <el-icon><component :is="it.icon" /></el-icon>
          <span>{{ t(it.i18nKey) }}</span>
        </el-menu-item>
      </template>
      <template v-else>
        <el-sub-menu v-for="sec in g.sections" :key="sec.key" :index="sec.key">
          <template #title>
            <el-icon><component :is="sec.icon" /></el-icon>
            <span>{{ t(sec.i18nKey) }}</span>
          </template>
          <el-menu-item v-for="it in sec.items" :key="it.path" :index="it.path">
            <el-icon><component :is="it.icon" /></el-icon>
            <span>{{ t(it.i18nKey) }}</span>
          </el-menu-item>
        </el-sub-menu>
      </template>
    </el-sub-menu>

    <el-sub-menu v-if="extMenuItems.length" index="ext-apps">
      <template #title>
        <el-icon><Grid /></el-icon>
        <span>{{ t('menu.extensions') }}</span>
      </template>
      <el-menu-item v-for="it in extMenuItems" :key="it.path" :index="it.path">
        <el-icon><component :is="iconOf(it.icon)" /></el-icon>
        <span>{{ extMenuLabel(it) }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-menu-item index="/account/profile">
      <el-icon><User /></el-icon>
      <span>{{ t('menu.profile') }}</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  House,
  DataBoard,
  DataLine,
  Setting,
  Box,
  Operation,
  Histogram,
  Monitor,
  User,
  Key,
  Lock,
  OfficeBuilding,
  Tools,
  Document,
  Bell,
  Calendar,
  Star,
  CollectionTag,
  FolderOpened,
  Notebook,
  InfoFilled,
  Goods,
  Grid,
  Van,
  Connection,
  Share,
  Money,
  UserFilled,
  DocumentCopy,
  List,
  DocumentChecked,
  EditPen,
  Search,
  DataAnalysis,
  Clock,
  Wallet,
  Sell,
  ShoppingCart,
  Aim,
  Files,
  SetUp,
  Tickets,
  Cloudy,
  Stamp,
  Promotion,
  ChatDotRound,
  Shop,
  MagicStick,
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { extensionMenus, type ExtensionMenu } from '@/utils/extensionLoader'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    layout?: 'sider' | 'drawer'
    collapse?: boolean
  }>(),
  { layout: 'sider', collapse: false }
)

const menuRootClass = computed(() =>
  props.layout === 'sider' ? 'h-full min-h-0 overflow-y-auto' : 'pb-2'
)

type Leaf = { path: string; i18nKey: string; permissions?: string[]; icon: Component }
type Section = { key: string; i18nKey: string; icon: Component; items: Leaf[] }
type Group = { key: string; i18nKey: string; icon: Component; sections: Section[] }

const route = useRoute()
const auth = useAuthStore()

const active = computed(() => route.path)

const hasMarketPermission = computed(() => auth.hasAnyPermission(['setting.manage']))

const groups: Group[] = [
  {
    key: 'board',
    i18nKey: 'menu.boardAndReports',
    icon: DataBoard,
    sections: [
      {
        key: 'board-all',
        i18nKey: 'menu.boardAndReports',
        icon: DataBoard,
        items: [
          { path: '/dashboard/kanban', i18nKey: 'menu.kanban', permissions: ['dashboard.view'], icon: Histogram },
          { path: '/dashboard/screen', i18nKey: 'menu.screen', permissions: ['dashboard.view'], icon: Monitor },
          { path: '/dashboard/exec', i18nKey: 'menu.execDashboard', permissions: ['exec_dashboard.view'], icon: Money },
          { path: '/reports', i18nKey: 'menu.reportsOverview', permissions: ['report.view'], icon: DataAnalysis },
        ],
      },
    ],
  },
  {
    key: 'sales',
    i18nKey: 'menu.salesAndPlans',
    icon: Sell,
    sections: [
      {
        key: 'sales-all',
        i18nKey: 'menu.salesAndPlans',
        icon: Sell,
        items: [
          { path: '/production/customers', i18nKey: 'menu.customers', permissions: ['customer.manage', 'crm.sales', 'customer.view'], icon: UserFilled },
          { path: '/production/orders', i18nKey: 'menu.orders', permissions: ['order.manage', 'order.view'], icon: DocumentCopy },
          { path: '/plans', i18nKey: 'menu.plans', permissions: ['plan.manage', 'production.plan'], icon: Calendar },
          { path: '/system/automation-settings', i18nKey: 'menu.automationSettings', permissions: ['setting.manage'], icon: Operation },
          { path: '/production/mrp', i18nKey: 'menu.mrp', permissions: ['work.manage'], icon: DataLine },
        ],
      },
    ],
  },
  {
    key: 'execute',
    i18nKey: 'menu.execution',
    icon: Operation,
    sections: [
      {
        key: 'execute-all',
        i18nKey: 'menu.execution',
        icon: Operation,
        items: [
          { path: '/production/work-orders', i18nKey: 'menu.workOrders', permissions: ['work.manage', 'workorder.view', 'workorder.manage'], icon: List },
          { path: '/production/tasks', i18nKey: 'menu.tasks', permissions: ['task.manage', 'dispatch.manage', 'task.view'], icon: Tickets },
          { path: '/production/assignments', i18nKey: 'menu.assignments', permissions: ['dispatch.manage', 'task.assign'], icon: User },
          { path: '/production/reports', i18nKey: 'menu.reports', permissions: ['report.audit', 'report.approve', 'qc.approve'], icon: EditPen },
          { path: '/production/report-units', i18nKey: 'menu.reportUnits', permissions: ['report.audit', 'qc.inspect', 'qc.approve', 'report.approve'], icon: DocumentChecked },
          { path: '/production/equipment', i18nKey: 'menu.equipment', permissions: ['equipment.manage', 'equipment.view'], icon: Monitor },
        ],
      },
    ],
  },
  {
    key: 'quality',
    i18nKey: 'menu.qualityAndTrace',
    icon: Aim,
    sections: [
      {
        key: 'quality-all',
        i18nKey: 'menu.qualityAndTrace',
        icon: Aim,
        items: [
          { path: '/production/inspection-templates', i18nKey: 'menu.inspectionTemplates', permissions: ['report.audit', 'qc.inspect', 'qc.approve'], icon: DocumentChecked },
          { path: '/production/defect-codes', i18nKey: 'menu.defectCodes', permissions: ['report.audit', 'qc.inspect', 'qc.approve'], icon: EditPen },
          { path: '/production/trace', i18nKey: 'menu.trace', permissions: ['trace.query'], icon: Search },
          { path: '/production/trace-tree', i18nKey: 'menu.traceTree', permissions: ['trace.query'], icon: Share },
        ],
      },
    ],
  },
  {
    key: 'stock',
    i18nKey: 'menu.warehouseLogistics',
    icon: Box,
    sections: [
      {
        key: 'stock-all',
        i18nKey: 'menu.warehouseLogistics',
        icon: Box,
        items: [
          { path: '/warehouse/warehouses', i18nKey: 'menu.warehouses', permissions: ['warehouse.manage', 'warehouse.view'], icon: OfficeBuilding },
          { path: '/warehouse/stocks', i18nKey: 'menu.stocks', permissions: ['warehouse.manage', 'warehouse.view'], icon: Box },
          { path: '/warehouse/material-issues', i18nKey: 'menu.materialIssues', permissions: ['warehouse.manage', 'warehouse.view'], icon: Sell },
          { path: '/warehouse/material-returns', i18nKey: 'menu.materialReturns', permissions: ['warehouse.manage', 'warehouse.view'], icon: Share },
          { path: '/warehouse/entries', i18nKey: 'menu.warehouseEntries', permissions: ['warehouse.manage', 'warehouse.view'], icon: Document },
          { path: '/warehouse/shipments', i18nKey: 'menu.shipments', permissions: ['order.manage', 'order.view'], icon: Van },
        ],
      },
    ],
  },
  {
    key: 'buy',
    i18nKey: 'menu.purchaseAndSubcontract',
    icon: ShoppingCart,
    sections: [
      {
        key: 'buy-all',
        i18nKey: 'menu.purchaseAndSubcontract',
        icon: ShoppingCart,
        items: [
          { path: '/purchase/orders', i18nKey: 'menu.purchaseOrders', permissions: ['purchase.manage'], icon: DocumentCopy },
          { path: '/purchase/subcontract', i18nKey: 'menu.subcontractOrders', permissions: ['purchase.manage'], icon: Van },
          { path: '/finance/supplier-statements', i18nKey: 'menu.supplierStatements', permissions: ['finance.manage'], icon: Money },
        ],
      },
    ],
  },
  {
    key: 'people',
    i18nKey: 'menu.hrAndPayroll',
    icon: UserFilled,
    sections: [
      {
        key: 'people-all',
        i18nKey: 'menu.hrAndPayroll',
        icon: UserFilled,
        items: [
          { path: '/production/shifts', i18nKey: 'menu.shifts', permissions: ['attendance.manage'], icon: Clock },
          { path: '/system/attendance-records', i18nKey: 'menu.attendanceRecords', permissions: ['attendance.manage'], icon: Calendar },
          { path: '/system/skills', i18nKey: 'menu.skills', permissions: ['skill.manage'], icon: Star },
          { path: '/production/salary', i18nKey: 'menu.salary', permissions: ['salary.manage'], icon: Wallet },
          { path: '/production/salary-slips', i18nKey: 'menu.salarySlips', permissions: ['salary.manage'], icon: Money },
        ],
      },
    ],
  },
  {
    key: 'master',
    i18nKey: 'menu.master',
    icon: Files,
    sections: [
      {
        key: 'master-all',
        i18nKey: 'menu.master',
        icon: Files,
        items: [
          { path: '/master/products', i18nKey: 'menu.products', permissions: ['product.manage'], icon: Goods },
          { path: '/master/skus', i18nKey: 'menu.skus', permissions: ['sku.manage'], icon: Grid },
          { path: '/master/skus/batch', i18nKey: 'menu.skusBatch', permissions: ['sku.manage', 'price.manage'], icon: Grid },
          { path: '/master/suppliers', i18nKey: 'menu.suppliers', permissions: ['supplier.manage'], icon: Van },
          { path: '/master/materials', i18nKey: 'menu.materials', permissions: ['material.manage'], icon: Box },
          { path: '/master/boms', i18nKey: 'menu.boms', permissions: ['bom.manage'], icon: Connection },
          { path: '/master/processes', i18nKey: 'menu.processes', permissions: ['process.manage'], icon: Operation },
          { path: '/master/process-routes', i18nKey: 'menu.processRoutes', permissions: ['product.manage'], icon: Share },
          { path: '/master/process-prices', i18nKey: 'menu.processPrices', permissions: ['price.manage'], icon: Money },
        ],
      },
    ],
  },
  {
    key: 'finance',
    i18nKey: 'menu.finance',
    icon: Money,
    sections: [
      {
        key: 'finance-all',
        i18nKey: 'menu.finance',
        icon: Money,
        items: [
          { path: '/finance/payables', i18nKey: 'menu.payables', permissions: ['finance.manage'], icon: Wallet },
          { path: '/finance/statements', i18nKey: 'menu.financeStatements', permissions: ['finance.manage'], icon: DocumentCopy },
          { path: '/finance/ledgers', i18nKey: 'menu.financeLedgers', permissions: ['finance.manage'], icon: List },
          { path: '/finance/profit', i18nKey: 'menu.financeProfit', permissions: ['finance.manage'], icon: DataLine },
        ],
      },
    ],
  },
  {
    key: 'system',
    i18nKey: 'menu.system',
    icon: Setting,
    sections: [
      {
        key: 'system-org',
        i18nKey: 'menu.orgAndPermissions',
        icon: Key,
        items: [
          { path: '/system/users', i18nKey: 'menu.users', permissions: ['user.manage'], icon: User },
          { path: '/system/roles', i18nKey: 'menu.roles', permissions: ['role.manage'], icon: Key },
          { path: '/system/permissions', i18nKey: 'menu.permissions', permissions: ['permission.manage'], icon: Lock },
          { path: '/system/departments', i18nKey: 'menu.departments', permissions: ['department.manage'], icon: OfficeBuilding },
          { path: '/system/approval-flows', i18nKey: 'menu.approvalFlows', permissions: ['setting.manage'], icon: Stamp },
        ],
      },
      {
        key: 'system-integration',
        i18nKey: 'menu.integrationAndNotify',
        icon: Connection,
        items: [
          { path: '/system/notifications', i18nKey: 'menu.notifications', permissions: ['notification.view'], icon: Bell },
          { path: '/system/message-center', i18nKey: 'menu.messageCenter', permissions: ['setting.manage'], icon: ChatDotRound },
          { path: '/system/feishu-notify', i18nKey: 'menu.feishuNotify', permissions: ['setting.manage'], icon: Promotion },
          { path: '/system/print-templates', i18nKey: 'menu.printTemplates', permissions: ['print_template.manage'], icon: Document },
          { path: '/system/attachments', i18nKey: 'menu.attachments', permissions: ['attachment.view'], icon: FolderOpened },
          { path: '/system/cloud-storage', i18nKey: 'menu.cloudStorage', permissions: ['cloud_storage.manage'], icon: Cloudy },
          { path: '/system/crm-adapter', i18nKey: 'menu.crmAdapter', permissions: ['setting.manage', 'crm.admin'], icon: Connection },
          { path: '/system/crm-orders', i18nKey: 'menu.crmOrders', permissions: ['setting.manage', 'crm.admin'], icon: List },
        ],
      },
      {
        key: 'system-ops',
        i18nKey: 'menu.paramsAndOps',
        icon: SetUp,
        items: [
          { path: '/system/settings', i18nKey: 'menu.settings', permissions: ['setting.manage'], icon: Tools },
          { path: '/system/ai-gateway', i18nKey: 'menu.aiModels', permissions: ['setting.manage'], icon: MagicStick },
          { path: '/system/dictionary', i18nKey: 'menu.dictionary', permissions: ['dict.manage'], icon: CollectionTag },
          { path: '/system/cron-jobs', i18nKey: 'menu.cronJobs', permissions: ['setting.manage'], icon: Clock },
          { path: '/system/operation-logs', i18nKey: 'menu.operationLogs', permissions: ['operation_log.view'], icon: Notebook },
          { path: '/system/about', i18nKey: 'menu.systemAbout', permissions: ['setting.manage'], icon: InfoFilled },
        ],
      },
    ],
  },
]

const canSee = (x: Leaf) => auth.hasAnyPermission(x.permissions)

/** 扩展菜单图标（插件声明的 Element Plus 图标名 → 组件）；未知名称回退 Grid */
const EXT_ICONS: Record<string, Component> = {
  House,
  DataBoard,
  DataLine,
  Setting,
  Box,
  Operation,
  Histogram,
  Monitor,
  User,
  Key,
  Lock,
  OfficeBuilding,
  Tools,
  Document,
  Bell,
  Calendar,
  Star,
  CollectionTag,
  FolderOpened,
  Notebook,
  InfoFilled,
  Goods,
  Grid,
  Van,
  Connection,
  Share,
  Money,
  UserFilled,
  DocumentCopy,
  List,
  DocumentChecked,
  EditPen,
  Search,
  DataAnalysis,
  Clock,
  Wallet,
  Sell,
  ShoppingCart,
  Aim,
  Files,
  SetUp,
  Tickets,
  Cloudy,
  Stamp,
  Promotion,
  ChatDotRound,
}

/** 已加载扩展的菜单项（按当前用户权限过滤） */
const extMenuItems = computed(() =>
  extensionMenus.value.filter((m) => auth.hasAnyPermission(m.permission ? [m.permission] : undefined))
)

function iconOf(name?: string): Component {
  return (name && EXT_ICONS[name]) || Grid
}

function extMenuLabel(m: ExtensionMenu & { key: string }): string {
  return m.i18nKey ? t(m.i18nKey) : m.title
}

const visibleGroups = computed(() =>
  groups
    .map((g) => {
      const sections = g.sections
        .map((sec) => ({ ...sec, items: sec.items.filter(canSee) }))
        .filter((sec) => sec.items.length > 0)
      return { ...g, sections }
    })
    .filter((g) => g.sections.length > 0)
)
</script>
