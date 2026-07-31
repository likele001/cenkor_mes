<template>
  <AdminPage :title="t('attendance.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-input-number
          v-model="query.user_id"
          :min="1"
          :controls="false"
          :placeholder="t('attendance.employeeId')"
          style="width: 140px"
          @change="reload(true)"
        />
        <el-date-picker
          v-model="query.range"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="~"
          :start-placeholder="t('attendance.dateRange')"
          :end-placeholder="t('attendance.dateRange')"
          @change="reload(true)"
        />
        <el-button type="primary" @click="openCreate">{{ t('common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('common.refresh') }}</el-button>
      </div>
    </template>

    <!-- GPS 围栏配置 -->
    <el-card shadow="never" class="mb-4" v-loading="geofence.loading">
      <template #header>
        <div class="flex items-center justify-between flex-wrap gap-2">
          <span class="font-medium">{{ t('attendance.geofenceTitle') }}</span>
          <el-switch v-model="geofence.form.enabled" :active-text="t('attendance.geofenceEnabled')" />
        </div>
      </template>
      <p class="text-xs text-zinc-500 mb-4">{{ t('attendance.geofenceHint') }}</p>
      <el-form label-width="120px" class="max-w-xl">
        <el-form-item :label="t('attendance.latitude')">
          <el-input-number
            v-model="geofence.form.lat"
            :precision="6"
            :step="0.0001"
            :disabled="!geofence.form.enabled"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('attendance.longitude')">
          <el-input-number
            v-model="geofence.form.lng"
            :precision="6"
            :step="0.0001"
            :disabled="!geofence.form.enabled"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('attendance.radiusM')">
          <el-input-number
            v-model="geofence.form.radius_m"
            :min="10"
            :max="50000"
            :step="10"
            :disabled="!geofence.form.enabled"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="geofence.saving" @click="saveGeofence">
            {{ t('attendance.saveGeofence') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-loading="loading">
      <el-table class="hidden lg:block w-full" :data="items" border>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="user_id" :label="t('attendance.employeeId')" width="90" />
        <el-table-column prop="user_name" label="姓名" width="120" />
        <el-table-column prop="work_date" :label="t('attendance.workDate')" width="120" />
        <el-table-column prop="check_in_at" :label="t('attendance.checkIn')" width="180" />
        <el-table-column prop="check_out_at" :label="t('attendance.checkOut')" width="180" />
        <el-table-column :label="t('attendance.location')" width="160">
          <template #default="{ row }">
            <span v-if="row.check_in_lat != null" class="text-xs font-mono">
              {{ row.check_in_lat?.toFixed(4) }}, {{ row.check_in_lng?.toFixed(4) }}
            </span>
            <span v-else class="text-zinc-400">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="minutes" :label="t('attendance.minutes')" width="90" />
        <el-table-column prop="remark" :label="t('attendance.remark')" min-width="160" show-overflow-tooltip />
        <el-table-column label="" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="min-w-0">
              <div class="font-semibold text-el-primary">{{ row.user_name || `#${row.user_id}` }}</div>
              <div class="text-xs text-el-placeholder">{{ row.work_date }} · #{{ row.id }}</div>
            </div>
          </div>
          <dl class="admin-mobile-kv">
            <dt>{{ t('attendance.checkIn') }}</dt>
            <dd>{{ row.check_in_at || '—' }}</dd>
            <dt>{{ t('attendance.checkOut') }}</dt>
            <dd>{{ row.check_out_at || '—' }}</dd>
            <dt>{{ t('attendance.location') }}</dt>
            <dd class="text-left text-xs font-mono">
              {{ row.check_in_lat != null ? `${row.check_in_lat?.toFixed(4)}, ${row.check_in_lng?.toFixed(4)}` : '—' }}
            </dd>
            <dt>{{ t('attendance.minutes') }}</dt>
            <dd>{{ row.minutes ?? '—' }}</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" :description="t('common.noData')" />
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

    <template #extra>
      <el-dialog
        v-model="dlg.open"
        :title="dlg.id ? t('attendance.editTitle') : t('attendance.createTitle')"
        width="520px"
        destroy-on-close
      >
        <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
          <el-form-item :label="t('attendance.employeeId')" prop="user_id" v-if="!dlg.id">
            <el-input-number v-model="dlg.form.user_id" :min="1" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('attendance.workDate')" prop="work_date" v-if="!dlg.id">
            <el-date-picker v-model="dlg.form.work_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="t('attendance.checkInTime')">
            <el-date-picker
              v-model="dlg.form.check_in_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="t('attendance.checkOutTime')">
            <el-date-picker
              v-model="dlg.form.check_out_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="t('attendance.remark')">
            <el-input v-model="dlg.form.remark" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dlg.open = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('common.save') }}</el-button>
        </template>
      </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi } from '@/api/system'

const { t } = useI18n()

type AttendanceRow = {
  id: number
  user_id: number
  user_name: string | null
  work_date: string
  check_in_at: string | null
  check_out_at: string | null
  check_in_lat?: number | null
  check_in_lng?: number | null
  minutes: number | null
  remark: string | null
}

const loading = ref(false)
const items = ref<AttendanceRow[]>([])
const pager = reactive({ total: 0, page: 1 })
const query = reactive({
  user_id: undefined as number | undefined,
  range: [] as string[],
  offset: 0,
  limit: 20,
})

const geofence = reactive({
  loading: false,
  saving: false,
  form: {
    enabled: false,
    lat: undefined as number | undefined,
    lng: undefined as number | undefined,
    radius_m: 200,
  },
})

const dlg = reactive({
  open: false,
  saving: false,
  id: 0 as number | 0,
  form: {
    user_id: undefined as number | undefined,
    work_date: '',
    check_in_at: '' as string | '',
    check_out_at: '' as string | '',
    remark: '' as string | '',
  },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  user_id: [{ required: true, message: () => t('attendance.employeeId'), trigger: 'blur' }],
  work_date: [{ required: true, message: () => t('attendance.workDate'), trigger: 'change' }],
}

async function loadGeofence() {
  geofence.loading = true
  try {
    const res = await systemApi.getAttendanceGeofence()
    geofence.form.enabled = !!res.enabled
    geofence.form.lat = res.lat ?? undefined
    geofence.form.lng = res.lng ?? undefined
    geofence.form.radius_m = res.radius_m ?? 200
  } finally {
    geofence.loading = false
  }
}

async function saveGeofence() {
  if (geofence.form.enabled && (geofence.form.lat == null || geofence.form.lng == null)) {
    ElMessage.warning(t('attendance.latitude'))
    return
  }
  geofence.saving = true
  try {
    await systemApi.setAttendanceGeofence({
      enabled: geofence.form.enabled,
      lat: geofence.form.enabled ? geofence.form.lat : null,
      lng: geofence.form.enabled ? geofence.form.lng : null,
      radius_m: geofence.form.radius_m,
    })
    ElMessage.success(t('attendance.geofenceSaved'))
  } catch {
    ElMessage.error(t('attendance.geofenceFailed'))
  } finally {
    geofence.saving = false
  }
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const date_from = query.range?.[0] || undefined
    const date_to = query.range?.[1] || undefined
    const res = await systemApi.listAttendanceRecords({
      user_id: query.user_id || undefined,
      date_from,
      date_to,
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

function openCreate() {
  dlg.id = 0
  dlg.form = { user_id: undefined, work_date: '', check_in_at: '', check_out_at: '', remark: '' }
  dlg.open = true
}

function openEdit(row: AttendanceRow) {
  dlg.id = row.id
  dlg.form = {
    user_id: row.user_id,
    work_date: row.work_date,
    check_in_at: row.check_in_at || '',
    check_out_at: row.check_out_at || '',
    remark: row.remark || '',
  }
  dlg.open = true
}

async function onSave() {
  if (!dlg.id) {
    const ok = await formRef.value?.validate().catch(() => false)
    if (!ok) return
  }
  dlg.saving = true
  try {
    const payload: any = {
      check_in_at: dlg.form.check_in_at || null,
      check_out_at: dlg.form.check_out_at || null,
      remark: dlg.form.remark || null,
    }
    if (dlg.id) {
      await systemApi.updateAttendanceRecord(dlg.id, payload)
    } else {
      await systemApi.createAttendanceRecord({ user_id: dlg.form.user_id, work_date: dlg.form.work_date, ...payload })
    }
    dlg.open = false
    await reload(true)
  } finally {
    dlg.saving = false
  }
}

onMounted(async () => {
  await Promise.all([loadGeofence(), reload(true)])
})
</script>
