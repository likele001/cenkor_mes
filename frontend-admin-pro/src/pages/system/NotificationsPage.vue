<template>
  <AdminPage :title="t('system.notifications.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-select v-model="query.unread" clearable :placeholder="t('system.notifications.statusPlaceholder')" style="width: 120px" @change="reload(true)">
            <el-option :label="t('system.notifications.all')" :value="undefined" />
            <el-option :label="t('system.notifications.unread')" :value="true" />
            <el-option :label="t('system.notifications.read')" :value="false" />
          </el-select>
          <el-select v-model="query.level" clearable :placeholder="t('system.notifications.levelPlaceholder')" style="width: 120px" @change="reload(true)">
            <el-option label="info" value="info" />
            <el-option label="warning" value="warning" />
            <el-option label="error" value="error" />
          </el-select>
          <el-button type="primary" @click="reload(true)">{{ t('system.notifications.refresh') }}</el-button>
          <el-button :disabled="!items.length" @click="markAllRead">{{ t('system.notifications.markAllRead') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border @row-click="onRowClick" style="cursor: pointer">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column :label="t('system.notifications.level')" width="110">
            <template #default="{ row }">
              <el-tag :type="levelTag(row.level)">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.notifications.type')" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.biz_type === 'report'" size="small">{{ t('system.notifications.reportType') }}</el-tag>
              <el-tag v-else-if="row.biz_type === 'salary_slip'" size="small" type="warning">{{ t('system.notifications.salarySlipType') }}</el-tag>
              <span v-else class="text-xs text-zinc-400">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" :label="t('system.notifications.titleCol')" min-width="200" />
          <el-table-column prop="content" :label="t('system.notifications.content')" min-width="320" show-overflow-tooltip />
          <el-table-column :label="t('system.notifications.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.read_at ? 'success' : 'info'">{{ row.read_at ? t('system.notifications.readStatus') : t('system.notifications.unreadStatus') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('system.notifications.time')" width="180" />
          <el-table-column :label="t('system.notifications.operation')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button v-if="!row.read_at" size="small" @click="markRead(row.id)">{{ t('system.notifications.markRead') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row cursor-pointer" @click="onRowClick(row)">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary text-sm">{{ row.title }}</div>
                <div class="text-xs text-el-placeholder mt-1">{{ row.created_at }}</div>
              </div>
              <div class="flex flex-col items-end gap-1 shrink-0">
                <el-tag :type="levelTag(row.level)" size="small">{{ row.level }}</el-tag>
                <el-tag :type="row.read_at ? 'success' : 'info'" size="small">{{ row.read_at ? t('system.notifications.readStatus') : t('system.notifications.unreadStatus') }}</el-tag>
              </div>
            </div>
            <p class="text-xs text-el-regular line-clamp-3 m-0">{{ row.content }}</p>
            <div class="mt-2 flex flex-wrap gap-2">
              <el-tag v-if="row.biz_type === 'report'" size="small">{{ t('system.notifications.reportType') }}</el-tag>
              <el-tag v-else-if="row.biz_type === 'salary_slip'" size="small" type="warning">{{ t('system.notifications.salarySlipType') }}</el-tag>
            </div>
            <div v-if="!row.read_at" class="admin-mobile-actions">
              <el-button size="small" @click.stop="markRead(row.id)">{{ t('system.notifications.markRead') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.notifications.noNotifications')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="pager.total"
          :page-size="query.limit"
          :current-page="pager.page"
          @current-change="onPage"
        />
      </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi } from '@/api/system'

const { t } = useI18n()

type NotificationOut = {
  id: number
  title: string
  content: string
  level: string
  biz_type: string | null
  biz_id: number | null
  read_at: string | null
  created_at: string
}

const router = useRouter()

const loading = ref(false)
const items = ref<NotificationOut[]>([])
const pager = reactive({ total: 0, page: 1 })
const query = reactive({
  unread: undefined as undefined | boolean,
  level: '' as '' | 'info' | 'warning' | 'error',
  offset: 0,
  limit: 20,
})

function bizRoute(bizType: string | null, bizId: number | null): string | null {
  if (bizType === 'report') return '/production/reports'
  if (bizType === 'salary_slip') return '/production/salary-slips'
  if (bizType === 'order' && bizId) return `/production/orders?keyword=${bizId}`
  if (bizType === 'crm_opportunity') return '/crm/opportunities'
  if (bizType === 'after_sale') return '/crm/after-sales'
  if (bizType === 'statement' && bizId) return `/finance/statements/${bizId}`
  return null
}

function levelTag(v: string) {
  if (v === 'warning') return 'warning'
  if (v === 'error') return 'danger'
  return 'info'
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await systemApi.listNotifications({
      unread: query.unread,
      level: query.level || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items ?? []
    pager.page = Math.floor(query.offset / query.limit) + 1
    pager.total = res.items?.length === query.limit ? query.offset + query.limit + 1 : query.offset + items.value.length
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function markRead(id: number) {
  await systemApi.markNotificationRead(id)
  ElMessage.success(t('system.notifications.marked'))
  await reload(false)
}

async function markAllRead() {
  const res = await systemApi.markAllNotificationsRead()
  ElMessage.success(t('system.notifications.updatedCount', { count: res.updated }))
  await reload(true)
}

function onRowClick(row: NotificationOut) {
  if (!row.read_at) {
    markRead(row.id)
  }
  const route = bizRoute(row.biz_type, row.biz_id)
  if (route) {
    router.push(route)
  }
}

onMounted(() => reload(true))
</script>
