<template>
  <AdminPage :title="$t('cronJobs.title')">
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ $t('cronJobs.list') }}</span>
          <el-button size="small" :loading="reloading" @click="doReload">{{ $t('cronJobs.reload') }}</el-button>
        </div>
      </template>
      <el-table :data="items" stripe size="small" v-loading="loading">
        <el-table-column prop="name" label="任务名" width="200" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
        <el-table-column label="Cron 表达式" min-width="240">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" class="font-mono text-xs">
              {{ row.cron_minute }} {{ row.cron_hour }} {{ row.cron_day_of_month }} {{ row.cron_month_of_year }} {{ row.cron_day_of_week }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" size="small" @change="(v: boolean) => quickToggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次执行" width="150">
          <template #default="{ row }">{{ row.last_run_at ? row.last_run_at.slice(0, 19).replace('T', ' ') : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">{{ $t('common.edit') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog :model-value="editOpen" :title="$t('cronJobs.edit')" width="520px" destroy-on-close @update:model-value="editOpen = $event">
      <div v-if="editRow" class="space-y-4">
        <el-form-item :label="$t('cronJobs.name')">
          <el-input :model-value="editRow.name" disabled />
        </el-form-item>
        <el-form-item v-if="!editRow.is_system" :label="$t('cronJobs.description')">
          <el-input v-model="editForm.description" />
        </el-form-item>
        <el-form-item :label="$t('cronJobs.enabled')">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
        <div class="text-sm font-medium text-zinc-700 mb-1">{{ $t('cronJobs.cronExpression') }}</div>
        <div class="grid grid-cols-5 gap-2">
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.minute') }}</div>
            <el-input v-model="editForm.cron_minute" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.hour') }}</div>
            <el-input v-model="editForm.cron_hour" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.day') }}</div>
            <el-input v-model="editForm.cron_day_of_month" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.month') }}</div>
            <el-input v-model="editForm.cron_month_of_year" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.week') }}</div>
            <el-input v-model="editForm.cron_day_of_week" size="small" />
          </div>
        </div>
        <div class="text-xs text-zinc-400">{{ $t('cronJobs.cronHint') }}</div>
      </div>
      <template #footer>
        <el-button @click="editOpen = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { cronJobsApi, type CronJobOut } from '@/api/cron-jobs'

const { t } = useI18n()

const items = ref<CronJobOut[]>([])
const loading = ref(false)
const reloading = ref(false)

const editOpen = ref(false)
const editRow = ref<CronJobOut | null>(null)
const editForm = ref({
  enabled: true,
  description: '',
  cron_minute: '*',
  cron_hour: '*',
  cron_day_of_month: '*',
  cron_month_of_year: '*',
  cron_day_of_week: '*',
})
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await cronJobsApi.list()
    items.value = (res as any).items ?? []
  } finally {
    loading.value = false
  }
}

async function doReload() {
  reloading.value = true
  try {
    await cronJobsApi.reload()
    ElMessage.success(t('cronJobs.reloaded'))
    load()
  } finally {
    reloading.value = false
  }
}

function openEdit(row: CronJobOut) {
  editRow.value = row
  editForm.value = {
    enabled: row.enabled,
    description: row.description ?? '',
    cron_minute: row.cron_minute,
    cron_hour: row.cron_hour,
    cron_day_of_month: row.cron_day_of_month,
    cron_month_of_year: row.cron_month_of_year,
    cron_day_of_week: row.cron_day_of_week,
  }
  editOpen.value = true
}

async function doSave() {
  if (!editRow.value) return
  saving.value = true
  try {
    await cronJobsApi.update(editRow.value.id, editForm.value)
    ElMessage.success(t('cronJobs.saved'))
    editOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function quickToggle(row: CronJobOut, v: boolean) {
  try {
    await cronJobsApi.update(row.id, { enabled: v })
    row.enabled = v
    ElMessage.success(t('common.success'))
  } catch {
    ElMessage.error(t('common.failed'))
  }
}

onMounted(load)
</script>
