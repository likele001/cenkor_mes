<template>
  <AdminPage :title="t('system.feishu.title')">
    <el-card v-loading="loading" class="mb-4">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">{{ t('system.feishu.title') }}</div>
          <p class="text-xs text-zinc-500 mt-1">{{ t('system.feishu.subtitle') }}</p>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-button :loading="testing" @click="onTestConnection">{{ t('system.feishu.testConnection') }}</el-button>
          <el-button type="primary" :loading="saving" @click="save">{{ t('system.feishu.save') }}</el-button>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="setupChecklist && !setupChecklist.ready"
      type="warning"
      :closable="false"
      class="mb-4"
      :title="t('system.feishu.personalSetupRequired')"
    >
      <p class="text-sm mb-2">{{ t('system.feishu.personalSetupHint') }}（{{ t('system.feishu.onlineVersion') }}：{{ setupChecklist.online_version || '-' }}）</p>
      <ul class="text-sm list-disc pl-5 space-y-2">
        <li v-for="(step, idx) in setupChecklist.steps" :key="idx">
          <el-tag v-if="step.done === true" type="success" size="small" class="mr-1">OK</el-tag>
          <el-tag v-else-if="step.done === false" type="danger" size="small" class="mr-1">!</el-tag>
          <strong>{{ step.title }}</strong>：{{ step.detail }}
        </li>
      </ul>
      <div v-if="setupChecklist.missing_events.length" class="mt-2 text-sm text-red-600">
        {{ t('system.feishu.missingEvents') }}：{{ setupChecklist.missing_events.map(e => e.code).join('、') }}
      </div>
      <el-button v-if="setupChecklist.bot_open_link" class="mt-3" type="primary" @click="openLink(setupChecklist.bot_open_link)">
        {{ t('system.feishu.openBotApp') }}
      </el-button>
      <el-button class="mt-3 ml-2" :loading="checklistLoading" @click="onCheckSetup">{{ t('system.feishu.refresh') }}</el-button>
    </el-alert>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane :label="t('system.feishu.tabConnection')" name="connection">
        <div class="mt-4 mb-4 flex items-center gap-3 flex-wrap">
          <el-button :loading="checklistLoading" @click="onCheckSetup">{{ t('system.feishu.checkSetup') }}</el-button>
          <el-tag v-if="setupChecklist" :type="setupChecklist.ready ? 'success' : 'danger'" size="small">
            {{ setupChecklist.ready ? t('system.feishu.setupReady') : t('system.feishu.setupNotReady') }}
          </el-tag>
          <span v-if="setupChecklist" class="text-xs text-zinc-500">{{ t('system.feishu.onlineVersion') }}：{{ setupChecklist.online_version || '-' }}</span>
        </div>
        <el-form label-width="160px" class="max-w-2xl">
          <el-form-item :label="t('system.feishu.enabled')">
            <el-switch v-model="form.enabled" />
          </el-form-item>
          <el-form-item label="App ID">
            <el-input v-model="form.app_id" placeholder="cli_xxx" maxlength="64" />
          </el-form-item>
          <el-form-item label="App Secret">
            <el-input v-model="appSecret" type="password" show-password :placeholder="secretPlaceholder" maxlength="128" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.tenantKey')">
            <el-input v-model="form.tenant_key" placeholder="可选" maxlength="128" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.encryptKey')">
            <el-input v-model="encryptKey" type="password" show-password placeholder="事件回调可选" maxlength="128" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.verificationToken')">
            <el-input v-model="verificationToken" type="password" show-password placeholder="事件回调可选" maxlength="128" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.h5BaseUrl')">
            <el-input v-model="form.h5_public_base_url" placeholder="https://h5.example.com" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.adminBaseUrl')">
            <el-input v-model="form.admin_public_base_url" placeholder="https://admin.example.com" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.apiBaseUrl')">
            <el-input v-model="form.api_public_base_url" placeholder="https://api.example.com" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.messageFormat')">
            <el-radio-group v-model="form.message_format">
              <el-radio value="card">{{ t('system.feishu.formatCard') }}</el-radio>
              <el-radio value="text">{{ t('system.feishu.formatText') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="t('system.feishu.cardActions')">
            <el-switch v-model="form.card_actions_enabled" />
            <span class="text-xs text-zinc-500 ml-2">{{ t('system.feishu.cardActionsHint') }}</span>
          </el-form-item>
          <el-form-item :label="t('system.feishu.personalUrgent')">
            <el-switch v-model="form.personal_urgent_enabled" />
            <span class="text-xs text-zinc-500 ml-2">{{ t('system.feishu.personalUrgentHint') }}</span>
          </el-form-item>
          <el-form-item :label="t('system.feishu.oauthRedirect')">
            <el-input :model-value="form.oauth_redirect_url" readonly />
          </el-form-item>
          <el-form-item :label="t('system.feishu.callbackUrl')">
            <el-input :model-value="form.callback_url" readonly>
              <template #append>
                <el-button @click="copyCallback">{{ t('system.feishu.copy') }}</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="t('system.feishu.quietHours')">
            <el-switch v-model="form.quiet_hours.enabled" class="mr-3" />
            <el-time-select v-model="form.quiet_hours.start" start="00:00" step="01:00" end="23:00" placeholder="开始" style="width: 120px" />
            <span class="mx-2">-</span>
            <el-time-select v-model="form.quiet_hours.end" start="00:00" step="01:00" end="23:00" placeholder="结束" style="width: 120px" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabGroups')" name="groups">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-button @click="loadChats" :loading="loadingChats">{{ t('system.feishu.fetchChats') }}</el-button>
          <el-button @click="addGroup">{{ t('system.feishu.addGroup') }}</el-button>
        </div>
        <el-table :data="form.groups" border stripe>
          <el-table-column prop="code" :label="t('system.feishu.groupCode')" width="140">
            <template #default="{ row }">
              <el-input v-model="row.code" size="small" />
            </template>
          </el-table-column>
          <el-table-column prop="name" :label="t('system.feishu.groupName')" width="160">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column prop="chat_id" label="chat_id">
            <template #default="{ row }">
              <el-select v-model="row.chat_id" filterable allow-create clearable placeholder="oc_xxx" style="width: 100%">
                <el-option v-for="c in chatOptions" :key="c.chat_id" :label="`${c.name} (${c.chat_id})`" :value="c.chat_id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column prop="webhook_url" label="Webhook">
            <template #default="{ row }">
              <el-input v-model="row.webhook_url" size="small" placeholder="可选" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.feishu.enabled')" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column width="80" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" @click="form.groups.splice($index, 1)">{{ t('system.feishu.remove') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabRules')" name="rules">
        <el-table :data="ruleRows" border stripe class="mt-4">
          <el-table-column prop="name" :label="t('system.feishu.event')" min-width="140" />
          <el-table-column prop="code" label="code" width="180" />
          <el-table-column :label="t('system.feishu.enabled')" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="form.rules[row.code].enabled" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.feishu.targets')" min-width="280">
            <template #default="{ row }">
              <el-select
                v-if="form.rules[row.code]"
                v-model="form.rules[row.code].targets"
                multiple
                collapse-tags
                collapse-tags-tooltip
                style="width: 100%"
              >
                <el-option v-for="opt in form.target_options" :key="opt.code" :label="opt.name" :value="opt.code" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabUsers')" name="users">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-input v-model="userKeyword" :placeholder="t('system.feishu.searchUser')" style="width: 200px" clearable @change="loadUsers" />
          <el-checkbox v-model="unboundOnly" @change="loadUsers">{{ t('system.feishu.unboundOnly') }}</el-checkbox>
          <el-button :loading="matching" @click="onBatchMatch">{{ t('system.feishu.batchMatchMobile') }}</el-button>
          <el-button :loading="matching" @click="onBatchRefresh">{{ t('system.feishu.batchRefreshOpenId') }}</el-button>
          <el-button @click="openBindForSelf">{{ t('system.feishu.bindMyFeishu') }}</el-button>
        </div>
        <el-table :data="userBindings" border stripe v-loading="loadingUsers">
          <el-table-column prop="username" :label="t('system.feishu.username')" width="120" />
          <el-table-column prop="full_name" :label="t('system.feishu.fullName')" width="120" />
          <el-table-column prop="phone" label="手机" width="120" />
          <el-table-column label="open_id" min-width="200">
            <template #default="{ row }">
              <el-input v-model="row.feishu_open_id" size="small" placeholder="ou_xxx" @blur="saveUserBinding(row)" />
            </template>
          </el-table-column>
          <el-table-column label="user_id" width="160">
            <template #default="{ row }">
              <el-input v-model="row.feishu_user_id" size="small" @blur="saveUserBinding(row)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.feishu.bound')" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.bound ? 'success' : 'info'" size="small">{{ row.bound ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.feishu.actions')" width="100" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openBindForUser(row.id)">{{ t('system.feishu.oauthBind') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabDepartments')" name="departments">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-button @click="loadFeishuDepts" :loading="loadingFeishuDepts">{{ t('system.feishu.fetchFeishuDepts') }}</el-button>
        </div>
        <el-table :data="deptBindings" border stripe class="mt-2" v-loading="loadingDepts">
          <el-table-column prop="name" :label="t('system.feishu.deptName')" width="160" />
          <el-table-column prop="code" label="code" width="120" />
          <el-table-column label="open_department_id" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.feishu_open_department_id" filterable allow-create clearable size="small" @change="saveDeptBinding(row)">
                <el-option v-for="d in feishuDeptOptions" :key="d.open_department_id" :label="`${d.name} (${d.open_department_id})`" :value="d.open_department_id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.feishu.deptGroup')" width="160">
            <template #default="{ row }">
              <el-select v-model="row.feishu_chat_group_code" clearable size="small" @change="saveDeptBinding(row)">
                <el-option v-for="g in form.groups" :key="g.code" :label="g.name" :value="g.code" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabLogs')" name="logs">
        <div class="mt-4 mb-3 flex gap-2">
          <el-select v-model="logStatus" clearable :placeholder="t('system.feishu.status')" style="width: 120px" @change="loadLogs">
            <el-option label="pending" value="pending" />
            <el-option label="deferred" value="deferred" />
            <el-option label="success" value="success" />
            <el-option label="failed" value="failed" />
          </el-select>
          <el-button @click="loadLogs">{{ t('system.feishu.refresh') }}</el-button>
        </div>
        <el-table :data="pushLogs" border stripe v-loading="loadingLogs">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="event_code" label="event" width="160" />
          <el-table-column prop="target_kind" width="80" />
          <el-table-column prop="target_ref" min-width="140" show-overflow-tooltip />
          <el-table-column prop="title" min-width="140" show-overflow-tooltip />
          <el-table-column prop="status" width="90" />
          <el-table-column prop="error_msg" min-width="120" show-overflow-tooltip />
          <el-table-column prop="created_at" width="170" />
          <el-table-column width="90" align="center">
            <template #default="{ row }">
              <el-button v-if="row.status === 'failed'" link type="primary" @click="retryLog(row.id)">{{ t('system.feishu.retry') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabCards')" name="cards">
        <div class="mt-4 max-w-3xl">
          <p class="text-xs text-zinc-500 mb-3">{{ t('system.feishu.cardPreviewHint') }}</p>
          <el-form label-width="120px">
            <el-form-item :label="t('system.feishu.event')">
              <el-select v-model="previewForm.event_code" style="width: 240px">
                <el-option v-for="ev in form.event_catalog" :key="ev.code" :label="ev.name" :value="ev.code" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('system.feishu.testContent')">
              <el-input v-model="previewForm.content" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item>
              <el-button :loading="previewLoading" @click="loadPreview">{{ t('system.feishu.previewCard') }}</el-button>
            </el-form-item>
          </el-form>
          <pre v-if="previewJson" class="text-xs bg-zinc-50 p-3 rounded border overflow-auto max-h-96">{{ previewJson }}</pre>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="t('system.feishu.tabTest')" name="test">
        <el-alert
          v-if="deliveryInfo"
          type="success"
          :closable="false"
          class="mt-4 mb-4"
          :title="t('system.feishu.testSendDeliveryHint')"
        >
          <p class="text-sm">{{ t('system.feishu.feishuTenant') }}：{{ deliveryInfo.feishu_tenant_name }}</p>
          <p class="text-sm">{{ t('system.feishu.boundFeishuUser') }}：{{ deliveryInfo.bound_feishu_name }}（{{ deliveryInfo.bound_feishu_email }}）</p>
          <p class="text-sm">{{ t('system.feishu.p2pMessageCount') }}：{{ deliveryInfo.p2p_message_count }}</p>
          <ul class="text-sm mt-2 list-disc pl-5">
            <li v-for="(hint, idx) in deliveryInfo.hints" :key="idx">{{ hint }}</li>
          </ul>
          <div class="mt-3 flex gap-2 flex-wrap">
            <el-button v-if="deliveryInfo.chat_open_link" type="primary" @click="openLink(deliveryInfo.chat_open_link)">
              {{ t('system.feishu.openBotChat') }}
            </el-button>
            <el-button v-if="deliveryInfo.bot_open_link" @click="openLink(deliveryInfo.bot_open_link)">
              {{ t('system.feishu.openBotApp') }}
            </el-button>
          </div>
        </el-alert>
        <el-form label-width="140px" class="max-w-xl mt-4">
          <el-form-item label="receive_id_type">
            <el-select v-model="testForm.receive_id_type" style="width: 200px">
              <el-option label="open_id（个人）" value="open_id" />
              <el-option label="chat_id（群）" value="chat_id" />
              <el-option label="webhook" value="webhook" />
            </el-select>
          </el-form-item>
          <el-form-item label="receive_id">
            <el-input v-model="testForm.receive_id" placeholder="ou_xxx / oc_xxx / webhook url" />
          </el-form-item>
          <el-form-item :label="t('system.feishu.testContent')">
            <el-input v-model="testForm.text" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="testSending" @click="onTestSend">{{ t('system.feishu.testSend') }}</el-button>
          </el-form-item>
        </el-form>
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
  feishuApi,
  type FeishuDeliveryDiagnostics,
  type FeishuDeptBinding,
  type FeishuPushLog,
  type FeishuSettings,
  type FeishuSetupChecklist,
  type FeishuUserBinding,
} from '@/api/feishu'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const checklistLoading = ref(false)
const loadingChats = ref(false)
const loadingUsers = ref(false)
const loadingDepts = ref(false)
const loadingLogs = ref(false)
const matching = ref(false)
const testSending = ref(false)
const deliveryInfo = ref<FeishuDeliveryDiagnostics | null>(null)
const setupChecklist = ref<FeishuSetupChecklist | null>(null)
const activeTab = ref('connection')

const appSecret = ref('')
const encryptKey = ref('')
const verificationToken = ref('')
const userKeyword = ref('')
const unboundOnly = ref(false)
const logStatus = ref('')
const chatOptions = ref<{ chat_id: string; name: string }[]>([])
const userBindings = ref<FeishuUserBinding[]>([])
const deptBindings = ref<FeishuDeptBinding[]>([])
const pushLogs = ref<FeishuPushLog[]>([])

const loadingFeishuDepts = ref(false)
const previewLoading = ref(false)
const previewJson = ref('')
const feishuDeptOptions = ref<{ open_department_id: string; name: string }[]>([])

const previewForm = reactive({
  event_code: 'report.submitted',
  content: '员工张三提交报工：合格 50，不良 2',
})

const testForm = reactive({
  receive_id_type: 'open_id',
  receive_id: '',
  text: '辰科MES 飞书推送测试',
})

const defaultForm = (): FeishuSettings => ({
  enabled: false,
  app_id: '',
  app_secret_configured: false,
  app_secret_masked: '',
  tenant_key: '',
  encrypt_key_configured: false,
  verification_token_configured: false,
  message_format: 'card',
  h5_public_base_url: '',
  admin_public_base_url: '',
  api_public_base_url: '',
  card_actions_enabled: true,
  personal_urgent_enabled: false,
  callback_url: '',
  oauth_redirect_url: '',
  groups: [
    { code: 'production', name: '生产群', chat_id: '', webhook_url: '', enabled: true },
    { code: 'management', name: '管理群', chat_id: '', webhook_url: '', enabled: true },
    { code: 'factory', name: '全厂群', chat_id: '', webhook_url: '', enabled: true },
  ],
  rules: {},
  quiet_hours: { enabled: false, start: '22:00', end: '07:00' },
  card_templates: {},
  event_catalog: [],
  target_options: [],
})

const form = reactive<FeishuSettings>(defaultForm())

const secretPlaceholder = computed(() =>
  form.app_secret_configured ? t('system.feishu.leaveEmptyNoChange') : 'App Secret',
)

const ruleRows = computed(() =>
  (form.event_catalog || []).map((e) => ({
    code: e.code,
    name: e.name,
    category: e.category,
  })),
)

function mergeSettings(data: FeishuSettings) {
  Object.assign(form, defaultForm(), data)
  for (const ev of data.event_catalog || []) {
    if (!form.rules[ev.code]) {
      form.rules[ev.code] = { enabled: true, targets: [] }
    }
  }
  appSecret.value = ''
  encryptKey.value = ''
  verificationToken.value = ''
}

async function reload() {
  loading.value = true
  try {
    mergeSettings(await feishuApi.getSettings())
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      enabled: form.enabled,
      app_id: form.app_id,
      tenant_key: form.tenant_key,
      message_format: form.message_format,
      h5_public_base_url: form.h5_public_base_url,
      admin_public_base_url: form.admin_public_base_url,
      api_public_base_url: form.api_public_base_url,
      card_actions_enabled: form.card_actions_enabled,
      personal_urgent_enabled: form.personal_urgent_enabled,
      groups: form.groups,
      rules: form.rules,
      quiet_hours: form.quiet_hours,
      card_templates: form.card_templates,
    }
    if (appSecret.value) payload.app_secret = appSecret.value
    if (encryptKey.value) payload.encrypt_key = encryptKey.value
    if (verificationToken.value) payload.verification_token = verificationToken.value
    mergeSettings(await feishuApi.saveSettings(payload))
    ElMessage.success(t('system.feishu.saved'))
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testing.value = true
  try {
    const res = await feishuApi.testConnection()
    ElMessage.success(res.token_preview ? `连接成功 ${res.token_preview}` : '连接成功')
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    testing.value = false
  }
}

async function loadChats() {
  loadingChats.value = true
  try {
    const res = await feishuApi.listChats()
    chatOptions.value = res.items || []
    ElMessage.success(t('system.feishu.chatsLoaded', { count: chatOptions.value.length }))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    loadingChats.value = false
  }
}

function addGroup() {
  form.groups.push({ code: '', name: '', chat_id: '', webhook_url: '', enabled: true })
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res = await feishuApi.listUserBindings({
      keyword: userKeyword.value || undefined,
      unbound_only: unboundOnly.value,
    })
    userBindings.value = res.items || []
  } finally {
    loadingUsers.value = false
  }
}

async function saveUserBinding(row: FeishuUserBinding) {
  await feishuApi.updateUserBinding(row.id, {
    feishu_open_id: row.feishu_open_id || '',
    feishu_user_id: row.feishu_user_id || '',
  })
  row.bound = Boolean((row.feishu_open_id || '').trim())
}

async function onBatchMatch() {
  matching.value = true
  try {
    const res = await feishuApi.batchMatchMobile(false)
    ElMessage.success(t('system.feishu.matchResult', { matched: res.matched, total: res.total }))
    await loadUsers()
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    matching.value = false
  }
}

async function onBatchRefresh() {
  try {
    await ElMessageBox.confirm(t('system.feishu.batchRefreshConfirm'), t('system.feishu.batchRefreshOpenId'), {
      type: 'warning',
    })
  } catch {
    return
  }
  matching.value = true
  try {
    const res = await feishuApi.batchMatchMobile(true)
    ElMessage.success(t('system.feishu.matchResult', { matched: res.matched, total: res.total }))
    await loadUsers()
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    matching.value = false
  }
}

async function loadDepts() {
  loadingDepts.value = true
  try {
    const res = await feishuApi.listDepartmentBindings()
    deptBindings.value = res.items || []
  } finally {
    loadingDepts.value = false
  }
}

async function saveDeptBinding(row: FeishuDeptBinding) {
  await feishuApi.updateDepartmentBinding(row.id, {
    feishu_open_department_id: row.feishu_open_department_id || '',
    feishu_chat_group_code: row.feishu_chat_group_code || '',
  })
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    const res = await feishuApi.listPushLogs({ status: logStatus.value || undefined, limit: 100 })
    pushLogs.value = res.items || []
  } finally {
    loadingLogs.value = false
  }
}

async function retryLog(id: number) {
  await feishuApi.retryPushLog(id)
  ElMessage.success(t('system.feishu.retryQueued'))
  await loadLogs()
}

async function onTestSend() {
  testSending.value = true
  try {
    const res = await feishuApi.testSend({
      receive_id: testForm.receive_id,
      receive_id_type: testForm.receive_id_type,
      text: testForm.text,
    })
    ElMessage.success(t('system.feishu.testSendOk'))
    deliveryInfo.value = res.delivery || null
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    testSending.value = false
  }
}

function openLink(url: string) {
  window.open(url, '_blank')
}

function copyCallback() {
  if (form.callback_url) {
    navigator.clipboard.writeText(form.callback_url)
    ElMessage.success(t('system.feishu.copied'))
  }
}

async function loadPreview() {
  previewLoading.value = true
  try {
    const res = await feishuApi.previewCard({
      event_code: previewForm.event_code,
      content: previewForm.content,
    })
    previewJson.value = JSON.stringify(res.card, null, 2)
  } finally {
    previewLoading.value = false
  }
}

async function openBindForUser(userId: number) {
  const res = await feishuApi.getBindUrl(userId)
  window.open(res.authorize_url, '_blank')
}

async function openBindForSelf() {
  const res = await feishuApi.getBindUrl()
  window.open(res.authorize_url, '_blank')
}

async function loadFeishuDepts() {
  loadingFeishuDepts.value = true
  try {
    const res = await feishuApi.listFeishuDepartments()
    feishuDeptOptions.value = res.items || []
    ElMessage.success(t('system.feishu.deptsLoaded', { count: feishuDeptOptions.value.length }))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    loadingFeishuDepts.value = false
  }
}

async function loadSetupChecklist(silent = true) {
  try {
    setupChecklist.value = await feishuApi.getSetupChecklist()
  } catch {
    if (!silent) ElMessage.error(t('system.feishu.setupCheckFailed'))
    setupChecklist.value = null
  }
  checklistLoading.value = false
}

async function onCheckSetup() {
  checklistLoading.value = true
  await loadSetupChecklist(false)
}

onMounted(async () => {
  await reload()
  await loadSetupChecklist()
  loadUsers()
  loadDepts()
  loadLogs()
})
</script>
