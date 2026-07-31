<template>
  <view class="adm-page assistant-page">
    <view class="toolbar">
      <picker v-if="models.length" :range="models" range-key="display_name" @change="onModelPick">
        <view class="model-pick">{{ currentModelLabel }}</view>
      </picker>
      <text class="tool-link" @tap="showHistory = !showHistory">历史</text>
      <text class="tool-link" @tap="newChat">新对话</text>
    </view>
    <scroll-view v-if="showHistory && history.length" scroll-y class="history">
      <view v-for="h in history" :key="h.id" class="hist-row">
        <text class="hist-title" @tap="convId = h.id; showHistory = false">{{ h.title || `对话 #${h.id}` }}</text>
        <text class="hist-del" @tap="removeConv(h.id)">删</text>
      </view>
    </scroll-view>
    <scroll-view scroll-y class="msg-list">
      <view v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <text class="bubble">{{ m.content }}</text>
      </view>
      <view v-if="!messages.length" class="empty-wrap">
        <text class="empty-tip">全厂智能助手：产量、订单、齐套、CRM、采购、设备、毛利率与预警</text>
        <view class="quick-chips">
          <text v-for="q in quickQuestions" :key="q" class="chip" @tap="askQuick(q)">{{ q }}</text>
        </view>
      </view>
    </scroll-view>
    <view class="input-bar">
      <textarea v-model="input" class="input" placeholder="输入问题..." :disabled="sending" />
      <button class="send" :loading="sending" @tap="send">发送</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { aiAdminApi } from '@/api/admin/ai'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'

const auth = useAuthStore()
const focusPlanId = ref<number | undefined>()
const quickQuestions = [
  '今天产量和良率怎么样？',
  '今天毛利率多少？本月毛利情况？',
  '有哪些待审核订单？物料缺什么？',
  'CRM 有哪些商机要跟进？',
  '采购待收货情况？本月采购额？',
  '设备保养逾期或点检风险？',
]
const input = ref('')
const sending = ref(false)
const convId = ref<number | undefined>()
const messages = ref<Array<{ role: string; content: string }>>([])
const models = ref<Array<{ code: string; display_name: string; is_default: boolean }>>([])
const modelCode = ref('')
const history = ref<Array<{ id: number; title: string | null }>>([])
const showHistory = ref(false)

const currentModelLabel = computed(() => {
  const m = models.value.find((x) => x.code === modelCode.value)
  return m?.display_name || '选择模型'
})

onLoad((q) => {
  const pid = Number(q?.planId || q?.plan_id || 0)
  if (pid > 0) focusPlanId.value = pid
})

onMounted(async () => {
  try {
    const res = await aiAdminApi.listModels()
    models.value = res.items || []
    const def = models.value.find((m) => m.is_default)
    modelCode.value = def?.code || models.value[0]?.code || ''
  } catch {
    models.value = []
  }
  await loadHistory()
})

async function loadHistory() {
  try {
    const res = await aiAdminApi.listConversations('boss_qa')
    history.value = res.items || []
  } catch {
    history.value = []
  }
}

function onModelPick(e: { detail: { value: string } }) {
  const idx = Number(e.detail.value)
  if (models.value[idx]) modelCode.value = models.value[idx].code
}

function newChat() {
  convId.value = undefined
  messages.value = []
}

async function removeConv(id: number) {
  try {
    await aiAdminApi.deleteConversation(id)
    if (convId.value === id) newChat()
    await loadHistory()
    uni.showToast({ title: '已删除', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '删除失败', icon: 'none' })
  }
}

function askQuick(q: string) {
  input.value = q
  void send()
}

async function send() {
  if (!auth.hasPermission(PermissionCode.AI_USE)) {
    uni.showToast({ title: '无 AI 使用权限', icon: 'none' })
    return
  }
  const msg = input.value.trim()
  if (!msg) return
  messages.value.push({ role: 'user', content: msg })
  input.value = ''
  sending.value = true
  try {
    const res = await aiAdminApi.chat({
      message: msg,
      conversation_id: convId.value,
      model_code: modelCode.value || undefined,
      context_id: focusPlanId.value,
    })
    convId.value = res.conversation_id
    messages.value.push({ role: 'assistant', content: res.reply })
    await loadHistory()
  } catch (e: unknown) {
    messages.value.pop()
    uni.showToast({ title: (e as Error).message || 'AI 暂不可用', icon: 'none' })
  } finally {
    sending.value = false
  }
}
</script>

<style scoped lang="scss">
.assistant-page { display: flex; flex-direction: column; height: 100vh; background: #f4f6f9; }
.toolbar {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 16rpx 24rpx;
  background: #fff;
  border-bottom: 1rpx solid #eee;
}
.model-pick { font-size: 24rpx; color: #4338ca; max-width: 280rpx; overflow: hidden; text-overflow: ellipsis; }
.tool-link { font-size: 24rpx; color: #64748b; }
.history { max-height: 200rpx; background: #fff; padding: 8rpx 24rpx; border-bottom: 1rpx solid #f1f5f9; }
.hist-row { display: flex; justify-content: space-between; padding: 12rpx 0; border-bottom: 1rpx solid #f8fafc; }
.hist-title { flex: 1; font-size: 24rpx; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hist-del { font-size: 22rpx; color: #ef4444; margin-left: 16rpx; }
.msg-list { flex: 1; padding: 24rpx; box-sizing: border-box; }
.msg { margin-bottom: 20rpx; }
.msg.user { text-align: right; }
.bubble {
  display: inline-block;
  max-width: 85%;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  font-size: 28rpx;
  line-height: 1.5;
  white-space: pre-wrap;
}
.msg.user .bubble { background: #2563eb; color: #fff; }
.msg.assistant .bubble { background: #fff; color: #303133; }
.empty-wrap { padding: 40rpx 16rpx; }
.empty-tip { display: block; text-align: center; color: #64748b; font-size: 26rpx; line-height: 1.6; }
.quick-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-top: 28rpx; justify-content: center; }
.chip {
  padding: 12rpx 20rpx;
  background: #fff;
  border: 1rpx solid #e2e8f0;
  border-radius: 999rpx;
  font-size: 24rpx;
  color: #4338ca;
}
.input-bar {
  display: flex;
  gap: 16rpx;
  padding: 16rpx 24rpx calc(16rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid #eee;
}
.input {
  flex: 1;
  min-height: 72rpx;
  max-height: 160rpx;
  padding: 12rpx 16rpx;
  border: 1px solid #e4e7ed;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.send {
  align-self: flex-end;
  background: #2563eb;
  color: #fff;
  font-size: 28rpx;
  padding: 0 32rpx;
  line-height: 72rpx;
  border-radius: 12rpx;
}
</style>
