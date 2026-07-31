<template>
  <div v-loading="loading">
    <el-table class="hidden lg:block w-full" :data="items" border>
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="code" label="计划编号" width="180" />
      <el-table-column prop="order_code" label="订单号" width="220" />
      <el-table-column prop="customer_name" label="客户" width="180" />
      <el-table-column prop="qty" label="数量" width="110" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="start_date" label="开始" width="120" />
      <el-table-column prop="end_date" label="结束" width="120" />
      <el-table-column prop="work_days" label="工期(天)" width="110" />
      <el-table-column prop="remark" label="备注" min-width="220" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="400" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
          <el-button v-if="canAi" size="small" type="warning" plain :loading="aiPlanId === row.id && aiLoading" @click="emit('aiSchedule', row.id)">{{ t('production.plans.aiSchedule') }}</el-button>
          <el-button size="small" @click="emit('checkKit', row.id)">{{ t('production.plans.kitCheck') }}</el-button>
          <el-button
            v-if="row.can_release"
            size="small"
            type="primary"
            :loading="releasingId === row.id"
            @click="emit('releasePlan', row)"
          >
            确认下发
          </el-button>
          <el-tag v-else-if="row.status === 'in_progress'" type="success" size="small">{{ t('production.plans.released') }}</el-tag>
          <el-tag v-else-if="row.has_work_orders" type="warning" size="small">{{ t('production.plans.hasWorkOrders') }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <div class="lg:hidden space-y-3">
      <div v-for="row in items" :key="row.id" class="admin-mobile-row">
        <div class="admin-mobile-row__head">
          <div class="min-w-0">
            <div class="font-semibold text-el-primary truncate">{{ row.code }}</div>
            <div class="text-xs text-el-placeholder">#{{ row.id }} · {{ row.order_code }}</div>
          </div>
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </div>
        <dl class="admin-mobile-kv">
          <dt>客户</dt>
          <dd>{{ row.customer_name || '—' }}</dd>
          <dt>数量</dt>
          <dd>{{ row.qty }}</dd>
          <dt>工期</dt>
          <dd>{{ row.start_date }} ~ {{ row.end_date }}（{{ row.work_days }} 天）</dd>
          <dt>备注</dt>
          <dd>{{ row.remark || '—' }}</dd>
          <dt>创建</dt>
          <dd>{{ row.created_at }}</dd>
        </dl>
        <div class="admin-mobile-actions">
          <el-button size="small" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
          <el-button v-if="canAi" size="small" type="warning" plain @click="emit('aiSchedule', row.id)">{{ t('production.plans.aiSchedule') }}</el-button>
          <el-button size="small" @click="emit('checkKit', row.id)">{{ t('production.plans.kitCheck') }}</el-button>
          <el-button
            v-if="row.can_release"
            size="small"
            type="primary"
            :loading="releasingId === row.id"
            @click="emit('releasePlan', row)"
          >
            确认下发
          </el-button>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无数据" />
    </div>
  </div>

  <div class="mt-4 flex justify-end">
    <el-pagination
      background
      layout="prev, pager, next"
      :page-size="pageSize"
      :total="fakeTotal"
      :current-page="currentPage"
      @current-change="emit('pageChange', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import type { PlanOut } from '@/api/plans'

const { t } = useI18n()
const { label: statusLabel, type: statusTagType } = useStatus('plan')
const router = useRouter()

defineProps<{
  items: PlanOut[]
  loading: boolean
  canAi: boolean
  aiPlanId: number | null
  aiLoading: boolean
  releasingId: number | null
  pageSize: number
  fakeTotal: number
  currentPage: number
}>()

const emit = defineEmits<{
  (e: 'aiSchedule', planId: number): void
  (e: 'checkKit', planId: number): void
  (e: 'releasePlan', row: PlanOut): void
  (e: 'pageChange', page: number): void
}>()


</script>
