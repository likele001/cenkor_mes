<template>
  <view class="adm-page">
    <view class="section">
      <text class="section-title">微信小程序配置</text>
      <view class="field"><text class="label">AppID</text><input v-model="form.app_id" class="input" placeholder="wx..." /></view>
      <view class="field">
        <text class="label">AppSecret</text>
        <input v-model="form.app_secret" class="input" password :placeholder="masked || '留空则不修改'" />
      </view>
      <view v-if="configured" class="hint">当前已配置 · Secret: {{ masked || '已设置' }}</view>
      <button class="btn primary" :loading="saving" @tap="saveWx">保存微信配置</button>
    </view>

    <view v-if="canAiGateway" class="section">
      <text class="section-title">AI 网关（Key）</text>
      <text class="hint">启用后本企业 AI 优先使用下方 Key；未启用则走平台总控。</text>
      <view class="field row-between">
        <text class="label">启用覆盖</text>
        <switch :checked="aiGw.enabled" @change="onAiEnabled" color="#4338ca" />
      </view>
      <view class="field"><text class="label">Base URL</text><input v-model="aiGw.base_url" class="input" placeholder="https://api.openai.com/v1" /></view>
      <view class="field">
        <text class="label">API Key</text>
        <input v-model="aiGw.api_key" class="input" password :placeholder="aiGw.api_key_configured ? '留空不修改' : 'sk-...'" />
        <text v-if="aiGw.api_key_configured" class="hint">已配置，留空则不修改</text>
      </view>
      <view class="field"><text class="label">Model ID</text><input v-model="aiGw.model_id" class="input" placeholder="留空用平台默认" /></view>
      <view class="field inline">
        <text class="label">超时(秒)</text>
        <input v-model.number="aiGw.timeout_seconds" type="number" class="input short" />
      </view>
      <button class="btn primary" :loading="aiSaving" @tap="saveAiGw">保存 AI 网关</button>
      <view class="field mt">
        <text class="label">工厂助手提示词</text>
        <textarea v-model="aiPrompt" class="input area" maxlength="2000" placeholder="可选，追加到系统 prompt" />
      </view>
      <button class="btn ghost" :loading="aiPromptSaving" @tap="saveAiPrompt">保存提示词</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { systemAdminApi } from '@/api/admin/system'
import { aiAdminApi } from '@/api/admin/ai'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'

const { requirePermission } = usePermission()
const auth = useAuthStore()
const saving = ref(false)
const aiSaving = ref(false)
const aiPromptSaving = ref(false)
const aiPrompt = ref('')
const configured = ref(false)
const masked = ref('')
const form = reactive({ app_id: '', app_secret: '' })
const aiGw = reactive({
  enabled: false,
  base_url: '',
  api_key: '',
  api_key_configured: false,
  model_id: '',
  timeout_seconds: 120,
})

const canAiGateway = computed(
  () => auth.hasPermission(PermissionCode.AI_USE) && auth.hasPermission(PermissionCode.SETTING_MANAGE),
)

onShow(async () => {
  if (!requirePermission('setting.manage')) return
  try {
    const r = await systemAdminApi.getWechatMiniapp()
    form.app_id = r.app_id || ''
    masked.value = r.app_secret_masked || ''
    configured.value = !!(r as { app_secret_configured?: boolean }).app_secret_configured || !!r.configured
  } catch {
    configured.value = false
  }
  if (canAiGateway.value) {
    try {
      const g = await aiAdminApi.getGatewaySettings()
      aiGw.enabled = g.enabled
      aiGw.base_url = g.base_url || ''
      aiGw.api_key_configured = g.api_key_configured
      aiGw.api_key = ''
      aiGw.model_id = g.model_id || ''
      aiGw.timeout_seconds = g.timeout_seconds || 120
      const p = await aiAdminApi.getPromptSettings()
      aiPrompt.value = p.prompt || ''
    } catch {
      /* ignore */
    }
  }
})

function onAiEnabled(e: { detail: { value: boolean } }) {
  aiGw.enabled = e.detail.value
}

async function saveWx() {
  saving.value = true
  try {
    await systemAdminApi.saveWechatMiniapp({
      app_id: form.app_id.trim(),
      app_secret: form.app_secret.trim() || null,
    })
    uni.showToast({ title: '保存成功', icon: 'success' })
    form.app_secret = ''
    const r = await systemAdminApi.getWechatMiniapp()
    masked.value = r.app_secret_masked || ''
    configured.value = !!(r as { app_secret_configured?: boolean }).app_secret_configured || !!r.configured
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function saveAiGw() {
  if (aiGw.enabled && !aiGw.base_url.trim()) {
    uni.showToast({ title: '启用时请填写 Base URL', icon: 'none' })
    return
  }
  aiSaving.value = true
  try {
    const data: Record<string, unknown> = {
      enabled: aiGw.enabled,
      base_url: aiGw.base_url.trim(),
      model_id: aiGw.model_id.trim(),
      timeout_seconds: aiGw.timeout_seconds,
    }
    if (aiGw.api_key.trim()) data.api_key = aiGw.api_key.trim()
    await aiAdminApi.saveGatewaySettings(data)
    uni.showToast({ title: 'AI 网关已保存', icon: 'success' })
    aiGw.api_key = ''
    const g = await aiAdminApi.getGatewaySettings()
    aiGw.api_key_configured = g.api_key_configured
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    aiSaving.value = false
  }
}

async function saveAiPrompt() {
  aiPromptSaving.value = true
  try {
    await aiAdminApi.savePromptSettings({ prompt: aiPrompt.value })
    uni.showToast({ title: '提示词已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    aiPromptSaving.value = false
  }
}
</script>

<style scoped lang="scss">
.section { background: #fff; border-radius: 16rpx; padding: 28rpx; margin-bottom: 24rpx; }
.section-title { display: block; font-size: 32rpx; font-weight: 700; margin-bottom: 12rpx; }
.field { margin-bottom: 20rpx; }
.field.mt { margin-top: 24rpx; }
.row-between { display: flex; justify-content: space-between; align-items: center; }
.inline { display: flex; align-items: center; gap: 16rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; width: 100%; box-sizing: border-box; }
.input.area { min-height: 160rpx; }
.input.short { flex: 1; }
.hint { display: block; font-size: 24rpx; color: #64748b; margin-bottom: 12rpx; line-height: 1.4; }
.btn { border-radius: 12rpx; font-size: 28rpx; margin-top: 8rpx; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.ghost { background: #f1f5f9; color: #475569; }
</style>
