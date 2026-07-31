<template>
  <AdminPage :title="t('system.operationLogs.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap justify-end">
          <el-input v-model="query.keyword" :placeholder="t('system.operationLogs.keywordPlaceholder')" clearable style="width: 180px" @keyup.enter="reload(true)" />
          <el-input v-model="query.module" :placeholder="t('system.operationLogs.modulePlaceholder')" clearable style="width: 180px" @keyup.enter="reload(true)" />
          <el-input v-model="query.action" :placeholder="t('system.operationLogs.actionPlaceholder')" clearable style="width: 160px" @keyup.enter="reload(true)" />
          <el-input-number v-model="query.user_id" :min="1" :controls="false" :placeholder="t('system.operationLogs.userIdPlaceholder')" />
          <el-button @click="reload(true)">{{ t('system.operationLogs.query') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="created_at" :label="t('system.operationLogs.time')" width="180" />
          <el-table-column prop="username" :label="t('system.operationLogs.user')" width="140" />
          <el-table-column prop="module" :label="t('system.operationLogs.module')" width="200" />
          <el-table-column prop="action" :label="t('system.operationLogs.action')" width="160" />
          <el-table-column :label="t('system.operationLogs.object')" width="220">
            <template #default="{ row }">
              <span class="text-[12px] text-gray-700">{{ row.object_type || '-' }}{{ row.object_id ? `#${row.object_id}` : '' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="detail" :label="t('system.operationLogs.detail')" min-width="260" />
          <el-table-column prop="path" :label="t('system.operationLogs.path')" min-width="220" />
          <el-table-column prop="ip" label="IP" width="140" />
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0 text-xs text-el-placeholder">{{ row.created_at }}</div>
              <span class="text-xs font-medium text-el-regular">#{{ row.id }}</span>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.operationLogs.user') }}</dt>
              <dd>{{ row.username || '—' }}</dd>
              <dt>{{ t('system.operationLogs.module') }}</dt>
              <dd>{{ row.module || '—' }}</dd>
              <dt>{{ t('system.operationLogs.action') }}</dt>
              <dd>{{ row.action || '—' }}</dd>
              <dt>{{ t('system.operationLogs.object') }}</dt>
              <dd>{{ row.object_type || '—' }}{{ row.object_id ? `#${row.object_id}` : '' }}</dd>
              <dt>{{ t('system.operationLogs.detail') }}</dt>
              <dd class="text-left">{{ row.detail || '—' }}</dd>
              <dt>{{ t('system.operationLogs.path') }}</dt>
              <dd class="text-left break-all">{{ row.path || '—' }}</dd>
              <dt>IP</dt>
              <dd>{{ row.ip || '—' }}</dd>
            </dl>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.operationLogs.noData')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { systemApi, type OperationLogOut } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const items = ref<OperationLogOut[]>([])
const query = reactive({
  keyword: '',
  module: '',
  action: '',
  user_id: null as number | null,
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await systemApi.listOperationLogs({ ...query })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

onMounted(() => reload(true))
</script>

