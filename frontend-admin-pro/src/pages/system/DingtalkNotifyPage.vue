<template>
  <AdminPage :title="t('system.dingtalk.title')">
    <el-card v-loading="loading" class="mb-4">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">{{ t('system.dingtalk.title') }}</div>
          <p class="text-xs text-zinc-500 mt-1">{{ t('system.dingtalk.subtitle') }}</p>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-button :loading="testing" @click="onTestConnection">{{ t('system.dingtalk.testConnection') }}</el-button>
          <el-button type="primary" :loading="saving" @click="save">{{ t('system.dingtalk.save') }}</el-button>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane :label="t('system.dingtalk.tabConnection')" name="connection">
        <el-form label-width="160px" class="max-w-2xl mt-4">
          <el-form-item :label="t('system.dingtalk.enabled')">
            <el-switch v-model="form.enabled" />
          </el-form-item>
          <el-form-item label="CorpId">
            <el-input v-model="form.corp_id" placeholder="dingxxx" />
          </el-form-item>
          <el-form-item label="AppKey">
            <el-input v-model="form.app_key" placeholder="dingxxx" />
          </el-form-item>
          <el-form-item label="AppSecret">
            <el-input v-model="appSecret" type="password" show-password :placeholder="secretPlaceholder" />
          </el-form-item>
          <el-form-item label="AgentId">
            <el-input v-model="form.agent_id" placeholder="123456789" />
          </el-form-item>
          <el-form-item :label="t('system.dingtalk.h5BaseUrl')">
            <el-input v-model="form.h5_public_base_url" />
          </el-form-item>
          <el-form-item :label="t('system.dingtalk.adminBaseUrl')">
            <el-input v-model="form.admin_public_base_url" />
          </el-form-item>
          <el-form-item :label="t('system.dingtalk.apiBaseUrl')">
            <el-input v-model="form.api_public_base_url" />
          </el-form-item>
          <el-form-item label="OAuth 回调">
            <el-input :model-value="form.oauth_redirect_url" readonly>
              <template #append>
                <el-button @click="copyOAuth">{{ t('system.dingtalk.copy') }}</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="报工卡片审核">
            <el-switch v-model="form.card_actions_enabled" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane :label="t('system.dingtalk.tabGroups')" name="groups">
        <el-table :data="form.groups" border stripe class="mt-4">
          <el-table-column prop="code" :label="t('system.dingtalk.groupCode')" width="140">
            <template #default="{ row }"><el-input v-model="row.code" size="small" /></template>
          </el-table-column>
          <el-table-column prop="name" :label="t('system.dingtalk.groupName')" width="160">
            <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
          </el-table-column>
          <el-table-column label="Webhook URL">
            <template #default="{ row }">
              <el-input v-model="row.webhook_url" size="small" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
            </template>
          </el-table-column>
          <el-table-column label="加签 Secret" width="160">
            <template #default="{ row }"><el-input v-model="row.webhook_secret" size="small" /></template>
          </el-table-column>
          <el-table-column width="80" align="center">
            <template #default="{ row }"><el-switch v-model="row.enabled" /></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.dingtalk.tabUsers')" name="users">
        <div class="mb-3 flex gap-2 flex-wrap mt-4">
          <el-input v-model="userKeyword" :placeholder="t('system.dingtalk.searchUser')" style="width: 200px" clearable @change="loadUsers" />
          <el-checkbox v-model="unboundOnly" @change="loadUsers">{{ t('system.dingtalk.unboundOnly') }}</el-checkbox>
          <el-button :loading="matching" @click="onBatchMatch">{{ t('system.dingtalk.batchMatchMobile') }}</el-button>
          <el-button @click="onAdminBind">{{ t('system.dingtalk.adminBind') }}</el-button>
        </div>
        <el-table :data="userBindings" border stripe v-loading="loadingUsers">
          <el-table-column prop="username" :label="t('system.dingtalk.username')" width="120" />
          <el-table-column prop="full_name" :label="t('system.dingtalk.fullName')" width="120" />
          <el-table-column prop="phone" label="手机" width="120" />
          <el-table-column label="userid" min-width="200">
            <template #default="{ row }">
              <el-input v-model="row.dingtalk_userid" size="small" @blur="saveUserBinding(row)" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.dingtalk.tabLogs')" name="logs">
        <el-table :data="pushLogs" border stripe class="mt-4" v-loading="loadingLogs">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="event_code" width="160" />
          <el-table-column prop="status" width="90" />
          <el-table-column prop="error_msg" show-overflow-tooltip />
          <el-table-column width="90">
            <template #default="{ row }">
              <el-button v-if="row.status === 'failed'" link type="primary" @click="retryLog(row.id)">{{ t('system.dingtalk.retry') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { dingtalkApi, type DingtalkPushLog, type DingtalkSettings, type DingtalkUserBinding } from '@/api/dingtalk'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const loadingUsers = ref(false)
const loadingLogs = ref(false)
const matching = ref(false)
const activeTab = ref('connection')
const appSecret = ref('')
const userKeyword = ref('')
const unboundOnly = ref(false)
const userBindings = ref<DingtalkUserBinding[]>([])
const pushLogs = ref<DingtalkPushLog[]>([])

const defaultForm = (): DingtalkSettings => ({
  enabled: false,
  corp_id: '',
  app_key: '',
  agent_id: '',
  app_secret_configured: false,
  app_secret_masked: '',
  message_format: 'action_card',
  card_actions_enabled: true,
  h5_public_base_url: '',
  admin_public_base_url: '',
  api_public_base_url: '',
  oauth_redirect_url: '',
  groups: [
    { code: 'production', name: '生产群', webhook_url: '', webhook_secret: '', enabled: true },
    { code: 'management', name: '管理群', webhook_url: '', webhook_secret: '', enabled: true },
    { code: 'factory', name: '全厂群', webhook_url: '', webhook_secret: '', enabled: true },
  ],
  rules: {},
  quiet_hours: { enabled: false, start: '22:00', end: '07:00' },
  event_catalog: [],
  target_options: [],
})

const form = reactive<DingtalkSettings>(defaultForm())
const secretPlaceholder = computed(() =>
  form.app_secret_configured ? t('system.dingtalk.leaveEmptyNoChange') : 'AppSecret',
)

function mergeSettings(data: DingtalkSettings) {
  Object.assign(form, defaultForm(), data)
  appSecret.value = ''
}

async function reload() {
  loading.value = true
  try {
    mergeSettings(await dingtalkApi.getSettings())
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      enabled: form.enabled,
      message_format: form.message_format,
      card_actions_enabled: form.card_actions_enabled,
      h5_public_base_url: form.h5_public_base_url,
      admin_public_base_url: form.admin_public_base_url,
      api_public_base_url: form.api_public_base_url,
      groups: form.groups,
      rules: form.rules,
      quiet_hours: form.quiet_hours,
    }
    if (form.corp_id.trim()) payload.corp_id = form.corp_id.trim()
    if (form.app_key.trim()) payload.app_key = form.app_key.trim()
    if (form.agent_id.trim()) payload.agent_id = form.agent_id.trim()
    if (appSecret.value) payload.app_secret = appSecret.value
    mergeSettings(await dingtalkApi.saveSettings(payload))
    ElMessage.success(t('system.dingtalk.saved'))
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testing.value = true
  try {
    const res = await dingtalkApi.testConnection()
    ElMessage.success(res.token_preview ? `连接成功 ${res.token_preview}` : '连接成功')
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    testing.value = false
  }
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    userBindings.value = (await dingtalkApi.listUserBindings({
      keyword: userKeyword.value || undefined,
      unbound_only: unboundOnly.value,
    })).items || []
  } finally {
    loadingUsers.value = false
  }
}

async function saveUserBinding(row: DingtalkUserBinding) {
  await dingtalkApi.updateUserBinding(row.id, { dingtalk_userid: row.dingtalk_userid || '' })
}

async function onBatchMatch() {
  matching.value = true
  try {
    const res = await dingtalkApi.batchMatchMobile()
    ElMessage.success(t('system.dingtalk.matchResult', { matched: res.matched, total: res.total }))
    await loadUsers()
  } finally {
    matching.value = false
  }
}

async function onAdminBind() {
  const res = await dingtalkApi.getBindUrl()
  if (res.authorize_url) window.open(res.authorize_url, '_blank')
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    pushLogs.value = (await dingtalkApi.listPushLogs({ limit: 100 })).items || []
  } finally {
    loadingLogs.value = false
  }
}

async function retryLog(id: number) {
  await dingtalkApi.retryPushLog(id)
  await loadLogs()
}

function copyOAuth() {
  if (form.oauth_redirect_url) {
    navigator.clipboard.writeText(form.oauth_redirect_url)
    ElMessage.success(t('system.dingtalk.copied'))
  }
}

onMounted(async () => {
  await reload()
  loadUsers()
  loadLogs()
})
</script>
