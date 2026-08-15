<template>
  <AdminPage :title="t('system.crmAdapter.title')">
    <el-tabs v-model="activeTab" class="mb-4">
      <el-tab-pane label="对接配置" name="config">
        <el-card v-loading="loading" class="mb-4">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div class="text-[16px] font-semibold">{{ t('system.crmAdapter.title') }}</div>
              <p class="text-xs text-zinc-500 mt-1">{{ t('system.crmAdapter.subtitle') }}</p>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <el-tag :type="form.configured ? 'success' : 'warning'" size="small">
                {{ form.configured ? t('system.crmAdapter.configuredYes') : t('system.crmAdapter.configuredNo') }}
              </el-tag>
              <el-button type="primary" :loading="saving" @click="save">{{ t('system.crmAdapter.save') }}</el-button>
            </div>
          </div>
        </el-card>

        <el-card v-loading="loading" shadow="never">
          <el-form label-width="190px" class="max-w-2xl">
            <el-form-item :label="t('system.crmAdapter.enabled')">
              <el-switch v-model="form.enabled" />
            </el-form-item>
            <el-form-item :label="t('system.crmAdapter.crmBaseUrl')">
              <el-input v-model="form.crm_base_url" placeholder="https://crm.cenkor.cn" />
            </el-form-item>
            <el-form-item :label="t('system.crmAdapter.connectionId')">
              <el-input v-model="form.connection_id" placeholder="CRM 连接 ID（cid）" />
              <div class="text-xs text-zinc-500 mt-1">{{ t('system.crmAdapter.connectionIdHint') }}</div>
            </el-form-item>
            <el-form-item :label="t('system.crmAdapter.apiKey')">
              <el-input v-model="apiKeyInput" type="password" show-password :placeholder="apiKeyPlaceholder" />
              <div class="text-xs text-zinc-500 mt-1">{{ t('system.crmAdapter.apiKeyHint') }}</div>
            </el-form-item>
            <el-form-item :label="t('system.crmAdapter.signWindow')">
              <el-input-number v-model="form.sign_window" :min="30" :max="3600" :step="30" />
              <span class="text-xs text-zinc-500 ml-2">{{ t('system.crmAdapter.signWindowHint') }}</span>
            </el-form-item>

            <el-divider>{{ t('system.crmAdapter.statusMapTitle') }}</el-divider>
            <p class="text-xs text-zinc-500 mb-3">{{ t('system.crmAdapter.statusMapHint') }}</p>
            <div v-for="(row, idx) in mapRows" :key="idx" class="flex items-center gap-2 mb-2">
              <el-input v-model="row.mes" :placeholder="t('system.crmAdapter.mesStatus')" class="w-48" />
              <span class="text-zinc-400">→</span>
              <el-select v-model="row.std" class="w-48">
                <el-option v-for="s in stdStatuses" :key="s" :label="s" :value="s" />
              </el-select>
              <el-button link type="danger" @click="mapRows.splice(idx, 1)">{{ t('system.crmAdapter.remove') }}</el-button>
            </div>
            <el-button @click="mapRows.push({ mes: '', std: 'producing' })">{{ t('system.crmAdapter.addMap') }}</el-button>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="产品映射" name="maps">
        <div class="flex items-center justify-between mb-3">
          <div class="text-xs text-zinc-500">
            把 CRM 的产品名(+规格) 精确对应到 MES 已有 SKU；CRM 推单时直接复用该 SKU，不再自动建占位。
          </div>
          <el-button type="primary" :loading="mapsLoading" @click="openAddMap">新增映射</el-button>
        </div>
        <el-table :data="maps" v-loading="mapsLoading" border empty-text="暂无映射">
          <el-table-column prop="crm_product_name" label="CRM 产品名" min-width="180" />
          <el-table-column prop="crm_spec" label="规格" width="160" />
          <el-table-column label="MES SKU" min-width="220">
            <template #default="{ row }">{{ skuLabel(row.mes_sku_id) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="danger" :loading="delId === row.id" @click="onDeleteMap(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="mapDialog" title="新增产品映射" width="520px">
      <el-form label-width="120px">
        <el-form-item label="CRM 产品名">
          <el-input v-model="mapForm.crm_product_name" placeholder="与 CRM 推送单里的 product_name 完全一致" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="mapForm.crm_spec" placeholder="与 CRM 的 spec 一致，可留空" />
        </el-form-item>
        <el-form-item label="MES SKU">
          <el-select
            v-model="mapForm.mes_sku_id"
            filterable
            remote
            :remote-method="onSearchSku"
            :loading="skuLoading"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="s in skuOptions"
              :key="s.id"
              :label="`${s.name} / ${s.spec || '-'} (${s.code})`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mapDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingMap" @click="onSaveMap">保存</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  crmAdapterApi,
  type CrmAdapterConfig,
  type CrmProductMap,
  type SkuOption,
} from '@/api/crm-adapter'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const apiKeyInput = ref('')
const mapRows = ref<{ mes: string; std: string }[]>([])

const stdStatuses = ['pending', 'producing', 'part_done', 'completed', 'cancelled']

const defaultForm = (): CrmAdapterConfig => ({
  crm_base_url: '',
  connection_id: '',
  api_key: '',
  status_map: {},
  enabled: true,
  sign_window: 300,
  configured: false,
})

const form = reactive<CrmAdapterConfig>(defaultForm())

const apiKeyPlaceholder = computed(() =>
  form.api_key ? t('system.crmAdapter.leaveEmptyNoChange') : t('system.crmAdapter.apiKeyPlaceholder'),
)

function loadMap(statusMap: Record<string, string>) {
  mapRows.value = Object.entries(statusMap).map(([mes, std]) => ({ mes, std }))
}

function toMap(): Record<string, string> {
  const m: Record<string, string> = {}
  for (const r of mapRows.value) {
    const mes = r.mes.trim()
    if (mes) m[mes] = r.std || 'producing'
  }
  return m
}

async function reload() {
  loading.value = true
  try {
    const data = await crmAdapterApi.getConfig()
    Object.assign(form, defaultForm(), data)
    apiKeyInput.value = ''
    loadMap(data.status_map || {})
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload: Partial<CrmAdapterConfig> = {
      crm_base_url: form.crm_base_url,
      connection_id: form.connection_id,
      status_map: toMap(),
      enabled: form.enabled,
      sign_window: form.sign_window,
    }
    if (apiKeyInput.value) payload.api_key = apiKeyInput.value
    await crmAdapterApi.saveConfig(payload)
    ElMessage.success(t('system.crmAdapter.saved'))
    await reload()
  } finally {
    saving.value = false
  }
}

// ---- 产品映射 ----
const activeTab = ref('config')
const maps = ref<CrmProductMap[]>([])
const mapsLoading = ref(false)
const mapDialog = ref(false)
const savingMap = ref(false)
const delId = ref<number | null>(null)
const skuOptions = ref<SkuOption[]>([])
const skuLoading = ref(false)
const skuLabelCache = ref<Record<number, string>>({})
const mapForm = reactive({ crm_product_name: '', crm_spec: '', mes_sku_id: null as number | null })

function skuLabel(id: number): string {
  return skuLabelCache.value[id] || `#${id}`
}

async function loadMaps() {
  mapsLoading.value = true
  try {
    maps.value = await crmAdapterApi.listProductMaps()
    await refreshSkuLabels()
  } finally {
    mapsLoading.value = false
  }
}

async function refreshSkuLabels() {
  if (!maps.value.length) return
  try {
    const data = await crmAdapterApi.listSkus()
    for (const s of data.items) {
      skuLabelCache.value[s.id] = `${s.name} / ${s.spec || '-'} (${s.code})`
    }
  } catch {
    /* 标签拉取失败不影响主流程 */
  }
}

async function onSearchSku(keyword: string) {
  skuLoading.value = true
  try {
    const data = await crmAdapterApi.listSkus(keyword || undefined)
    skuOptions.value = data.items
  } finally {
    skuLoading.value = false
  }
}

function openAddMap() {
  mapForm.crm_product_name = ''
  mapForm.crm_spec = ''
  mapForm.mes_sku_id = null
  skuOptions.value = []
  mapDialog.value = true
  onSearchSku('')
}

async function onSaveMap() {
  if (!mapForm.crm_product_name.trim()) {
    ElMessage.warning('请填写 CRM 产品名')
    return
  }
  if (!mapForm.mes_sku_id) {
    ElMessage.warning('请选择 MES SKU')
    return
  }
  savingMap.value = true
  try {
    await crmAdapterApi.createProductMap({
      crm_product_name: mapForm.crm_product_name.trim(),
      crm_spec: mapForm.crm_spec.trim(),
      mes_sku_id: mapForm.mes_sku_id,
    })
    ElMessage.success('已保存映射')
    mapDialog.value = false
    await loadMaps()
  } finally {
    savingMap.value = false
  }
}

async function onDeleteMap(row: CrmProductMap) {
  delId.value = row.id
  try {
    await crmAdapterApi.deleteProductMap(row.id)
    ElMessage.success('已删除')
    await loadMaps()
  } finally {
    delId.value = null
  }
}

onMounted(() => {
  reload()
  loadMaps()
})
</script>
