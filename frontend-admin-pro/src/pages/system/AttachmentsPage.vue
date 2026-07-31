<template>
  <AdminPage :title="t('system.attachments.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-select v-model="query.storage_driver" clearable :placeholder="t('system.attachments.storageDriver')" style="width: 140px">
            <el-option :label="t('system.attachments.local')" value="local" />
            <el-option :label="t('system.attachments.aliyunOss')" value="aliyun_oss" />
            <el-option :label="t('system.attachments.tencentCos')" value="tencent_cos" />
            <el-option :label="t('system.attachments.qiniu')" value="qiniu" />
          </el-select>
          <el-input v-model="query.keyword" :placeholder="t('system.attachments.searchPlaceholder')" clearable style="width: 240px" @keyup.enter="reload(true)" />
          <el-input-number v-model="query.uploader_id" :min="1" :controls="false" :placeholder="t('system.attachments.uploaderId')" />
          <el-upload :show-file-list="false" :http-request="onUpload" :disabled="uploading">
            <el-button type="primary" :loading="uploading">{{ t('system.attachments.uploadAttachment') }}</el-button>
          </el-upload>
          <el-button @click="reload(true)">{{ t('system.attachments.query') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="original_filename" :label="t('system.attachments.filename')" min-width="200" show-overflow-tooltip />
          <el-table-column prop="storage_driver" :label="t('system.attachments.driver')" width="120" />
          <el-table-column prop="content_type" :label="t('system.attachments.contentType')" width="160" />
          <el-table-column :label="t('system.attachments.size')" width="100">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column prop="uploader_id" :label="t('system.attachments.uploader')" width="90" />
          <el-table-column prop="created_at" :label="t('system.attachments.time')" width="170" />
          <el-table-column :label="t('system.attachments.preview')" width="180">
            <template #default="{ row }">
              <AttachmentPreview v-if="isPreviewable(row)" :attachment="row" :width="140" :height="90" />
              <span v-else class="text-xs text-zinc-400">—</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.attachments.operation')" width="160" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="downloadFile(row)">{{ t('system.attachments.download') }}</el-button>
              <el-button type="danger" link size="small" @click="removeFile(row)">{{ t('system.attachments.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary text-sm break-all">{{ row.original_filename }}</div>
                <div class="text-xs text-el-placeholder">#{{ row.id }} · {{ row.storage_driver }} · {{ row.created_at }}</div>
              </div>
            </div>
            <AttachmentPreview v-if="isPreviewable(row)" :attachment="row" :width="160" :height="100" class="mt-2" />
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.attachments.type') }}</dt>
              <dd>{{ row.content_type || '—' }}</dd>
              <dt>{{ t('system.attachments.size') }}</dt>
              <dd>{{ formatSize(row.size) }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button type="primary" link size="small" @click="downloadFile(row)">{{ t('system.attachments.download') }}</el-button>
              <el-button type="danger" link size="small" @click="removeFile(row)">{{ t('system.attachments.delete') }}</el-button>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.attachments.noAttachments')" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import AttachmentPreview from '@/components/AttachmentPreview.vue'
import { useI18n } from 'vue-i18n'
import { systemApi, type AttachmentOut } from '@/api/system'
import { http } from '@/utils/http'

const { t } = useI18n()

const loading = ref(false)
const uploading = ref(false)
const items = ref<AttachmentOut[]>([])
const query = reactive({
  keyword: '',
  uploader_id: null as number | null,
  storage_driver: '' as string,
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function isPreviewable(row: AttachmentOut) {
  const ct = (row.content_type || '').toLowerCase()
  return ct.startsWith('image/') || ct.startsWith('video/')
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const params: Record<string, unknown> = { ...query }
    if (!params.storage_driver) delete params.storage_driver
    if (!params.uploader_id) delete params.uploader_id
    const res = await systemApi.listAttachments(params)
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function onUpload(options: UploadRequestOptions) {
  uploading.value = true
  try {
    await systemApi.uploadAttachment(options.file as File)
    ElMessage.success(t('system.attachments.uploadSuccess'))
    await reload(true)
  } catch {
    ElMessage.error(t('system.attachments.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

function resolveDownloadUrl(row: AttachmentOut) {
  const direct = row.play_url || row.url
  if (direct?.startsWith('http')) return direct
  const origin = window.location.origin
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const prefix = base.startsWith('http') ? base.replace(/\/$/, '') : `${origin}${base}`.replace(/\/$/, '')
  if (direct?.startsWith('/')) return `${origin}${direct}`
  return `${prefix}/files/${row.id}?download=true`
}

async function downloadFile(row: AttachmentOut) {
  try {
    if (row.play_url?.startsWith('http')) {
      window.open(resolveDownloadUrl(row), '_blank')
      return
    }
    const blob = await http.request<Blob>({
      url: `/files/${row.id}`,
      method: 'GET',
      params: { download: true },
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(blob as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = row.original_filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch {
    ElMessage.error(t('system.attachments.downloadFailed'))
  }
}

async function removeFile(row: AttachmentOut) {
  try {
    await ElMessageBox.confirm(t('system.attachments.confirmDelete', { name: row.original_filename }), t('system.attachments.deleteTitle'), { type: 'warning' })
    await systemApi.deleteAttachment(row.id)
    ElMessage.success(t('system.attachments.deleted'))
    await reload(false)
  } catch {
    /* cancelled or failed */
  }
}

onMounted(() => reload(true))
</script>
