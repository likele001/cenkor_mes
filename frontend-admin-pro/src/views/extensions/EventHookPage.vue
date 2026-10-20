<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage title="扩展事件钩子" description="查看扩展挂载到核心业务流程的事件钩子：契约、订阅、执行流与拦截审计">
    <template #actions>
      <div class="flex items-center gap-2">
        <el-switch v-model="autoRefresh" active-text="自动刷新" />
        <el-button :loading="loading" @click="refreshAll">
          <el-icon class="mr-1"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </template>

    <!-- 顶部统计卡片区 -->
    <div class="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="text-xs text-gray-500">事件契约</div>
        <div class="mt-1 text-2xl font-bold text-gray-900">{{ catalogCount }}</div>
      </div>
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="text-xs text-gray-500">订阅关系</div>
        <div class="mt-1 text-2xl font-bold text-gray-900">{{ subsCount }}</div>
      </div>
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="text-xs text-gray-500">最近错误</div>
        <div class="mt-1 text-2xl font-bold" :class="errorCount > 0 ? 'text-red-600' : 'text-gray-900'">
          {{ errorCount }}
        </div>
      </div>
      <div class="rounded-lg border border-gray-200 bg-white p-4">
        <div class="text-xs text-gray-500">拦截否决</div>
        <div class="mt-1 text-2xl font-bold" :class="rejectionCount > 0 ? 'text-orange-600' : 'text-gray-900'">
          {{ rejectionCount }}
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="event-tabs">
      <!-- Tab 1 · 事件契约 -->
      <el-tab-pane label="事件契约" name="catalog">
        <div class="mb-3">
          <el-input
            v-model="catalogSearch"
            placeholder="搜索事件名"
            clearable
            style="width: 280px"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <el-table :data="filteredCatalog" stripe border v-loading="loading">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="p-4">
                <div class="mb-2 text-sm font-medium text-gray-700">payload 字段契约</div>
                <el-table :data="row.payloadList" size="small" border>
                  <el-table-column prop="name" label="字段名" width="200" />
                  <el-table-column prop="desc" label="说明" />
                </el-table>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="事件名" min-width="220" />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.phase === 'intercept' ? 'warning' : 'info'" size="small">
                {{ row.phase === 'intercept' ? '拦截型' : '通知型' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="payload 字段数" width="140">
            <template #default="{ row }">{{ row.payloadList.length }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 2 · 订阅关系 -->
      <el-tab-pane label="订阅关系" name="subscriptions">
        <div class="mb-3 flex items-center gap-2">
          <el-select v-model="subsExtFilter" clearable placeholder="按扩展筛选" style="width: 220px">
            <el-option v-for="k in extKeyOptions" :key="k" :label="k" :value="k" />
          </el-select>
          <el-select v-model="subsPhaseFilter" clearable placeholder="按类型筛选" style="width: 140px">
            <el-option label="通知型" value="notify" />
            <el-option label="拦截型" value="intercept" />
          </el-select>
        </div>
        <el-table :data="filteredSubs" stripe border v-loading="loading">
          <el-table-column prop="event_name" label="事件名" min-width="200" />
          <el-table-column prop="extension_name" label="扩展名" min-width="160" />
          <el-table-column prop="key" label="扩展 key" width="160" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="row.phase === 'intercept' ? 'warning' : 'info'" size="small">
                {{ row.phase === 'intercept' ? '拦截' : '通知' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="handler" label="handler" min-width="200" show-overflow-tooltip />
          <el-table-column label="超时预算" width="100">
            <template #default="{ row }">
              <span v-if="row.timeout">{{ row.timeout }}s</span>
              <span v-else class="text-gray-400">默认</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag v-if="!row.enabled" type="info" size="small">已禁用</el-tag>
              <el-tag v-else-if="!row.in_catalog" type="warning" size="small">未收录</el-tag>
              <el-tag v-else type="success" size="small">正常</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !filteredSubs.length" description="暂无订阅关系" />
      </el-tab-pane>

      <!-- Tab 3 · 最近事件 -->
      <el-tab-pane label="最近事件" name="recent">
        <div class="mb-3 flex items-center gap-2">
          <el-select v-model="recentPhaseFilter" clearable placeholder="按类型筛选" style="width: 140px">
            <el-option label="通知型" value="notify" />
            <el-option label="拦截型" value="intercept" />
          </el-select>
          <el-select v-model="recentExtFilter" clearable placeholder="按扩展筛选" style="width: 220px">
            <el-option v-for="k in extKeyOptions" :key="k" :label="k" :value="k" />
          </el-select>
        </div>
        <el-table :data="filteredRecent" stripe border v-loading="loading" max-height="600">
          <el-table-column prop="occurred_at" label="时间" width="170" />
          <el-table-column prop="event_name" label="事件名" min-width="180" />
          <el-table-column prop="ext_key" label="扩展" width="140" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="row.phase === 'intercept' ? 'warning' : 'info'" size="small">
                {{ row.phase === 'intercept' ? '拦截' : '通知' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">
              <span :class="row.elapsed_ms > 3000 ? 'text-red-600 font-medium' : ''">{{ row.elapsed_ms }}ms</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="!row.ok" type="danger" size="small">异常</el-tag>
              <el-tag v-else-if="row.allowed === false" type="warning" size="small">否决</el-tag>
              <el-tag v-else type="success" size="small">成功</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="详情" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="text-red-600">{{ row.error }}</span>
              <span v-else-if="row.reason" class="text-orange-600">{{ row.reason }}</span>
              <span v-else class="text-gray-400">—</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-if="!loading && !filteredRecent.length"
          description="暂无事件记录（服务重启后缓冲区已清空）"
        />
      </el-tab-pane>

      <!-- Tab 4 · 拦截审计 -->
      <el-tab-pane label="拦截审计" name="audit">
        <div class="mb-3 text-sm text-gray-600">
          最近 {{ interceptRecords.length }} 条拦截中：
          <el-tag type="success" size="small" class="mx-1">{{ auditAllowCount }} 次放行</el-tag>
          <el-tag type="warning" size="small" class="mx-1">{{ auditRejectCount }} 次否决</el-tag>
          <el-tag type="danger" size="small" class="mx-1">{{ auditErrorCount }} 次异常 fail-open</el-tag>
        </div>
        <el-table :data="interceptRecords" stripe border v-loading="loading" max-height="600">
          <el-table-column prop="occurred_at" label="时间" width="170" />
          <el-table-column prop="event_name" label="事件名" min-width="180" />
          <el-table-column prop="ext_key" label="扩展" width="140" />
          <el-table-column label="结果" width="120">
            <template #default="{ row }">
              <el-tag v-if="!row.ok" type="danger" size="small">异常放行</el-tag>
              <el-tag v-else-if="row.allowed === false" type="warning" size="small">否决</el-tag>
              <el-tag v-else type="success" size="small">放行</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="原因 / 错误" min-width="280" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="text-red-600">{{ row.error }}</span>
              <span v-else-if="row.reason" class="text-orange-600">{{ row.reason }}</span>
              <span v-else class="text-gray-400">—</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ row.elapsed_ms }}ms</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !interceptRecords.length" description="暂无拦截记录" />
      </el-tab-pane>
    </el-tabs>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  getEventCatalog,
  getEventSubscriptions,
  getRecentEvents,
  type EventCatalogEntry,
  type EventSubscription,
  type DispatchRecord,
} from '@/api/extensions'

const activeTab = ref<'catalog' | 'subscriptions' | 'recent' | 'audit'>('catalog')
const loading = ref(false)
const autoRefresh = ref(false)

const catalog = ref<Record<string, EventCatalogEntry>>({})
const subs = ref<EventSubscription[]>([])
const recent = ref<DispatchRecord[]>([])

// Tab 1 搜索
const catalogSearch = ref('')
const filteredCatalog = computed(() => {
  const q = catalogSearch.value.trim().toLowerCase()
  return Object.entries(catalog.value)
    .filter(([name]) => !q || name.toLowerCase().includes(q))
    .map(([name, entry]) => ({
      name,
      phase: entry.phase,
      payloadList: Object.entries(entry.payload).map(([pn, desc]) => ({ name: pn, desc })),
    }))
})

// Tab 2 筛选
const subsExtFilter = ref('')
const subsPhaseFilter = ref('')
const filteredSubs = computed(() =>
  subs.value.filter(
    (s) =>
      (!subsExtFilter.value || s.key === subsExtFilter.value) &&
      (!subsPhaseFilter.value || s.phase === subsPhaseFilter.value)
  )
)

// Tab 3 筛选
const recentPhaseFilter = ref('')
const recentExtFilter = ref('')
const filteredRecent = computed(() =>
  recent.value.filter(
    (r) =>
      (!recentPhaseFilter.value || r.phase === recentPhaseFilter.value) &&
      (!recentExtFilter.value || r.ext_key === recentExtFilter.value)
  )
)

// Tab 4 拦截审计
const interceptRecords = computed(() => recent.value.filter((r) => r.phase === 'intercept'))
const auditAllowCount = computed(() => interceptRecords.value.filter((r) => r.ok && r.allowed === true).length)
const auditRejectCount = computed(() => interceptRecords.value.filter((r) => r.ok && r.allowed === false).length)
const auditErrorCount = computed(() => interceptRecords.value.filter((r) => !r.ok).length)

// 顶部统计
const catalogCount = computed(() => Object.keys(catalog.value).length)
const subsCount = computed(() => subs.value.length)
const errorCount = computed(() => recent.value.filter((r) => !r.ok).length)
const rejectionCount = computed(() => recent.value.filter((r) => r.allowed === false).length)
const extKeyOptions = computed(() => Array.from(new Set(subs.value.map((s) => s.key))).sort())

async function refreshAll() {
  loading.value = true
  try {
    const [c, s, r] = await Promise.all([
      getEventCatalog(),
      getEventSubscriptions(),
      getRecentEvents({ limit: 200 }),
    ])
    catalog.value = c.items
    subs.value = s.items
    recent.value = r.items
  } catch {
    /* http 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

let timer: number | undefined
function setupAutoRefresh() {
  if (timer) window.clearInterval(timer)
  timer = window.setInterval(() => {
    if (autoRefresh.value && !loading.value) refreshAll()
  }, 5000)
}

onMounted(() => {
  refreshAll()
  setupAutoRefresh()
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.event-tabs :deep(.el-tabs__content) {
  padding-top: 8px;
}
</style>
