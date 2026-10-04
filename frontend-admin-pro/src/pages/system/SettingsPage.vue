<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="t('system.settings.title')">
    <el-card class="mb-4" v-loading="companyLoading">
      <div class="text-[16px] font-semibold mb-1">{{ t('system.settings.companyInfo') }}</div>
      <div class="text-xs text-zinc-500 mb-4">
        {{ t('system.settings.companyInfoHint') }}
      </div>
      <el-form :model="companyForm" label-width="140px" class="max-w-xl">
        <el-form-item :label="t('system.settings.companyName')">
          <el-input v-model="companyForm.name" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('system.settings.companyPhone')">
          <el-input v-model="companyForm.phone" maxlength="32" />
        </el-form-item>
        <el-form-item :label="t('system.settings.companyAddress')">
          <el-input v-model="companyForm.address" type="textarea" :rows="2" maxlength="256" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('system.settings.companyLogo')">
          <div class="flex items-center gap-3">
            <div
              class="w-14 h-14 rounded-lg overflow-hidden border shrink-0"
              :class="companyLogoUrl ? 'border-zinc-200 bg-white' : 'border-dashed border-zinc-300 flex items-center justify-center'"
            >
              <img v-if="companyLogoUrl" :src="companyLogoUrl" class="w-full h-full object-contain" />
              <span v-else class="text-xs text-zinc-400">{{ t('system.settings.noLogo') }}</span>
            </div>
            <el-upload
              :show-file-list="false"
              :http-request="onLogoUpload"
              :before-upload="beforeLogoUpload"
              :disabled="logoUploading"
              accept="image/*"
            >
              <el-button :loading="logoUploading">{{ t('system.settings.uploadLogo') }}</el-button>
            </el-upload>
            <el-button v-if="companyLogoUrl" link type="danger" :disabled="logoUploading" @click="removeCompanyLogo">
              {{ t('system.settings.removeLogo') }}
            </el-button>
          </div>
          <div class="text-xs text-zinc-500 mt-1">{{ t('system.settings.logoHint') }}</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="companySaving" @click="saveCompanyInfo">{{ t('system.settings.saveCompanyInfo') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mb-4" v-loading="modeLoading">
      <div class="text-[16px] font-semibold mb-1">{{ t('system.settings.reportMode') }}</div>
      <div class="text-xs text-zinc-500 mb-4">
        {{ t('system.settings.reportModeHint') }}
      </div>
      <el-form label-width="120px" class="max-w-xl">
        <el-form-item :label="t('system.settings.defaultMode')">
          <el-radio-group v-model="modeForm.default_mode">
            <el-radio
              v-for="m in modeOptions"
              :key="m.value"
              :value="m.value"
              :disabled="!m.enabled"
            >
              {{ m.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('system.settings.sequencePolicy')">
          <el-select v-model="modeForm.sequence_policy" class="!w-72">
            <el-option
              v-for="s in sequenceOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
          <div class="text-xs text-zinc-500 mt-1 ml-1">{{ sequenceHelp }}</div>
        </el-form-item>
        <p v-if="modeHelp" class="text-sm text-zinc-600 -mt-2 mb-2 ml-[120px]">{{ modeHelp }}</p>
        <el-form-item>
          <el-button type="primary" :loading="modeSaving" @click="saveModeSettings">{{ t('system.settings.saveMode') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mb-4" v-loading="wxLoading">
      <div class="text-[16px] font-semibold mb-1">{{ t('system.settings.wechatMiniapp') }}</div>
      <div class="text-xs text-zinc-500 mb-4" v-html="t('system.settings.wechatHint') + ' ' + t('system.settings.wechatBindHint')">
      </div>
      <el-form :model="wxForm" label-width="140px" class="max-w-xl">
        <el-form-item label="AppID">
          <el-input v-model="wxForm.app_id" placeholder="wx..." maxlength="64" />
        </el-form-item>
        <el-form-item label="AppSecret">
          <el-input
            v-model="wxForm.app_secret"
            type="password"
            show-password
            :placeholder="wxSecretPlaceholder"
            maxlength="128"
          />
          <p v-if="wxForm.app_secret_configured" class="text-xs text-zinc-500 mt-1">
            {{ t('system.settings.leaveEmptyNoChange') }}
          </p>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="wxSaving" @click="saveWxSettings">{{ t('system.settings.saveWxConfig') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mb-4" v-loading="mediaLoading">
      <div class="text-[16px] font-semibold mb-1">{{ t('system.settings.reportMedia') }}</div>
      <div class="text-xs text-zinc-500 mb-4">
        {{ t('system.settings.mediaHint') }}
      </div>
      <el-form :model="mediaForm" label-width="140px" class="max-w-xl">
        <el-form-item :label="t('system.settings.maxVideoSeconds')">
          <el-input-number v-model="mediaForm.max_video_seconds" :min="5" :max="120" /> 秒
        </el-form-item>
        <el-form-item :label="t('system.settings.maxVideoMb')">
          <el-input-number v-model="mediaForm.max_video_mb" :min="1" :max="50" /> MB
        </el-form-item>
        <el-form-item :label="t('system.settings.maxVideoCount')">
          <el-input-number v-model="mediaForm.max_video_count" :min="1" :max="10" />
        </el-form-item>
        <el-form-item :label="t('system.settings.maxPhotoCount')">
          <el-input-number v-model="mediaForm.max_photo_count" :min="1" :max="20" />
        </el-form-item>
        <el-form-item :label="t('system.settings.cameraOnly')">
          <el-switch v-model="mediaForm.camera_only" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="mediaSaving" @click="saveMediaSettings">{{ t('system.settings.saveMediaSettings') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[16px] font-semibold">{{ t('system.settings.settingTable') }}</div>
        <div class="flex items-center gap-2">
          <el-button type="primary" @click="openCreate">{{ t('system.settings.createOrUpdate') }}</el-button>
        </div>
      </div>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="key" :label="t('system.settings.key')" width="320" />
          <el-table-column :label="t('system.settings.value')">
            <template #default="{ row }">
              <pre class="text-[12px] whitespace-pre-wrap break-words m-0">{{ stringify(row.value) }}</pre>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" :label="t('system.settings.updateTime')" width="180" />
          <el-table-column :label="t('system.settings.operation')" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('system.users.edit') }}</el-button>
              <el-popconfirm :title="t('system.settings.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.roles.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.key" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0 font-mono text-sm font-semibold break-all">{{ row.key }}</div>
            </div>
            <pre class="text-[12px] whitespace-pre-wrap break-words m-0 bg-[#fafafa] p-2 rounded max-h-40 overflow-auto">{{ stringify(row.value) }}</pre>
            <div class="text-xs text-el-placeholder mt-2">{{ row.updated_at || '—' }}</div>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('system.users.edit') }}</el-button>
              <el-popconfirm :title="t('system.settings.confirmDelete')" @confirm="onDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger">{{ t('system.roles.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.settings.noSettings')" />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="dlg.open" :title="t('system.settings.createOrUpdateTitle')" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="80px">
        <el-form-item label="Key" prop="key">
          <el-input v-model="dlg.form.key" :disabled="dlg.lockKey" />
        </el-form-item>
        <el-form-item label="Value" prop="valueText">
          <el-input v-model="dlg.form.valueText" type="textarea" :rows="10" :placeholder="t('system.settings.valuePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('system.settings.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.settings.save') }}</el-button>
      </template>
    </el-dialog>  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type SettingOut } from '@/api/system'
import { useAppConfigStore } from '@/stores/app-config'

const { t } = useI18n()
const appConfig = useAppConfigStore()

const companyLoading = ref(false)
const companySaving = ref(false)
const logoUploading = ref(false)
const companyForm = reactive({ name: '', phone: '', address: '' })
const companyLogoUrl = ref('')

const loading = ref(false)
const items = ref<SettingOut[]>([])
const modeLoading = ref(false)
const modeSaving = ref(false)
const modeForm = reactive({ default_mode: 'batch', sequence_policy: 'soft' })
const modeOptions = ref<{ value: string; label: string; help: string; enabled: boolean }[]>([])
const modeHelp = computed(() => modeOptions.value.find((m) => m.value === modeForm.default_mode)?.help || '')
const sequenceOptions = ref<{ value: string; label: string; help: string }[]>([])
const sequenceHelp = computed(() => sequenceOptions.value.find((s) => s.value === modeForm.sequence_policy)?.help || '')

const wxLoading = ref(false)
const wxSaving = ref(false)
const wxForm = reactive({
  app_id: '',
  app_secret: '',
  app_secret_configured: false,
})
const wxSecretPlaceholder = computed(() =>
  wxForm.app_secret_configured ? t('system.settings.leaveEmptyNoChangeKey') : '从微信公众平台复制 AppSecret',
)

const mediaLoading = ref(false)
const mediaSaving = ref(false)
const mediaForm = reactive({
  max_video_seconds: 15,
  max_video_mb: 8,
  max_video_count: 3,
  max_photo_count: 5,
  camera_only: true,
})

const dlg = reactive({
  open: false,
  lockKey: false,
  saving: false,
  form: { key: '', valueText: '' },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  key: [{ required: true, message: () => t('system.settings.pleaseInputKey'), trigger: 'blur' }],
}

function stringify(v: any) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function parseValue(s: string): any {
  const t = s.trim()
  if (!t) return null
  if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']')) || t === 'true' || t === 'false' || t === 'null' || /^-?\d+(\.\d+)?$/.test(t)) {
    return JSON.parse(t)
  }
  return s
}

async function reload() {
  loading.value = true
  try {
    const res = await systemApi.listSettings({ offset: 0, limit: 500 })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dlg.lockKey = false
  dlg.form = { key: '', valueText: '' }
  dlg.open = true
}

function openEdit(row: SettingOut) {
  dlg.lockKey = true
  dlg.form = { key: row.key, valueText: stringify(row.value) }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const v = parseValue(dlg.form.valueText)
    await systemApi.upsertSetting(dlg.form.key, { value: v })
    dlg.open = false
    await reload()
  } finally {
    dlg.saving = false
  }
}

async function onDelete(row: SettingOut) {
  await systemApi.deleteSetting(row.key)
  await reload()
}

async function loadCompanyInfo() {
  companyLoading.value = true
  try {
    const cfg = await systemApi.getCompanyInfo()
    companyForm.name = cfg.name || ''
    companyForm.phone = cfg.phone || ''
    companyForm.address = cfg.address || ''
    companyLogoUrl.value = cfg.logo_url || ''
  } finally {
    companyLoading.value = false
  }
}

async function saveCompanyInfo() {
  companySaving.value = true
  try {
    const cfg = await systemApi.saveCompanyInfo({
      name: companyForm.name.trim(),
      phone: companyForm.phone.trim(),
      address: companyForm.address.trim(),
    })
    companyLogoUrl.value = cfg.logo_url || ''
    ElMessage.success(t('system.settings.companySaved'))
    await appConfig.load(true)
  } finally {
    companySaving.value = false
  }
}

const MAX_LOGO_BYTES = 2 * 1024 * 1024

function beforeLogoUpload(file: File) {
  if (file.size > MAX_LOGO_BYTES) {
    ElMessage.warning(t('system.settings.logoTooLarge'))
    return false
  }
  return true
}

async function onLogoUpload(options: UploadRequestOptions) {
  logoUploading.value = true
  try {
    const att = await systemApi.uploadAttachment(options.file as File)
    const cfg = await systemApi.saveCompanyInfo({ logo_attachment_id: att.id })
    companyLogoUrl.value = cfg.logo_url || ''
    ElMessage.success(t('system.settings.logoUploaded'))
    await appConfig.load(true)
  } finally {
    logoUploading.value = false
  }
}

async function removeCompanyLogo() {
  logoUploading.value = true
  try {
    await systemApi.saveCompanyInfo({ clear_logo: true })
    companyLogoUrl.value = ''
    await appConfig.load(true)
  } finally {
    logoUploading.value = false
  }
}

async function loadModeSettings() {
  modeLoading.value = true
  try {
    const cfg = await systemApi.getReportModeSettings()
    modeForm.default_mode = cfg.default_mode || 'batch'
    modeOptions.value = cfg.modes || []
    modeForm.sequence_policy = cfg.sequence_policy || 'soft'
    sequenceOptions.value = cfg.sequence_policies || []
  } finally {
    modeLoading.value = false
  }
}

async function saveModeSettings() {
  modeSaving.value = true
  try {
    await systemApi.saveReportModeSettings({ default_mode: modeForm.default_mode, sequence_policy: modeForm.sequence_policy })
    ElMessage.success(t('system.settings.modeSaved'))
    await loadModeSettings()
  } finally {
    modeSaving.value = false
  }
}

async function loadMediaSettings() {
  mediaLoading.value = true
  try {
    const cfg = await systemApi.getReportMediaSettings()
    Object.assign(mediaForm, cfg)
  } finally {
    mediaLoading.value = false
  }
}

async function saveMediaSettings() {
  mediaSaving.value = true
  try {
    await systemApi.saveReportMediaSettings({ ...mediaForm })
    ElMessage.success(t('system.settings.mediaSaved'))
  } finally {
    mediaSaving.value = false
  }
}

async function loadWxSettings() {
  wxLoading.value = true
  try {
    const cfg = await systemApi.getWechatMiniappSettings()
    wxForm.app_id = cfg.app_id || ''
    wxForm.app_secret_configured = cfg.app_secret_configured
    wxForm.app_secret = ''
  } finally {
    wxLoading.value = false
  }
}

async function saveWxSettings() {
  if (!wxForm.app_id.trim()) {
    ElMessage.warning(t('system.settings.pleaseInputAppID'))
    return
  }
  wxSaving.value = true
  try {
    const data: { app_id: string; app_secret?: string } = { app_id: wxForm.app_id.trim() }
    if (wxForm.app_secret.trim()) {
      data.app_secret = wxForm.app_secret.trim()
    }
    await systemApi.saveWechatMiniappSettings(data)
    ElMessage.success(t('system.settings.wxConfigSaved'))
    await loadWxSettings()
  } finally {
    wxSaving.value = false
  }
}

onMounted(() => {
  loadCompanyInfo()
  loadModeSettings()
  loadWxSettings()
  loadMediaSettings()
  reload()
})
</script>

