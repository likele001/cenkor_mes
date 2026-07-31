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

    <el-sub-menu index="dashboard" v-if="auth.hasAnyPermission(['dashboard.view'])">
      <template #title>
        <el-icon><DataBoard /></el-icon>
        <span>{{ t('menu.dashboard') }}</span>
      </template>
      <el-menu-item index="/dashboard/kanban">
        <el-icon><Histogram /></el-icon>
        <span>{{ t('menu.kanban') }}</span>
      </el-menu-item>
      <el-menu-item index="/dashboard/screen">
        <el-icon><Monitor /></el-icon>
        <span>{{ t('menu.screen') }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="system" v-if="systemItems.length">
      <template #title>
        <el-icon><Setting /></el-icon>
        <span>{{ t('menu.system') }}</span>
      </template>
      <el-menu-item v-for="it in systemItems" :key="it.path" :index="it.path">
        <el-icon><component :is="it.icon" /></el-icon>
        <span>{{ t(it.i18nKey) }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="master" v-if="masterItems.length">
      <template #title>
        <el-icon><Box /></el-icon>
        <span>{{ t('menu.master') }}</span>
      </template>
      <el-menu-item v-for="it in masterItems" :key="it.path" :index="it.path">
        <el-icon><component :is="it.icon" /></el-icon>
        <span>{{ t(it.i18nKey) }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-sub-menu index="production" v-if="productionItems.length">
      <template #title>
        <el-icon><Operation /></el-icon>
        <span>{{ t('menu.production') }}</span>
      </template>
      <el-menu-item v-for="it in productionItems" :key="it.path" :index="it.path">
        <el-icon><component :is="it.icon" /></el-icon>
        <span>{{ t(it.i18nKey) }}</span>
      </el-menu-item>
    </el-sub-menu>

    <el-menu-item v-if="auth.hasAnyPermission(['report.view'])" index="/reports">
      <el-icon><DataAnalysis /></el-icon>
      <span>{{ t('menu.reportsOverview') }}</span>
    </el-menu-item>

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
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

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

type MenuItem = { path: string; i18nKey: string; permissions?: string[]; icon: Component }

const route = useRoute()
const auth = useAuthStore()

const active = computed(() => route.path)

const systemAll: MenuItem[] = [
  { path: '/system/users', i18nKey: 'menu.users', permissions: ['user.manage'], icon: User },
  { path: '/system/roles', i18nKey: 'menu.roles', permissions: ['role.manage'], icon: Key },
  { path: '/system/permissions', i18nKey: 'menu.permissions', permissions: ['permission.manage'], icon: Lock },
  { path: '/system/departments', i18nKey: 'menu.departments', permissions: ['department.manage'], icon: OfficeBuilding },
  { path: '/system/settings', i18nKey: 'menu.settings', permissions: ['setting.manage'], icon: Tools },
  { path: '/system/cron-jobs', i18nKey: 'menu.cronJobs', permissions: ['setting.manage'], icon: Clock },
  { path: '/system/print-templates', i18nKey: 'menu.printTemplates', permissions: ['print_template.manage'], icon: Document },
  { path: '/system/notifications', i18nKey: 'menu.notifications', permissions: ['notification.view'], icon: Bell },
  { path: '/system/attendance-records', i18nKey: 'menu.attendanceRecords', permissions: ['attendance.manage'], icon: Calendar },
  { path: '/system/skills', i18nKey: 'menu.skills', permissions: ['skill.manage'], icon: Star },
  { path: '/system/dictionary', i18nKey: 'menu.dictionary', permissions: ['dict.manage'], icon: CollectionTag },
  { path: '/system/attachments', i18nKey: 'menu.attachments', permissions: ['attachment.view'], icon: FolderOpened },
  { path: '/system/operation-logs', i18nKey: 'menu.operationLogs', permissions: ['operation_log.view'], icon: Notebook },
]

const masterAll: MenuItem[] = [
  { path: '/master/products', i18nKey: 'menu.products', permissions: ['product.manage'], icon: Goods },
  { path: '/master/skus', i18nKey: 'menu.skus', permissions: ['sku.manage'], icon: Grid },
  { path: '/master/skus/batch', i18nKey: 'menu.skusBatch', permissions: ['sku.manage', 'price.manage'], icon: Grid },
  { path: '/master/suppliers', i18nKey: 'menu.suppliers', permissions: ['supplier.manage'], icon: Van },
  { path: '/master/materials', i18nKey: 'menu.materials', permissions: ['material.manage'], icon: Box },
  { path: '/master/boms', i18nKey: 'menu.boms', permissions: ['bom.manage'], icon: Connection },
  { path: '/master/processes', i18nKey: 'menu.processes', permissions: ['process.manage'], icon: Operation },
  { path: '/master/process-routes', i18nKey: 'menu.processRoutes', permissions: ['product.manage'], icon: Share },
  { path: '/master/process-prices', i18nKey: 'menu.processPrices', permissions: ['price.manage'], icon: Money },
]

const productionAll: MenuItem[] = [
  { path: '/production/shifts', i18nKey: 'menu.shifts', permissions: ['attendance.manage'], icon: Calendar },
  { path: '/production/customers', i18nKey: 'menu.customers', permissions: ['customer.manage', 'crm.sales'], icon: UserFilled },
  { path: '/production/orders', i18nKey: 'menu.orders', permissions: ['order.manage'], icon: DocumentCopy },
  { path: '/production/work-orders', i18nKey: 'menu.workOrders', permissions: ['work.manage'], icon: List },
  { path: '/plans', i18nKey: 'menu.plans', permissions: ['plan.manage'], icon: Calendar },
  { path: '/production/tasks', i18nKey: 'menu.tasks', permissions: ['task.manage', 'dispatch.manage'], icon: List },
  { path: '/production/assignments', i18nKey: 'menu.assignments', permissions: ['dispatch.manage'], icon: User },
  { path: '/production/inspection-templates', i18nKey: 'menu.inspectionTemplates', permissions: ['report.audit'], icon: DocumentChecked },
  { path: '/production/defect-codes', i18nKey: 'menu.defectCodes', permissions: ['report.audit'], icon: EditPen },
  { path: '/production/report-units', i18nKey: 'menu.reportUnits', permissions: ['report.audit'], icon: DocumentChecked },
  { path: '/production/reports', i18nKey: 'menu.reports', permissions: ['report.audit'], icon: EditPen },
  { path: '/production/salary', i18nKey: 'menu.salary', permissions: ['salary.manage'], icon: Wallet },
  { path: '/production/salary-slips', i18nKey: 'menu.salarySlips', permissions: ['salary.manage'], icon: EditPen },
  { path: '/production/equipment', i18nKey: 'menu.equipment', permissions: ['equipment.manage'], icon: Monitor },
  { path: '/production/trace', i18nKey: 'menu.trace', permissions: ['trace.query'], icon: Search },
]

const systemItems = computed(() => systemAll.filter((x) => auth.hasAnyPermission(x.permissions)))
const masterItems = computed(() => masterAll.filter((x) => auth.hasAnyPermission(x.permissions)))
const productionItems = computed(() => productionAll.filter((x) => auth.hasAnyPermission(x.permissions)))
</script>
