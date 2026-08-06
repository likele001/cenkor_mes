<template>
  <AdminPage :title="t('messageCenter.title')">
    <el-card v-loading="loading" class="mb-4">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">{{ t('messageCenter.title') }}</div>
          <p class="text-xs text-zinc-500 mt-1">{{ t('messageCenter.subtitle') }}</p>
        </div>
        <div class="flex gap-2">
          <el-button :loading="migrating" @click="onRunMigration">{{ t('messageCenter.runMigration') }}</el-button>
        </div>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 1. 通道总览 -->
      <el-tab-pane :label="t('messageCenter.tabOverview')" name="overview">
        <div v-if="overview" class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <el-card v-for="(info, key) in overview.channels" :key="key">
            <div class="flex items-center justify-between mb-3">
              <div class="text-base font-semibold">{{ t(`messageCenter.channel.${key}`) }}</div>
              <el-tag v-if="info.configured && info.enabled" type="success" size="small">{{ t('messageCenter.running') }}</el-tag>
              <el-tag v-else-if="!info.configured" type="info" size="small">{{ t('messageCenter.notConfigured') }}</el-tag>
              <el-tag v-else type="warning" size="small">{{ t('messageCenter.disabled') }}</el-tag>
            </div>
            <div class="text-sm space-y-2">
              <div class="flex justify-between"><span class="text-zinc-500">{{ t('messageCenter.todayTotal') }}</span><span class="font-medium">{{ info.today_total }}</span></div>
              <div class="text-xs text-zinc-500 truncate">
                <a v-if="info.callback_url" :href="info.callback_url" target="_blank">{{ info.callback_url }}</a>
              </div>
              <div class="text-xs text-zinc-500 truncate">
                <a v-if="info.oauth_redirect_url" :href="info.oauth_redirect_url" target="_blank">{{ info.oauth_redirect_url }}</a>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 2. 群组配置 -->
      <el-tab-pane :label="t('messageCenter.tabGroups')" name="groups">
        <div class="mt-4">
          <el-alert type="info" :closable="false" class="mb-3" :title="t('messageCenter.groupsHint')" />
          <el-table :data="groups" border stripe>
            <el-table-column prop="name" :label="t('messageCenter.groupName')" width="120" />
            <el-table-column prop="code" label="code" width="100" />
            <el-table-column :label="t('messageCenter.enabled')" width="80" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" />
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.feishuChannel')" min-width="240">
              <template #default="{ row }">
                <div v-if="row.channels.feishu" class="flex items-center gap-2">
                  <el-switch v-model="row.channels.feishu.enabled" />
                  <el-input v-model="row.channels.feishu.chat_id" placeholder="oc_xxx" size="small" :disabled="!row.channels.feishu.enabled" />
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.wecomChannel')" min-width="280">
              <template #default="{ row }">
                <div v-if="row.channels.wecom" class="flex items-center gap-2">
                  <el-switch v-model="row.channels.wecom.enabled" />
                  <el-input v-model="row.channels.wecom.webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" size="small" :disabled="!row.channels.wecom.enabled" />
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.dingtalkChannel')" min-width="280">
              <template #default="{ row }">
                <div v-if="row.channels.dingtalk" class="flex flex-col gap-1">
                  <div class="flex items-center gap-2">
                    <el-switch v-model="row.channels.dingtalk.enabled" />
                    <el-input v-model="row.channels.dingtalk.webhook_url" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." size="small" :disabled="!row.channels.dingtalk.enabled" />
                  </div>
                  <el-input v-model="row.channels.dingtalk.webhook_secret" placeholder="加签 Secret（可选）" size="small" :disabled="!row.channels.dingtalk.enabled" />
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="mt-3 flex items-center gap-3 flex-wrap">
            <el-button type="primary" :loading="savingGroups" @click="saveGroups">{{ t('messageCenter.save') }}</el-button>
            <span class="text-xs text-zinc-500">{{ t('messageCenter.groupsSaveHint') }}</span>
          </div>
        </div>
      </el-tab-pane>

      <!-- 3. 推送规则 -->
      <el-tab-pane :label="t('messageCenter.tabRules')" name="rules">
        <div class="mt-4">
          <el-table :data="rules" border stripe>
            <el-table-column :label="t('messageCenter.eventName')" min-width="180">
              <template #default="{ row }">
                <div class="font-medium">{{ getEventName(row.event_code) }}</div>
                <div class="text-xs text-zinc-500">{{ row.event_code }}</div>
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.feishuTargets')" min-width="200">
              <template #default="{ row }">
                <div v-if="row.feishu_rule && row.feishu_rule.targets" class="text-xs">
                  {{ formatTargets(row.feishu_rule.targets) }}
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.wecomTargets')" min-width="200">
              <template #default="{ row }">
                <div v-if="row.wecom_rule && row.wecom_rule.targets" class="text-xs">
                  {{ formatTargets(row.wecom_rule.targets) }}
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('messageCenter.dingtalkTargets')" min-width="200">
              <template #default="{ row }">
                <div v-if="row.dingtalk_rule && row.dingtalk_rule.targets" class="text-xs">
                  {{ formatTargets(row.dingtalk_rule.targets) }}
                </div>
                <span v-else class="text-xs text-zinc-400">-</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="mt-3 text-xs text-zinc-500">{{ t('messageCenter.rulesHint') }}</div>
        </div>
      </el-tab-pane>

      <!-- 4. 人员绑定 -->
      <el-tab-pane :label="t('messageCenter.tabBindings')" name="bindings">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-input v-model="userKeyword" :placeholder="t('messageCenter.searchUser')" style="width: 200px" clearable @change="loadBindings" />
          <el-checkbox v-model="unboundOnly" @change="loadBindings">{{ t('messageCenter.unboundOnly') }}</el-checkbox>
        </div>
        <el-table :data="bindings" border stripe v-loading="loadingBindings">
          <el-table-column prop="username" :label="t('messageCenter.username')" width="120" />
          <el-table-column prop="full_name" :label="t('messageCenter.fullName')" width="120" />
          <el-table-column prop="phone" label="手机" width="120" />
          <el-table-column :label="t('messageCenter.feishuStatus')" min-width="160">
            <template #default="{ row }">
              <el-tag v-if="row.feishu_open_id" type="success" size="small">{{ row.feishu_open_id }}</el-tag>
              <el-tag v-else type="info" size="small">{{ t('messageCenter.unbound') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('messageCenter.wecomStatus')" min-width="160">
            <template #default="{ row }">
              <el-tag v-if="row.wecom_userid" type="success" size="small">{{ row.wecom_userid }}</el-tag>
              <el-tag v-else type="info" size="small">{{ t('messageCenter.unbound') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('messageCenter.dingtalkStatus')" min-width="160">
            <template #default="{ row }">
              <el-tag v-if="row.dingtalk_userid" type="success" size="small">{{ row.dingtalk_userid }}</el-tag>
              <el-tag v-else type="info" size="small">{{ t('messageCenter.unbound') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('messageCenter.boundAt')" width="170">
            <template #default="{ row }">
              <div v-if="row.feishu_bound_at" class="text-xs">F: {{ row.feishu_bound_at }}</div>
              <div v-if="row.wecom_bound_at" class="text-xs">W: {{ row.wecom_bound_at }}</div>
              <div v-if="row.dingtalk_bound_at" class="text-xs">D: {{ row.dingtalk_bound_at }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 5. 推送日志 -->
      <el-tab-pane :label="t('messageCenter.tabLogs')" name="logs">
        <div class="mt-4 mb-3 flex gap-2 flex-wrap">
          <el-select v-model="logChannel" clearable :placeholder="t('messageCenter.channel')" style="width: 120px" @change="loadLogs">
            <el-option label="Feishu" value="feishu" />
            <el-option label="WeCom" value="wecom" />
            <el-option label="DingTalk" value="dingtalk" />
          </el-select>
          <el-select v-model="logStatus" clearable :placeholder="t('messageCenter.status')" style="width: 120px" @change="loadLogs">
            <el-option label="pending" value="pending" />
            <el-option label="deferred" value="deferred" />
            <el-option label="success" value="success" />
            <el-option label="failed" value="failed" />
          </el-select>
          <el-button @click="loadLogs">{{ t('messageCenter.refresh') }}</el-button>
        </div>
        <el-table :data="pushLogs" border stripe v-loading="loadingLogs">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="channel" label="Channel" width="90">
            <template #default="{ row }">
              <el-tag :type="row.channel === 'feishu' ? 'primary' : row.channel === 'dingtalk' ? 'warning' : 'success'" size="small">{{ row.channel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="event_code" label="event" width="160" />
          <el-table-column prop="target_kind" width="80" />
          <el-table-column prop="target_ref" min-width="120" show-overflow-tooltip />
          <el-table-column prop="title" min-width="120" show-overflow-tooltip />
          <el-table-column prop="status" width="90" />
          <el-table-column prop="retry_count" label="重试" width="60" align="center" />
          <el-table-column prop="error_msg" min-width="100" show-overflow-tooltip />
          <el-table-column prop="created_at" width="160" />
          <el-table-column width="100" align="center">
            <template #default="{ row }">
              <el-button v-if="row.status === 'failed'" link type="primary" @click="onRetry(row)">{{ t('messageCenter.retry') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 6. 告警接收人 -->
      <el-tab-pane :label="t('messageCenter.tabRecipients')" name="recipients">
        <div class="mt-4 mb-3">
          <el-alert type="info" :closable="false" :title="t('messageCenter.recipientsHint')" />
        </div>
        <div class="mt-4 flex gap-4">
          <div class="flex-1">
            <div class="text-sm font-medium mb-2">{{ t('messageCenter.allUsers') }}</div>
            <el-table :data="allUsers" border stripe v-loading="loadingUsers" height="500" @selection-change="onAllUserSelChange">
              <el-table-column type="selection" width="55" />
              <el-table-column prop="username" :label="t('messageCenter.username')" width="120" />
              <el-table-column prop="full_name" :label="t('messageCenter.fullName')" />
              <el-table-column :label="t('messageCenter.isSuperuser')" width="100">
                <template #default="{ row }">
                  <el-tag v-if="row.is_superuser" type="warning" size="small">超管</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="flex-1">
            <div class="text-sm font-medium mb-2">{{ t('messageCenter.recipients') }}</div>
            <el-table :data="recipients" border stripe height="500">
              <el-table-column prop="username" :label="t('messageCenter.username')" width="120" />
              <el-table-column prop="full_name" :label="t('messageCenter.fullName')" />
              <el-table-column :label="t('messageCenter.isSuperuser')" width="100">
                <template #default="{ row }">
                  <el-tag v-if="row.is_superuser" type="warning" size="small">超管</el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('messageCenter.actions')" width="80" align="center">
                <template #default="{ row }">
                  <el-button link type="danger" @click="removeRecipient(row.id)">-</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="mt-3 flex gap-2">
              <el-button type="primary" :loading="savingRecipients" @click="saveRecipients">{{ t('messageCenter.save') }}</el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  messageCenterApi,
  type AlertRecipient,
  type MessageGroup,
  type MessageRule,
  type MessageCenterOverview,
  type PushLog,
  type UserBinding,
} from '@/api/message-center'

const { t } = useI18n()

const activeTab = ref('overview')
const loading = ref(false)
const migrating = ref(false)

const overview = ref<MessageCenterOverview | null>(null)
const groups = ref<MessageGroup[]>([])
const rules = ref<MessageRule[]>([])
const eventCatalog = ref<{ code: string; name: string; category: string }[]>([])
const targetOptions = ref<{ code: string; name: string }[]>([])

const userKeyword = ref('')
const unboundOnly = ref(false)
const bindings = ref<UserBinding[]>([])
const loadingBindings = ref(false)

const logChannel = ref('')
const logStatus = ref('')
const pushLogs = ref<PushLog[]>([])
const loadingLogs = ref(false)

const allUsers = ref<AlertRecipient[]>([])
const recipients = ref<AlertRecipient[]>([])
const selectedAllUserIds = ref<number[]>([])
const loadingUsers = ref(false)
const savingRecipients = ref(false)
const savingGroups = ref(false)

function getEventName(code: string): string {
  return eventCatalog.value.find((e) => e.code === code)?.name || code
}

function formatTargets(targets: string[]): string {
  return targets
    .map((t) => targetOptions.value.find((o) => o.code === t)?.name || t)
    .join('、')
}

async function loadOverview() {
  loading.value = true
  try {
    overview.value = await messageCenterApi.getOverview()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  try {
    const res = await messageCenterApi.listGroups()
    groups.value = (res.items || []).map((g) => ({
      ...g,
      channels: {
        feishu: { enabled: false, chat_id: '', ...g.channels?.feishu },
        wecom: { enabled: false, webhook_url: '', ...g.channels?.wecom },
        dingtalk: { enabled: false, webhook_url: '', webhook_secret: '', ...g.channels?.dingtalk },
      },
    }))
  } catch (e) {
    ElMessage.error(String(e))
  }
}

function normalizeGroupsForSave(): MessageGroup[] {
  return groups.value.map((g) => ({
    code: g.code,
    name: g.name,
    enabled: g.enabled,
    channels: {
      feishu: {
        enabled: Boolean(g.channels?.feishu?.enabled),
        chat_id: (g.channels?.feishu?.chat_id || '').trim(),
      },
      wecom: {
        enabled: Boolean(g.channels?.wecom?.enabled),
        webhook_url: (g.channels?.wecom?.webhook_url || '').trim(),
      },
      dingtalk: {
        enabled: Boolean(g.channels?.dingtalk?.enabled),
        webhook_url: (g.channels?.dingtalk?.webhook_url || '').trim(),
        webhook_secret: (g.channels?.dingtalk?.webhook_secret || '').trim(),
      },
    },
  }))
}

async function saveGroups() {
  for (const g of groups.value) {
    const chatId = (g.channels?.feishu?.chat_id || '').trim()
    if (g.channels?.feishu?.enabled && chatId && (chatId.startsWith('http') || !chatId.startsWith('oc_'))) {
      ElMessage.warning(`「${g.name}」飞书 chat_id 应填 oc_ 开头的群 ID，不是网址。请在飞书推送页「拉取机器人所在群」获取。`)
      return
    }
    const webhook = (g.channels?.wecom?.webhook_url || '').trim()
    if (g.channels?.wecom?.enabled && webhook && !webhook.includes('qyapi.weixin.qq.com')) {
      ElMessage.warning(`「${g.name}」企微 Webhook 格式不正确`)
      return
    }
  }
  savingGroups.value = true
  try {
    const res = await messageCenterApi.saveGroups(normalizeGroupsForSave())
    groups.value = res.items
    ElMessage.success(t('messageCenter.groupsSaved'))
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    savingGroups.value = false
  }
}

async function loadRules() {
  try {
    const res = await messageCenterApi.listRules()
    rules.value = res.items
    eventCatalog.value = res.event_catalog
    targetOptions.value = res.target_options
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function loadBindings() {
  loadingBindings.value = true
  try {
    const res = await messageCenterApi.listUserBindings({
      keyword: userKeyword.value || undefined,
      unbound_only: unboundOnly.value,
    })
    bindings.value = res.items
  } finally {
    loadingBindings.value = false
  }
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    const res = await messageCenterApi.listPushLogs({
      channel: (logChannel.value as 'feishu' | 'wecom' | 'dingtalk') || undefined,
      status: logStatus.value || undefined,
      limit: 100,
    })
    pushLogs.value = res.items
  } finally {
    loadingLogs.value = false
  }
}

async function onRetry(row: PushLog) {
  try {
    await messageCenterApi.retryPushLog(row.channel, row.id)
    ElMessage.success(t('messageCenter.retryQueued'))
    loadLogs()
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function onRunMigration() {
  migrating.value = true
  try {
    const summary = (await messageCenterApi.runMigration()) as { total_migrated: number; skipped: number }
    ElMessage.success(`迁移完成：${summary.total_migrated} 租户迁移，${summary.skipped} 跳过`)
    loadOverview()
    loadGroups()
    loadRules()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    migrating.value = false
  }
}

async function loadRecipients() {
  try {
    const res = await messageCenterApi.getAlertRecipients()
    recipients.value = res.users
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function loadAllUsers() {
  loadingUsers.value = true
  try {
    const res = await messageCenterApi.getAllBindableUsers()
    allUsers.value = res.items
  } finally {
    loadingUsers.value = false
  }
}

function onAllUserSelChange(sel: AlertRecipient[]) {
  selectedAllUserIds.value = sel.map((u) => u.id)
}

function removeRecipient(uid: number) {
  recipients.value = recipients.value.filter((r) => r.id !== uid)
}

async function saveRecipients() {
  savingRecipients.value = true
  try {
    const ids = recipients.value.map((r) => r.id)
    await messageCenterApi.saveAlertRecipients(ids)
    ElMessage.success(t('messageCenter.recipientsSaved'))
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    savingRecipients.value = false
  }
}

onMounted(async () => {
  await loadOverview()
  await loadGroups()
  await loadRules()
  await loadAllUsers()
  await loadRecipients()
  loadBindings()
  loadLogs()
})
</script>
