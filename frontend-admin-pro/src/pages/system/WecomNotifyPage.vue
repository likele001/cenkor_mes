<template>
  <AdminPage :title="t('system.wecom.title')">
    <el-card v-loading="loading" class="mb-4">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">{{ t('system.wecom.title') }}</div>
          <p class="text-xs text-zinc-500 mt-1">{{ t('system.wecom.subtitle') }}</p>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-button :loading="testing" @click="onTestConnection">{{ t('system.wecom.testConnection') }}</el-button>
          <el-button type="primary" :loading="saving" @click="save">{{ t('system.wecom.save') }}</el-button>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="setupChecklist && !setupChecklist.ready"
      type="warning"
      :closable="false"
      class="mb-4"
      :title="t('system.wecom.setupNotReady')"
    >
      <ul class="text-sm list-disc pl-5 space-y-2">
        <li v-for="(step, idx) in setupChecklist.steps" :key="idx">
          <el-tag v-if="step.done === true" type="success" size="small" class="mr-1">OK</el-tag>
          <el-tag v-else-if="step.done === false" type="danger" size="small" class="mr-1">!</el-tag>
          <strong>{{ step.title }}</strong>：{{ step.detail }}
        </li>
      </ul>
    </el-alert>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane :label="t('system.wecom.tabConnection')" name="connection">
        <div class="mt-4 mb-4 flex items-center gap-3 flex-wrap">
          <el-button :loading="checklistLoading" @click="onCheckSetup">{{ t('system.wecom.checkSetup') }}</el-button>
          <el-tag v-if="setupChecklist" :type="setupChecklist.ready ? 'success' : 'danger'" size="small">
            {{ setupChecklist.ready ? t('system.wecom.setupReady') : t('system.wecom.setupNotReady') }}
          </el-tag>
        </div>
        <el-form label-width="160px" class="max-w-2xl">
          <el-form-item :label="t('system.wecom.enabled')">
            <el-switch v-model="form.enabled" />
          </el-form-item>
          <el-form-item label="Corp ID">
            <el-input
              v-model="form.corp_id"
              placeholder="ww_xxx"
              maxlength="64"
              autocomplete="off"
              name="wecom-corp-id"
            />
            <p v-if="form.corp_id_configured" class="text-xs text-green-600 mt-1">已保存到数据库，刷新不会丢失</p>
          </el-form-item>
          <el-form-item label="Corp Secret">
            <el-input
              v-model="corpSecret"
              type="password"
              show-password
              :placeholder="secretPlaceholder"
              maxlength="128"
              autocomplete="new-password"
              name="wecom-corp-secret"
            />
            <p v-if="form.corp_secret_configured" class="text-xs text-green-600 mt-1">
              Secret 已保存（{{ form.corp_secret_masked }}），输入框留空表示不修改
            </p>
          </el-form-item>
          <el-form-item label="Agent ID">
            <el-input
              v-model="form.agent_id"
              placeholder="1000002"
              maxlength="32"
              autocomplete="off"
              name="wecom-agent-id"
            />
          </el-form-item>
          <el-form-item label="Token">
            <el-input
              v-model="tokenVal"
              type="password"
              show-password
              placeholder="回调 Token"
              maxlength="128"
              autocomplete="new-password"
              name="wecom-callback-token"
            />
            <p v-if="form.token_configured" class="text-xs text-green-600 mt-1">Token 已保存，留空表示不修改</p>
          </el-form-item>
          <el-form-item label="EncodingAESKey">
            <el-input
              v-model="encodingAesKey"
              type="password"
              show-password
              placeholder="回调 EncodingAESKey"
              maxlength="128"
              autocomplete="new-password"
              name="wecom-encoding-aes-key"
            />
            <p v-if="form.encoding_aes_key_configured" class="text-xs text-green-600 mt-1">EncodingAESKey 已保存，留空表示不修改</p>
          </el-form-item>
          <el-form-item :label="t('system.wecom.h5BaseUrl')">
            <el-input v-model="form.h5_public_base_url" placeholder="https://h5.example.com" autocomplete="off" />
            <p v-if="!form.h5_public_base_url && form.h5_public_base_url_default" class="text-xs text-zinc-500 mt-1">
              未填写时使用 .env 默认：{{ form.h5_public_base_url_default }}
            </p>
          </el-form-item>
          <el-form-item :label="t('system.wecom.adminBaseUrl')">
            <el-input v-model="form.admin_public_base_url" placeholder="https://admin.example.com" />
          </el-form-item>
          <el-form-item :label="t('system.wecom.apiBaseUrl')">
            <el-input v-model="form.api_public_base_url" placeholder="https://api.example.com" autocomplete="off" />
            <p v-if="!form.api_public_base_url && form.api_public_base_url_default" class="text-xs text-zinc-500 mt-1">
              未填写时使用 .env 默认：{{ form.api_public_base_url_default }}
            </p>
          </el-form-item>
          <el-form-item :label="t('system.wecom.messageFormat')">
            <el-radio-group v-model="form.message_format">
              <el-radio value="markdown">Markdown</el-radio>
              <el-radio value="text">{{ t('system.wecom.formatText') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="t('system.wecom.callbackUrl')">
            <el-input :model-value="form.callback_url" readonly>
              <template #append>
                <el-button @click="copyCallback">{{ t('system.wecom.copy') }}</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="t('system.wecom.quietHours')">
            <el-switch v-model="form.quiet_hours.enabled" class="mr-3" />
            <el-time-select v-model="form.quiet_hours.start" start="00:00" step="01:00" end="23:00" placeholder="开始" style="width: 120px" />
            <span class="mx-2">-</span>
            <el-time-select v-model="form.quiet_hours.end" start="00:00" step="01:00" end="23:00" placeholder="结束" style="width: 120px" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane :label="t('system.wecom.tabGroups')" name="groups">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-button @click="addGroup">{{ t('system.wecom.addGroup') }}</el-button>
        </div>
        <el-table :data="form.groups" border stripe>
          <el-table-column prop="code" :label="t('system.wecom.groupCode')" width="140">
            <template #default="{ row }">
              <el-input v-model="row.code" size="small" />
            </template>
          </el-table-column>
          <el-table-column prop="name" :label="t('system.wecom.groupName')" width="160">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column prop="webhook_url" label="Webhook URL">
            <template #default="{ row }">
              <el-input v-model="row.webhook_url" size="small" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.wecom.enabled')" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column width="80" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" @click="form.groups.splice($index, 1)">{{ t('system.wecom.remove') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.wecom.tabRules')" name="rules">
        <el-table :data="ruleRows" border stripe class="mt-4">
          <el-table-column prop="name" :label="t('system.wecom.event')" min-width="140" />
          <el-table-column prop="code" label="code" width="180" />
          <el-table-column :label="t('system.wecom.enabled')" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="form.rules[row.code].enabled" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.wecom.targets')" min-width="280">
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

      <el-tab-pane :label="t('system.wecom.tabUsers')" name="users">
        <el-alert type="info" :closable="false" class="mt-4 mb-3" title="员工绑定说明">
          <p class="text-sm">H5 自助绑定需在手机企业微信内扫码授权，<strong>电脑浏览器无法直接绑定</strong>。</p>
          <p class="text-sm mt-1">推荐：确保员工资料手机号与企微通讯录一致，点击下方「批量匹配手机号」一键绑定；也可手动填写 userid。</p>
        </el-alert>
        <div class="mb-3 flex gap-2 flex-wrap">
          <el-input v-model="userKeyword" :placeholder="t('system.wecom.searchUser')" style="width: 200px" clearable @change="loadUsers" />
          <el-checkbox v-model="unboundOnly" @change="loadUsers">{{ t('system.wecom.unboundOnly') }}</el-checkbox>
          <el-button :loading="matching" @click="onBatchMatch">{{ t('system.wecom.batchMatchMobile') }}</el-button>
        </div>
        <el-table :data="userBindings" border stripe v-loading="loadingUsers">
          <el-table-column prop="username" :label="t('system.wecom.username')" width="120" />
          <el-table-column prop="full_name" :label="t('system.wecom.fullName')" width="120" />
          <el-table-column prop="phone" label="手机" width="120" />
          <el-table-column label="userid" min-width="200">
            <template #default="{ row }">
              <el-input v-model="row.wecom_userid" size="small" placeholder="userid" @blur="saveUserBinding(row)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('system.wecom.bound')" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.bound ? 'success' : 'info'" size="small">{{ row.bound ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.wecom.tabDepartments')" name="departments">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-button @click="loadWecomDepts" :loading="loadingWecomDepts">{{ t('system.wecom.fetchWecomDepts') }}</el-button>
        </div>
        <el-table :data="deptBindings" border stripe class="mt-2" v-loading="loadingDepts">
          <el-table-column prop="name" :label="t('system.wecom.deptName')" width="160" />
          <el-table-column prop="code" label="code" width="120" />
          <el-table-column label="wecom_department_id" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.wecom_department_id" filterable allow-create clearable size="small" @change="saveDeptBinding(row)">
                <el-option v-for="d in wecomDeptOptions" :key="d.department_id" :label="`${d.name} (${d.department_id})`" :value="String(d.department_id)" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="t('system.wecom.deptGroup')" width="160">
            <template #default="{ row }">
              <el-select v-model="row.wecom_chat_group_code" clearable size="small" @change="saveDeptBinding(row)">
                <el-option v-for="g in form.groups" :key="g.code" :label="g.name" :value="g.code" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.wecom.tabLogs')" name="logs">
        <div class="mt-4 mb-3 flex gap-2">
          <el-select v-model="logStatus" clearable :placeholder="t('system.wecom.status')" style="width: 120px" @change="loadLogs">
            <el-option label="pending" value="pending" />
            <el-option label="deferred" value="deferred" />
            <el-option label="success" value="success" />
            <el-option label="failed" value="failed" />
          </el-select>
          <el-button @click="loadLogs">{{ t('system.wecom.refresh') }}</el-button>
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
              <el-button v-if="row.status === 'failed'" link type="primary" @click="retryLog(row.id)">{{ t('system.wecom.retry') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('system.wecom.tabTest')" name="test">
        <el-form label-width="140px" class="max-w-xl mt-4">
          <el-form-item label="receive_id_type">
            <el-select v-model="testForm.receive_id_type" style="width: 200px">
              <el-option label="userid（个人）" value="userid" />
              <el-option label="webhook" value="webhook" />
            </el-select>
          </el-form-item>
          <el-form-item label="receive_id">
            <el-input v-model="testForm.receive_id" placeholder="userid / webhook url" />
          </el-form-item>
          <el-form-item :label="t('system.wecom.testContent')">
            <el-input v-model="testForm.text" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="testSending" @click="onTestSend">{{ t('system.wecom.testSend') }}</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  wecomApi,
  type WecomDeptBinding,
  type WecomPushLog,
  type WecomSettings,
  type WecomSetupChecklist,
  type WecomUserBinding,
} from '@/api/wecom'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const checklistLoading = ref(false)
const loadingUsers = ref(false)
const loadingDepts = ref(false)
const loadingLogs = ref(false)
const matching = ref(false)
const testSending = ref(false)
const setupChecklist = ref<WecomSetupChecklist | null>(null)
const activeTab = ref('connection')

const corpSecret = ref('')
const tokenVal = ref('')
const encodingAesKey = ref('')
const userKeyword = ref('')
const unboundOnly = ref(false)
const logStatus = ref('')
const userBindings = ref<WecomUserBinding[]>([])
const deptBindings = ref<WecomDeptBinding[]>([])
const pushLogs = ref<WecomPushLog[]>([])

const loadingWecomDepts = ref(false)
const wecomDeptOptions = ref<{ department_id: number; name: string }[]>([])

const testForm = reactive({
  receive_id_type: 'userid',
  receive_id: '',
  text: '辰科MES 企业微信推送测试',
})

const defaultForm = (): WecomSettings => ({
  enabled: false,
  corp_id: '',
  agent_id: '',
  corp_id_configured: false,
  agent_id_configured: false,
  corp_secret_configured: false,
  corp_secret_masked: '',
  token: '',
  token_configured: false,
  encoding_aes_key: '',
  encoding_aes_key_configured: false,
  message_format: 'markdown',
  h5_public_base_url: '',
  admin_public_base_url: '',
  api_public_base_url: '',
  h5_public_base_url_default: '',
  api_public_base_url_default: '',
  callback_url: '',
  oauth_redirect_url: '',
  groups: [
    { code: 'production', name: '生产群', webhook_url: '', enabled: true },
    { code: 'management', name: '管理群', webhook_url: '', enabled: true },
    { code: 'factory', name: '全厂群', webhook_url: '', enabled: true },
  ],
  rules: {},
  quiet_hours: { enabled: false, start: '22:00', end: '07:00' },
  event_catalog: [],
  target_options: [],
})

const form = reactive<WecomSettings>(defaultForm())

const secretPlaceholder = computed(() =>
  form.corp_secret_configured ? t('system.wecom.leaveEmptyNoChange') : 'Corp Secret',
)

const ruleRows = computed(() =>
  (form.event_catalog || []).map((e) => ({
    code: e.code,
    name: e.name,
    category: e.category,
  })),
)

function mergeSettings(data: WecomSettings) {
  Object.assign(form, defaultForm(), data)
  for (const ev of data.event_catalog || []) {
    if (!form.rules[ev.code]) {
      form.rules[ev.code] = { enabled: true, targets: [] }
    }
  }
  corpSecret.value = ''
  tokenVal.value = ''
  encodingAesKey.value = ''
}

async function reload() {
  loading.value = true
  try {
    mergeSettings(await wecomApi.getSettings())
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
      h5_public_base_url: form.h5_public_base_url,
      admin_public_base_url: form.admin_public_base_url,
      api_public_base_url: form.api_public_base_url,
      groups: form.groups,
      rules: form.rules,
      quiet_hours: form.quiet_hours,
    }
    if (form.corp_id.trim()) payload.corp_id = form.corp_id.trim()
    if (form.agent_id.trim()) payload.agent_id = form.agent_id.trim()
    if (corpSecret.value) payload.corp_secret = corpSecret.value
    if (tokenVal.value) payload.token = tokenVal.value
    if (encodingAesKey.value) payload.encoding_aes_key = encodingAesKey.value
    mergeSettings(await wecomApi.saveSettings(payload))
    ElMessage.success(t('system.wecom.saved'))
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testing.value = true
  try {
    const res = await wecomApi.testConnection()
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
    const res = await wecomApi.listUserBindings({
      keyword: userKeyword.value || undefined,
      unbound_only: unboundOnly.value,
    })
    userBindings.value = res.items || []
  } finally {
    loadingUsers.value = false
  }
}

async function saveUserBinding(row: WecomUserBinding) {
  await wecomApi.updateUserBinding(row.id, {
    wecom_userid: row.wecom_userid || '',
  })
  row.bound = Boolean((row.wecom_userid || '').trim())
}

async function onBatchMatch() {
  matching.value = true
  try {
    const res = await wecomApi.batchMatchMobile()
    ElMessage.success(t('system.wecom.matchResult', { matched: res.matched, total: res.total }))
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
    const res = await wecomApi.listDepartmentBindings()
    deptBindings.value = res.items || []
  } finally {
    loadingDepts.value = false
  }
}

async function saveDeptBinding(row: WecomDeptBinding) {
  await wecomApi.updateDepartmentBinding(row.id, {
    wecom_department_id: row.wecom_department_id || '',
    wecom_chat_group_code: row.wecom_chat_group_code || '',
  })
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    const res = await wecomApi.listPushLogs({ status: logStatus.value || undefined, limit: 100 })
    pushLogs.value = res.items || []
  } finally {
    loadingLogs.value = false
  }
}

async function retryLog(id: number) {
  await wecomApi.retryPushLog(id)
  ElMessage.success(t('system.wecom.retryQueued'))
  await loadLogs()
}

async function onTestSend() {
  testSending.value = true
  try {
    await wecomApi.testSend({
      receive_id: testForm.receive_id,
      receive_id_type: testForm.receive_id_type,
      text: testForm.text,
    })
    ElMessage.success(t('system.wecom.testSendOk'))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    testSending.value = false
  }
}

function addGroup() {
  form.groups.push({ code: '', name: '', webhook_url: '', enabled: true })
}

function copyCallback() {
  if (form.callback_url) {
    navigator.clipboard.writeText(form.callback_url)
    ElMessage.success(t('system.wecom.copied'))
  }
}

async function loadWecomDepts() {
  loadingWecomDepts.value = true
  try {
    const res = await wecomApi.listWecomDepartments()
    wecomDeptOptions.value = res.items || []
    ElMessage.success(t('system.wecom.deptsLoaded', { count: wecomDeptOptions.value.length }))
  } catch (e: unknown) {
    ElMessage.error(String(e))
  } finally {
    loadingWecomDepts.value = false
  }
}

async function loadSetupChecklist(silent = true) {
  try {
    setupChecklist.value = await wecomApi.getSetupChecklist()
  } catch {
    if (!silent) ElMessage.error(t('system.wecom.setupCheckFailed'))
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
