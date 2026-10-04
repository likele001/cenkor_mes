<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('system.cloudStorage.title')" :description="t('system.cloudStorage.subtitle')">
    <template #actions>
      <el-button :loading="loading" @click="reload">{{ t('system.cloudStorage.refresh') }}</el-button>
    </template>

    <el-card class="mb-4" shadow="never">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-sm text-zinc-500">{{ t('system.cloudStorage.currentActive') }}</div>
          <div class="text-[18px] font-semibold mt-1">
            <el-tag :type="activeTagType" size="large">{{ providerLabel(view.active_provider) }}</el-tag>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-sm text-zinc-500">{{ t('system.cloudStorage.keepLocalBackup') }}</span>
          <el-switch
            v-model="keepLocalBackup"
            :loading="settingsSaving"
            @change="onToggleBackup"
          />
        </div>
      </div>
      <p v-if="keepLocalBackup" class="text-xs text-zinc-400 mt-2">{{ t('system.cloudStorage.keepLocalBackupHint') }}</p>
    </el-card>

    <el-tabs v-model="activeTab" type="border-card" tab-position="top">
      <el-tab-pane
        v-for="p in tabProviders"
        :key="p"
        :name="p"
        :label="providerLabel(p)"
      >
        <!-- local：内置无需凭据 -->
        <template v-if="p === 'local'">
          <el-alert type="info" :closable="false" class="mb-4" :title="t('system.cloudStorage.localHint')" />
          <el-button
            type="primary"
            :disabled="view.active_provider === 'local'"
            :loading="acting === 'local'"
            @click="onActivate('local')"
          >{{ t('system.cloudStorage.setActive') }}</el-button>
        </template>

        <!-- 云 provider -->
        <template v-else>
          <div class="flex items-center gap-2 mb-4">
            <el-tag :type="view.providers[p]?.configured ? 'success' : 'info'" size="small">
              {{ view.providers[p]?.configured ? t('system.cloudStorage.configured') : t('system.cloudStorage.notConfigured') }}
            </el-tag>
            <el-tag v-if="view.active_provider === p" type="warning" size="small">{{ t('system.cloudStorage.activeNow') }}</el-tag>
            <el-tag v-if="!isSupported(p)" type="danger" size="small">{{ t('system.cloudStorage.driverNotReady') }}</el-tag>
          </div>

          <el-form label-width="140px" label-position="left">
            <el-form-item
              v-for="f in providerFields(p)"
              :key="f.key"
              :label="t(`system.cloudStorage.fields.${f.key}`)"
            >
              <el-input
                v-model="forms[p][f.key]"
                :type="f.secret ? 'text' : 'text'"
                :show-password="f.secret"
                :placeholder="f.required ? t('system.cloudStorage.requiredTag') : ''"
                autocomplete="off"
              />
              <div v-if="f.hint" class="text-xs text-zinc-400 mt-1">{{ t(`system.cloudStorage.hints.${f.key}`) }}</div>
            </el-form-item>
          </el-form>

          <div class="flex items-center gap-2 flex-wrap mt-2">
            <el-button type="primary" :loading="saving === p" @click="onSave(p)">{{ t('system.cloudStorage.save') }}</el-button>
            <el-button :loading="testing === p" @click="onTest(p)">{{ t('system.cloudStorage.testConnection') }}</el-button>
            <el-button
              :disabled="view.active_provider === p || !isSupported(p) || !view.providers[p]?.configured"
              :loading="acting === p"
              @click="onActivate(p)"
            >{{ t('system.cloudStorage.setActive') }}</el-button>
            <el-button
              v-if="view.providers[p]?.configured"
              type="danger"
              plain
              :loading="clearing === p"
              @click="onClear(p)"
            >{{ t('system.cloudStorage.clearCreds') }}</el-button>
          </div>

          <el-alert
            v-if="lastTest[p]"
            class="mt-4"
            :type="lastTest[p].ok ? 'success' : 'error'"
            :closable="true"
            :title="lastTest[p].ok ? t('system.cloudStorage.testOk') : t('system.cloudStorage.testFail')"
          >
            <pre class="text-xs whitespace-pre-wrap">{{ JSON.stringify(lastTest[p].detail || lastTest[p].error, null, 2) }}</pre>
          </el-alert>
        </template>
      </el-tab-pane>
    </el-tabs>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  systemApi,
  type CloudCredsPayload,
  type CloudHealthResult,
  type CloudStorageConfigView,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const saving = ref('')
const testing = ref('')
const acting = ref('')
const clearing = ref('')
const settingsSaving = ref(false)

const view = reactive<CloudStorageConfigView>({
  active_provider: 'local',
  keep_local_backup: false,
  supported_drivers: ['local'],
  providers: {},
})
const keepLocalBackup = ref(false)

const forms = reactive<Record<string, CloudCredsPayload>>({})
const lastTest = reactive<Record<string, CloudHealthResult | null>>({})

const activeTab = ref('local')

// 各 provider 需要展示的字段（required 仅用于占位提示，后端按非空合并保存）
type FieldDef = { key: keyof CloudCredsPayload; secret?: boolean; required?: boolean; hint?: boolean }
const FIELD_MAP: Record<string, FieldDef[]> = {
  aliyun: [
    { key: 'endpoint', required: true }, { key: 'bucket', required: true },
    { key: 'access_key', required: true }, { key: 'secret_key', secret: true, required: true },
    { key: 'region' }, { key: 'custom_domain', hint: true }, { key: 'prefix', hint: true },
  ],
  tencent: [
    { key: 'region', required: true }, { key: 'bucket', required: true },
    { key: 'access_key', required: true }, { key: 'secret_key', secret: true, required: true },
    { key: 'custom_domain', hint: true }, { key: 'prefix', hint: true },
  ],
  qiniu: [
    { key: 'bucket', required: true }, { key: 'access_key', required: true },
    { key: 'secret_key', secret: true, required: true }, { key: 'custom_domain', required: true, hint: true },
    { key: 'prefix', hint: true },
  ],
  upyun: [
    { key: 'bucket', required: true }, { key: 'access_key', required: true },
    { key: 'secret_key', secret: true, required: true }, { key: 'prefix', hint: true },
  ],
}

const CLOUD_ORDER = ['aliyun', 'tencent', 'qiniu', 'upyun']

const tabProviders = computed(() => {
  const keys = Object.keys(view.providers)
  const cloud = CLOUD_ORDER.filter((p) => keys.includes(p))
  return ['local', ...cloud]
})

const activeTagType = computed(() => (view.active_provider === 'local' ? 'info' : 'success'))

function providerFields(p: string): FieldDef[] {
  return FIELD_MAP[p] || []
}

function providerLabel(p: string): string {
  const key = `system.cloudStorage.providers.${p}`
  const label = t(key)
  return label === key ? p : label
}

function isSupported(p: string): boolean {
  return view.supported_drivers.map((d) => d.toLowerCase()).includes(p.toLowerCase())
}

function syncForms() {
  for (const p of CLOUD_ORDER) {
    const creds = view.providers[p]?.credentials || {}
    forms[p] = {
      endpoint: creds.endpoint || '',
      region: creds.region || '',
      bucket: creds.bucket || '',
      access_key: creds.access_key || '',
      secret_key: creds.secret_key || '',
      custom_domain: creds.custom_domain || '',
      prefix: creds.prefix || '',
    }
    if (!(p in lastTest)) lastTest[p] = null
  }
}

function applyView(data: CloudStorageConfigView) {
  view.active_provider = data.active_provider
  view.keep_local_backup = data.keep_local_backup
  view.supported_drivers = data.supported_drivers || ['local']
  view.providers = data.providers || {}
  keepLocalBackup.value = data.keep_local_backup
  syncForms()
}

async function reload() {
  loading.value = true
  try {
    applyView(await systemApi.getCloudStorage())
  } finally {
    loading.value = false
  }
}

async function onSave(p: string) {
  saving.value = p
  try {
    // 仅提交非空字段（空串交给后端"保留原值/忽略"，掩码字段同样被后端保留）
    const payload: CloudCredsPayload = {}
    for (const [k, v] of Object.entries(forms[p] || {})) {
      if (v !== undefined && v !== null) (payload as any)[k] = v
    }
    applyView(await systemApi.saveCloudCredentials(p, payload))
    ElMessage.success(t('system.cloudStorage.saved'))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    saving.value = ''
  }
}

async function onTest(p: string) {
  testing.value = p
  try {
    lastTest[p] = await systemApi.testCloudProvider(p)
  } catch (e: unknown) {
    lastTest[p] = { ok: false, provider: p, error: String(e) }
  } finally {
    testing.value = ''
  }
}

async function onActivate(p: string) {
  try {
    await ElMessageBox.confirm(
      t('system.cloudStorage.activateConfirm', { name: providerLabel(p) }),
      t('system.cloudStorage.setActive'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  acting.value = p
  try {
    applyView(await systemApi.activateCloudProvider(p))
    ElMessage.success(t('system.cloudStorage.activated'))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    acting.value = ''
  }
}

async function onClear(p: string) {
  try {
    await ElMessageBox.confirm(
      t('system.cloudStorage.clearConfirm', { name: providerLabel(p) }),
      t('system.cloudStorage.clearCreds'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  clearing.value = p
  try {
    applyView(await systemApi.clearCloudCredentials(p))
    ElMessage.success(t('system.cloudStorage.cleared'))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    clearing.value = ''
  }
}

async function onToggleBackup(val: boolean) {
  settingsSaving.value = true
  try {
    applyView(await systemApi.updateCloudSettings(val))
    ElMessage.success(t('system.cloudStorage.saved'))
  } catch (e: unknown) {
    ElMessage.error(String(e))
    keepLocalBackup.value = view.keep_local_backup // 回滚
  } finally {
    settingsSaving.value = false
  }
}

onMounted(reload)
</script>
