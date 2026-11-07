<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { basicsApi } from '@/api/basics'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const canManage = computed(() => auth.hasAnyPermission(['rework.manage']))

const loading = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const stats = ref<any>(null)

const query = reactive({
  status: '',
  keyword: '',
  offset: 0,
  limit: 20,
})

const STATUS_LABEL: Record<string, string> = {
  pending: '待派工', in_progress: '返工中', done: '已完成', cancelled: '已作废',
}
const STATUS_TAG: Record<string, string> = {
  pending: 'info', in_progress: 'warning', done: 'success', cancelled: 'danger',
}

async function load() {
  loading.value = true
  try {
    const [list, st] = await Promise.all([
      basicsApi.listReworks({
        status: query.status || undefined,
        keyword: query.keyword || undefined,
        offset: query.offset,
        limit: query.limit,
      }),
      basicsApi.reworkStats(),
    ])
    rows.value = list?.items || []
    total.value = list?.total ?? rows.value.length
    stats.value = st
  } finally {
    loading.value = false
  }
}

async function doAction(fn: () => Promise<unknown>, okMsg: string) {
  try {
    await fn()
    ElMessage.success(okMsg)
    await load()
  } catch {
    // 拦截器已提示
  }
}

async function complete(row: any) {
  try {
    const { value } = await ElMessageBox.prompt(
      `该返工单计划 ${row.qty} 件，实际完成多少件？`, '完成返工',
      { inputValue: String(row.qty), inputPattern: /^\d+$/, inputErrorMessage: '请输入整数' },
    )
    await doAction(() => basicsApi.completeRework(row.id, { done_qty: Number(value) }), '返工已登记完成')
  } catch {
    // 取消
  }
}

async function cancel(row: any) {
  try {
    const { value } = await ElMessageBox.prompt('作废原因（可留空）', '作废返工单', { inputValue: '' })
    await doAction(() => basicsApi.cancelRework(row.id, { reason: value }), '返工单已作废')
  } catch {
    // 取消
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  load()
}

onMounted(load)
</script>

<template>
  <AdminPage :title="t('menu.reworks')">
    <template #actions>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-row :gutter="12" class="mb-4">
      <el-col :span="6"><el-card shadow="never"><div class="text-xs text-el-placeholder">返工单总数</div><div class="text-2xl font-semibold">{{ stats?.total ?? '-' }}</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="text-xs text-el-placeholder">待派工</div><div class="text-2xl font-semibold">{{ stats?.pending ?? '-' }}</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="text-xs text-el-placeholder">返工中</div><div class="text-2xl font-semibold">{{ stats?.in_progress ?? '-' }}</div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="text-xs text-el-placeholder">完成率 / 返工良品</div><div class="text-2xl font-semibold">{{ stats?.completion_rate ?? '-' }}% / {{ stats?.done_qty ?? '-' }}</div></el-card></el-col>
    </el-row>

    <el-form :inline="true" class="mb-3" @submit.prevent="load">
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="(label, key) in STATUS_LABEL" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="单号 / 处置单">
        <el-input v-model="query.keyword" clearable placeholder="关键字" style="width: 200px" @keyup.enter="load" />
      </el-form-item>
      <el-form-item><el-button type="primary" @click="load">查询</el-button></el-form-item>
    </el-form>

    <el-alert type="info" :closable="false" class="mb-3" show-icon
      title="返工单由不良品处置单批准时自动生成（同一行只生成一次）。完成数会回流到处置明细，闭环时不会被按全量执行抹掉。" />

    <el-table :data="rows" v-loading="loading" border stripe size="small">
      <el-table-column prop="code" label="返工单号" width="180" />
      <el-table-column prop="disposition_code" label="处置单" width="170" />
      <el-table-column prop="process_name" label="返工工序" min-width="120" />
      <el-table-column prop="sku_name" label="产品" min-width="120" />
      <el-table-column prop="qty" label="计划数" width="90" />
      <el-table-column prop="done_qty" label="完成数" width="90" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="(STATUS_TAG[row.status] as any) || 'info'">{{ STATUS_LABEL[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canManage && row.status === 'pending'" size="small" type="primary"
            @click="doAction(() => basicsApi.startRework(row.id, {}), '已开工')">开工</el-button>
          <el-button v-if="canManage && ['pending', 'in_progress'].includes(row.status)" size="small" type="success"
            @click="complete(row)">完成</el-button>
          <el-button v-if="canManage && row.status !== 'done' && row.status !== 'cancelled'" size="small"
            @click="cancel(row)">作废</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-3 flex justify-end">
      <el-pagination background layout="total, prev, pager, next" :total="total"
        :page-size="query.limit" :current-page="Math.floor(query.offset / query.limit) + 1"
        @current-change="onPageChange" />
    </div>
  </AdminPage>
</template>
