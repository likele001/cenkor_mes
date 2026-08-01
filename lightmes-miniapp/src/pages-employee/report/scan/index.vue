<template>
  <view class="emp-page">
    <!-- 未确认任务：扫码入口 -->
    <view v-if="!confirmed" class="emp-card emp-card--brand scan-entry">
      <view class="scan-icon-wrap">
        <view class="scan-icon">⌘</view>
      </view>
      <text class="scan-title">扫码识别任务</text>
      <text class="scan-hint">对准任务二维码快速报工</text>
      <button class="emp-btn-primary scan-btn" @tap="scan">立即扫码</button>
      <view class="divider"><text class="divider-text">或手动输入</text></view>
      <input v-model="taskCode" class="input" placeholder="输入任务码" confirm-type="go" @confirm="loadTask" />
      <button class="emp-btn-outline" @tap="loadTask">确认</button>
    </view>

    <!-- 已确认任务：报工表单 -->
    <template v-else>
      <view class="emp-card emp-card--striped strip-info info-card">
        <view class="detail-head">
          <text class="title">{{ taskTitle }}</text>
        </view>
        <view class="emp-kv-grid">
          <view class="emp-kv"><text class="k">订单号</text><text class="v">{{ orderLabel }}</text></view>
          <view class="emp-kv"><text class="k">工序</text><text class="v">{{ task?.process?.name || '—' }}</text></view>
          <view class="emp-kv"><text class="k">分配</text><text class="v">{{ task?.assigned_qty ?? 0 }}</text></view>
          <view class="emp-kv"><text class="k">已报</text><text class="v reported">{{ task?.reported_qty ?? 0 }}</text></view>
          <view class="emp-kv"><text class="k">剩余</text><text class="v highlight">{{ task?.remaining_qty ?? 0 }}</text></view>
        </view>
      </view>

      <view class="emp-card form-card">
        <text class="emp-section-title">报工数量</text>
        <view class="qty-row">
          <text class="qty-label">良品</text>
          <BigStepper v-model="goodQty" />
        </view>
        <view class="qty-row">
          <text class="qty-label">不良</text>
          <BigStepper v-model="badQty" />
        </view>
        <textarea v-model="remark" class="remark" placeholder="备注（可选）" maxlength="500" />
        <button class="emp-btn-outline media-btn" @tap="pickMedia">📷 添加照片/视频</button>
        <text v-if="uploadCount" class="hint">已选 {{ uploadCount }} 个附件</text>
        <button v-if="uploadCount" class="emp-btn-outline ai-btn" :loading="aiCounting" @tap="handleAiCount">
          ✨ AI 拍照计数
        </button>
        <button class="emp-btn-outline voice-btn" :loading="voiceParsing" @tap="handleVoiceInput">
          🎤 语音输入
        </button>
        <button class="emp-btn-primary submit-btn" :loading="submitting" @tap="submit">提交报工</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import BigStepper from '@/components/employee-ui/BigStepper.vue'
import { getTaskDetail, submitReport, type H5Task } from '@/api/h5/tasks'
import { photoAiCount, voiceParseReport, attachmentIdToUrl } from '@/api/h5/ai'
import { parseTaskCodeFromScan } from '@/utils/parseTaskCode'
import { taskOrderLabel, taskSkuTitle } from '@/utils/taskDisplay'
import { useUpload } from '@/composables/useUpload'

const taskCode = ref('')
const task = ref<H5Task | null>(null)
const confirmed = ref(false)
const goodQty = ref(0)
const badQty = ref(0)
const remark = ref('')
const submitting = ref(false)
const aiCounting = ref(false)
const voiceParsing = ref(false)
const { pickAndUpload, attachmentIdsStr, attachmentIds } = useUpload()
const uploadCount = ref(0)

const taskTitle = computed(() => (task.value ? taskSkuTitle(task.value) : taskCode.value))
const orderLabel = computed(() => (task.value ? taskOrderLabel(task.value) : '—'))

onLoad((q) => {
  if (q?.task_code) {
    taskCode.value = String(q.task_code)
    loadTask()
  }
})

async function scan() {
  try {
    const res = await uni.scanCode({})
    const code = parseTaskCodeFromScan(res.result)
    if (!code) {
      uni.showToast({ title: '无法识别', icon: 'none' })
      return
    }
    taskCode.value = code
    uni.vibrateShort({})
    loadTask()
  } catch { /* cancel */ }
}

async function loadTask() {
  if (!taskCode.value.trim()) return
  try {
    const t = await getTaskDetail(taskCode.value.trim())
    if (t.use_unit_report) {
      uni.redirectTo({ url: `/pages-employee/report/unit/index?task_code=${encodeURIComponent(t.task_code)}` })
      return
    }
    task.value = t
    confirmed.value = true
  } catch {
    uni.showToast({ title: '任务不存在', icon: 'none' })
  }
}

async function pickMedia() {
  try {
    await pickAndUpload()
    uploadCount.value = attachmentIds.value.length
  } catch { /* error handled in useUpload */ }
}

async function handleAiCount() {
  if (!task.value?.id) { uni.showToast({ title: '请先加载任务', icon: 'none' }); return }
  if (!attachmentIds.value.length) { uni.showToast({ title: '请先上传照片', icon: 'none' }); return }
  aiCounting.value = true
  try {
    const image_urls = attachmentIds.value.map((id) => attachmentIdToUrl(id))
    const res = await photoAiCount({ image_urls, task_id: task.value.id })
    if (!res.ok) { uni.showToast({ title: res.error || 'AI 计数不可用', icon: 'none' }); return }
    const cur = Number(res.count || 0)
    if (cur <= 0) { uni.showToast({ title: 'AI 未识别到零件', icon: 'none' }); return }
    goodQty.value = cur
    uni.showModal({ title: 'AI 计数完成', content: `识别 ${res.image_count} 张照片，共 ${cur} 件。${res.note || ''}`, showCancel: false })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || 'AI 计数失败', icon: 'none' })
  } finally {
    aiCounting.value = false
  }
}

async function handleVoiceInput() {
  voiceParsing.value = true
  try {
    const { content } = await new Promise<{ content: string }>((resolve, reject) => {
      uni.showModal({
        title: '语音输入', content: '请用系统输入法的语音键说话', editable: true,
        placeholderText: '说：10个良品，2个不良...',
        success: (r) => { if (r.confirm) resolve({ content: r.content?.trim() || '' }); else reject(new Error('cancel')) },
        fail: () => reject(new Error('cancel')),
      })
    })
    if (!content) { uni.showToast({ title: '未输入内容', icon: 'none' }); return }
    const res = await voiceParseReport({ text: content, task_id: task.value?.id })
    if (res.good_qty != null) goodQty.value = res.good_qty
    if (res.bad_qty != null) badQty.value = res.bad_qty
    if (res.remark && !remark.value.trim()) remark.value = res.remark
    uni.showModal({
      title: '语音解析完成',
      content: res.summary || `良品 ${res.good_qty ?? '—'}，不良 ${res.bad_qty ?? '—'}${res.remark ? `\n备注：${res.remark}` : ''}`,
      showCancel: false,
    })
  } catch (e) {
    if ((e as Error).message !== 'cancel') uni.showToast({ title: (e as Error).message || '语音解析失败', icon: 'none' })
  } finally {
    voiceParsing.value = false
  }
}

async function submit() {
  if (goodQty.value + badQty.value <= 0) { uni.showToast({ title: '请填写数量', icon: 'none' }); return }
  submitting.value = true
  try {
    await submitReport({
      task_code: taskCode.value.trim(), good_qty: goodQty.value, bad_qty: badQty.value,
      remark: remark.value || undefined, attachment_ids: attachmentIdsStr() || undefined,
    })
    uni.vibrateShort({})
    uni.showToast({ title: '报工成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 800)
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

onUnload(() => {
  // 保存草稿（仅在有实际数据时）
  if ((goodQty.value || badQty.value || remark.value.trim() || attachmentIds.value.length) && taskCode.value) {
    uni.setStorageSync('report_scan_draft_' + taskCode.value, {
      goodQty: goodQty.value, badQty: badQty.value, remark: remark.value,
      attachmentIds: attachmentIds.value, timestamp: Date.now(),
    })
  }
})
</script>

<style scoped lang="scss">
// 扫码入口
.scan-entry {
  padding: $space-7 $space-6;
  border-radius: $radius-xl;
  text-align: center;
}
.scan-icon-wrap {
  width: 120rpx;
  height: 120rpx;
  margin: 0 auto $space-4;
}
.scan-icon {
  width: 100%;
  height: 100%;
  border-radius: $radius-xl;
  background: rgba(255, 255, 255, 0.18);
  border: 2rpx solid rgba(255, 255, 255, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 56rpx;
  font-weight: $fw-bold;
  color: #fff;
}
.scan-title {
  display: block;
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
}
.scan-hint {
  margin-top: $space-1;
  font-size: $text-sm;
  color: rgba(255, 255, 255, 0.78);
  display: block;
  margin-bottom: $space-5;
}
.scan-btn {
  background: #fff;
  color: $brand-600;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.12);
}
.divider {
  display: flex;
  align-items: center;
  margin: $space-5 0;
}
.divider::before, .divider::after {
  content: '';
  flex: 1;
  height: 1rpx;
  background: rgba(255, 255, 255, 0.25);
}
.divider-text {
  padding: 0 $space-3;
  font-size: $text-xs;
  color: rgba(255, 255, 255, 0.72);
}
.input {
  background: rgba(255, 255, 255, 0.15);
  border: 1rpx solid rgba(255, 255, 255, 0.25);
  padding: 22rpx 24rpx;
  border-radius: $radius-md;
  margin-bottom: $space-3;
  font-size: $text-md;
  color: #fff;
  &::placeholder { color: rgba(255, 255, 255, 0.6); }
}

// 信息卡
.info-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.detail-head {
  margin-bottom: $space-4;
}
.title {
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $slate-800;
  display: block;
}
.reported { color: $brand-600; }
.highlight { color: $warn-deep; font-weight: $fw-bold; }

// 表单卡
.form-card {
  padding: $space-5;
}
.qty-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-3 0;
}
.qty-label {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-700;
}
.remark {
  width: 100%;
  min-height: 120rpx;
  padding: $space-3 $space-4;
  margin: $space-3 0;
  background: $slate-50;
  border-radius: $radius-md;
  border: 1rpx solid $slate-200;
  font-size: $text-base;
  box-sizing: border-box;
}
.media-btn, .ai-btn, .voice-btn {
  width: 100%;
  margin-bottom: $space-3;
}
.ai-btn {
  border-color: $warn;
  color: $warn-deep;
  &:active { background: $warn-bg; }
}
.voice-btn {
  border-color: #8b5cf6;
  color: #7c3aed;
  &:active { background: #ede9fe; }
}
.hint {
  font-size: $text-xs;
  color: $slate-500;
  display: block;
  margin-bottom: $space-2;
}
.submit-btn {
  width: 100%;
  margin-top: $space-3;
}
</style>
