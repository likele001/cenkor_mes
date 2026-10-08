<template>
  <div class="max-w-4xl space-y-6">
    <h2 class="text-lg font-semibold">{{ t('platform.aiModels.title') }}</h2>
    <p class="text-xs text-zinc-500">{{ t('platform.aiModels.desc') }}</p>

    <el-form v-loading="settingsLoading" label-width="120px" class="max-w-md">
      <el-form-item :label="t('platform.aiModels.enableAi')">
        <el-switch v-model="globalEnabled" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="settingsSaving" @click="saveSettings">
          {{ t('platform.aiModels.saveMasterSwitch') }}
        </el-button>
      </el-form-item>
    </el-form>

    <el-divider />

    <div class="flex items-center justify-between mb-2">
      <h3 class="font-medium">{{ t('platform.aiModels.gatewayList') }}</h3>
      <el-button type="primary" size="small" @click="openGateway()">{{ t('platform.aiModels.addGateway') }}</el-button>
    </div>
    <el-table
      v-loading="gatewaysLoading"
      :data="gateways"
      border
      size="small"
      highlight-current-row
      @current-change="onGatewaySelect"
    >
      <el-table-column prop="display_name" :label="t('platform.aiModels.name')" min-width="120" />
      <el-table-column prop="code" :label="t('platform.aiModels.code')" width="100" />
      <el-table-column prop="base_url" label="Base URL" min-width="180" show-overflow-tooltip />
      <el-table-column label="Key" width="70">
        <template #default="{ row }">
          <el-tag :type="row.api_key_configured ? 'success' : 'info'" size="small">
            {{ row.api_key_configured ? t('platform.aiModels.configured') : t('platform.aiModels.notConfigured') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('platform.aiModels.defaultGateway')" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" size="small">{{ t('platform.aiModels.default') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('platform.aiModels.enabled')" width="70">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? t('platform.aiModels.yes') : t('platform.aiModels.no') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('platform.aiModels.action')" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click.stop="selectGateway(row)">{{ t('platform.aiModels.manageModels') }}</el-button>
          <el-button link size="small" @click.stop="openGateway(row)">{{ t('platform.aiModels.edit') }}</el-button>
          <el-button v-if="!row.is_default" link size="small" @click.stop="setDefaultGateway(row)">{{ t('platform.aiModels.setDefaultGateway') }}</el-button>
          <el-button link size="small" :loading="testingGatewayId === row.id" @click.stop="testGateway(row)">{{ t('platform.aiModels.test') }}</el-button>
          <el-button link type="danger" size="small" @click.stop="removeGateway(row)">{{ t('platform.aiModels.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <template v-if="selectedGatewayId">
      <div class="flex items-center justify-between mb-2 mt-4">
        <h3 class="font-medium">
          {{ t('platform.aiModels.modelList') }}
          <span v-if="selectedGatewayName" class="text-zinc-500 font-normal text-sm">（{{ selectedGatewayName }}）</span>
        </h3>
        <el-button type="primary" size="small" @click="openModel()">{{ t('platform.aiModels.addModel') }}</el-button>
      </div>
      <el-table v-loading="modelsLoading" :data="models" border size="small">
        <el-table-column prop="display_name" :label="t('platform.aiModels.displayName')" min-width="120" />
        <el-table-column prop="code" :label="t('platform.aiModels.code')" width="120" />
        <el-table-column prop="model_id" label="Model ID" min-width="140" />
        <el-table-column :label="t('platform.aiModels.globalDefault')" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" size="small">{{ t('platform.aiModels.default') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('platform.aiModels.enabled')" width="70">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? t('platform.aiModels.yes') : t('platform.aiModels.no') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('platform.aiModels.action')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openModel(row)">{{ t('platform.aiModels.edit') }}</el-button>
            <el-button v-if="!row.is_default" link size="small" @click="setDefaultModel(row)">{{ t('platform.aiModels.setDefaultModel') }}</el-button>
            <el-button link type="danger" size="small" @click="removeModel(row)">{{ t('platform.aiModels.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="text-xs text-zinc-500 mt-2">{{ t('platform.aiModels.setDefaultModelDesc') }}</p>
    </template>
    <el-empty v-else :description="t('platform.aiModels.selectGatewayHint')" :image-size="64" class="mt-4" />

    <el-dialog v-model="gatewayDlg" :title="gatewayForm.id ? t('platform.aiModels.editGateway') : t('platform.aiModels.addGateway')" width="520px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item :label="t('platform.aiModels.code')"><el-input v-model="gatewayForm.code" :disabled="!!gatewayForm.id" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.displayName')"><el-input v-model="gatewayForm.display_name" /></el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="gatewayForm.base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="gatewayForm.api_key" type="password" show-password :placeholder="t('platform.aiModels.apiKeyPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('platform.aiModels.timeoutSeconds')">
          <el-input-number v-model="gatewayForm.timeout_seconds" :min="10" :max="600" />
        </el-form-item>
        <el-form-item :label="t('platform.aiModels.sort')"><el-input-number v-model="gatewayForm.sort_order" :min="0" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.enabled')"><el-switch v-model="gatewayForm.enabled" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.defaultGateway')"><el-switch v-model="gatewayForm.is_default" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="gatewayDlg = false">{{ t('platform.aiModels.cancel') }}</el-button>
        <el-button type="primary" :loading="gatewaySaving" @click="saveGateway">{{ t('platform.aiModels.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="modelDlg" :title="modelForm.id ? t('platform.aiModels.editModel') : t('platform.aiModels.addModel')" width="480px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item :label="t('platform.aiModels.code')"><el-input v-model="modelForm.code" :disabled="!!modelForm.id" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.displayName')"><el-input v-model="modelForm.display_name" /></el-form-item>
        <el-form-item label="Model ID"><el-input v-model="modelForm.model_id" placeholder="gpt-4o-mini" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.sort')"><el-input-number v-model="modelForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="Vision"><el-switch v-model="modelForm.is_vision" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.enabled')"><el-switch v-model="modelForm.is_active" /></el-form-item>
        <el-form-item :label="t('platform.aiModels.globalDefault')"><el-switch v-model="modelForm.is_default" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDlg = false">{{ t('platform.aiModels.cancel') }}</el-button>
        <el-button type="primary" :loading="modelSaving" @click="saveModel">{{ t('platform.aiModels.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { aiConfigApi } from '@/api/ai-config'

const { t } = useI18n()

const settingsLoading = ref(false)
const settingsSaving = ref(false)
const globalEnabled = ref(false)

const gatewaysLoading = ref(false)
const gateways = ref<Array<Record<string, any>>>([])
const selectedGatewayId = ref<number | null>(null)
const selectedGatewayName = ref('')

const modelsLoading = ref(false)
const models = ref<Array<Record<string, any>>>([])

const testingGatewayId = ref<number | null>(null)

const gatewayDlg = ref(false)
const gatewaySaving = ref(false)
const gatewayForm = reactive({
  id: 0,
  code: '',
  display_name: '',
  base_url: '',
  api_key: '',
  enabled: true,
  timeout_seconds: 120,
  sort_order: 0,
  is_default: false,
})

const modelDlg = ref(false)
const modelSaving = ref(false)
const modelForm = reactive({
  id: 0,
  code: '',
  display_name: '',
  model_id: '',
  is_vision: false,
  is_active: true,
  sort_order: 0,
  is_default: false,
})

async function loadSettings() {
  settingsLoading.value = true
  try {
    const res = await aiConfigApi.getSettings()
    globalEnabled.value = !!res?.enabled
  } finally {
    settingsLoading.value = false
  }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    await aiConfigApi.saveSettings({ enabled: globalEnabled.value })
    ElMessage.success(t('platform.aiModels.saved'))
  } catch (e: any) {
    ElMessage.error(e?.message || t('platform.aiModels.saveFailed'))
  } finally {
    settingsSaving.value = false
  }
}

async function loadGateways() {
  gatewaysLoading.value = true
  try {
    const res = await aiConfigApi.listGateways()
    gateways.value = res?.items || []
    if (selectedGatewayId.value) {
      const g = gateways.value.find((x) => Number(x.id) === selectedGatewayId.value)
      if (g) selectedGatewayName.value = String(g.display_name || '')
      else {
        selectedGatewayId.value = null
        models.value = []
      }
    }
  } finally {
    gatewaysLoading.value = false
  }
}

function selectGateway(row: Record<string, any>) {
  selectedGatewayId.value = Number(row.id)
  selectedGatewayName.value = String(row.display_name || '')
  loadModels()
}

function onGatewaySelect(row: Record<string, any> | null) {
  if (row) selectGateway(row)
}

async function loadModels() {
  if (!selectedGatewayId.value) return
  modelsLoading.value = true
  try {
    const res = await aiConfigApi.listModels(selectedGatewayId.value)
    models.value = res?.items || []
  } finally {
    modelsLoading.value = false
  }
}

function openGateway(row?: Record<string, any>) {
  if (row) {
    gatewayForm.id = Number(row.id)
    gatewayForm.code = String(row.code || '')
    gatewayForm.display_name = String(row.display_name || '')
    gatewayForm.base_url = String(row.base_url || '')
    gatewayForm.api_key = ''
    gatewayForm.enabled = row.enabled !== false
    gatewayForm.timeout_seconds = Number(row.timeout_seconds || 120)
    gatewayForm.sort_order = Number(row.sort_order || 0)
    gatewayForm.is_default = !!row.is_default
  } else {
    gatewayForm.id = 0
    gatewayForm.code = ''
    gatewayForm.display_name = ''
    gatewayForm.base_url = ''
    gatewayForm.api_key = ''
    gatewayForm.enabled = true
    gatewayForm.timeout_seconds = 120
    gatewayForm.sort_order = 0
    gatewayForm.is_default = gateways.value.length === 0
  }
  gatewayDlg.value = true
}

async function saveGateway() {
  if (!gatewayForm.code || !gatewayForm.display_name || !gatewayForm.base_url) {
    ElMessage.warning(t('platform.aiModels.fillRequiredFields'))
    return
  }
  gatewaySaving.value = true
  try {
    const payload: Record<string, any> = {
      code: gatewayForm.code,
      display_name: gatewayForm.display_name,
      base_url: gatewayForm.base_url,
      enabled: gatewayForm.enabled,
      timeout_seconds: gatewayForm.timeout_seconds,
      sort_order: gatewayForm.sort_order,
      is_default: gatewayForm.is_default,
    }
    if (gatewayForm.api_key) payload.api_key = gatewayForm.api_key
    if (gatewayForm.id) {
      await aiConfigApi.updateGateway(gatewayForm.id, payload)
    } else {
      await aiConfigApi.createGateway(payload)
    }
    gatewayDlg.value = false
    ElMessage.success(t('platform.aiModels.saved'))
    await loadGateways()
    if (!selectedGatewayId.value && gateways.value.length === 1) {
      selectGateway(gateways.value[0])
    }
  } catch (e: any) {
    ElMessage.error(e?.message || t('platform.aiModels.saveFailed'))
  } finally {
    gatewaySaving.value = false
  }
}

async function setDefaultGateway(row: Record<string, any>) {
  await aiConfigApi.setDefaultGateway(Number(row.id))
  ElMessage.success(t('platform.aiModels.setDefaultGatewaySuccess'))
  await loadGateways()
}

async function testGateway(row: Record<string, any>) {
  testingGatewayId.value = Number(row.id)
  try {
    const res = await aiConfigApi.testConnection({ gateway_id: Number(row.id) })
    ElMessage.success(`${t('platform.aiModels.connectionSuccess')}${res?.reply || ''}`)
  } catch (e: any) {
    ElMessage.error(e?.message || t('platform.aiModels.testFailed'))
  } finally {
    testingGatewayId.value = null
  }
}

async function removeGateway(row: Record<string, any>) {
  await ElMessageBox.confirm(t('platform.aiModels.confirmDeleteGateway'), t('platform.aiModels.tip'))
  try {
    await aiConfigApi.deleteGateway(Number(row.id))
    if (selectedGatewayId.value === Number(row.id)) {
      selectedGatewayId.value = null
      models.value = []
    }
    ElMessage.success(t('platform.aiModels.deleted'))
    await loadGateways()
  } catch (e: any) {
    ElMessage.error(e?.message || t('platform.aiModels.deleteFailed'))
  }
}

function openModel(row?: Record<string, any>) {
  if (!selectedGatewayId.value) {
    ElMessage.warning(t('platform.aiModels.selectGatewayHint'))
    return
  }
  if (row) {
    modelForm.id = Number(row.id)
    modelForm.code = String(row.code || '')
    modelForm.display_name = String(row.display_name || '')
    modelForm.model_id = String(row.model_id || '')
    modelForm.is_vision = !!row.is_vision
    modelForm.is_active = row.is_active !== false
    modelForm.sort_order = Number(row.sort_order || 0)
    modelForm.is_default = !!row.is_default
  } else {
    modelForm.id = 0
    modelForm.code = ''
    modelForm.display_name = ''
    modelForm.model_id = ''
    modelForm.is_vision = false
    modelForm.is_active = true
    modelForm.sort_order = 0
    modelForm.is_default = models.value.length === 0
  }
  modelDlg.value = true
}

async function saveModel() {
  if (!selectedGatewayId.value) return
  if (!modelForm.code || !modelForm.display_name || !modelForm.model_id) {
    ElMessage.warning(t('platform.aiModels.fillRequiredFields'))
    return
  }
  modelSaving.value = true
  try {
    const payload = {
      gateway_id: selectedGatewayId.value,
      code: modelForm.code,
      display_name: modelForm.display_name,
      model_id: modelForm.model_id,
      is_vision: modelForm.is_vision,
      is_active: modelForm.is_active,
      sort_order: modelForm.sort_order,
      is_default: modelForm.is_default,
    }
    if (modelForm.id) {
      await aiConfigApi.updateModel(modelForm.id, payload)
    } else {
      await aiConfigApi.createModel(payload)
    }
    modelDlg.value = false
    ElMessage.success(t('platform.aiModels.saved'))
    await loadModels()
    await loadGateways()
  } catch (e: any) {
    ElMessage.error(e?.message || t('platform.aiModels.saveFailed'))
  } finally {
    modelSaving.value = false
  }
}

async function setDefaultModel(row: Record<string, any>) {
  await aiConfigApi.setDefaultModel(Number(row.id))
  ElMessage.success(t('platform.aiModels.setDefaultModelSuccess'))
  await loadModels()
  await loadGateways()
}

async function removeModel(row: Record<string, any>) {
  await ElMessageBox.confirm(t('platform.aiModels.confirmDeleteModel'), t('platform.aiModels.tip'))
  await aiConfigApi.deleteModel(Number(row.id))
  ElMessage.success(t('platform.aiModels.deleted'))
  await loadModels()
}

onMounted(async () => {
  await loadSettings()
  await loadGateways()
})
</script>
