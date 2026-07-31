<template>
  <view class="emp-page">
    <view v-if="!confirmed" class="emp-card">
      <button class="emp-btn-primary" @tap="scan">扫码识别任务</button>
      <input v-model="taskCode" class="input" placeholder="或输入任务码" />
      <button class="emp-btn-outline" @tap="loadTask">确认</button>
    </view>

    <template v-else>
      <view class="emp-card info-card">
        <text class="title">{{ taskTitle }}</text>
        <view class="emp-kv-grid">
          <view class="emp-kv">
            <text class="k">订单号</text>
            <text class="v">{{ orderLabel }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">工序</text>
            <text class="v">{{ task?.process?.name || '—' }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">分配数量</text>
            <text class="v">{{ task?.assigned_qty ?? 0 }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">已报数量</text>
            <text class="v">{{ task?.reported_qty ?? 0 }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">剩余数量</text>
            <text class="v">{{ task?.remaining_qty ?? 0 }}</text>
          </view>
        </view>
      </view>

      <view class="emp-card">
        <text class="section">报工数量</text>
        <view class="row">
          <text>良品</text>
          <BigStepper v-model="goodQty" />
        </view>
        <view class="row">
          <text>不良</text>
          <BigStepper v-model="badQty" />
        </view>
        <input v-model="remark" class="input" placeholder="备注（可选）" />
        <button class="emp-btn-outline" :loading="submitting" @tap="pickMedia">添加照片/视频</button>
        <text v-if="uploadCount" class="hint">已选 {{ uploadCount }} 个附件</text>
        <button v-if="uploadCount" class="emp-btn-outline ai-count" :loading="aiCounting" @tap="handleAiCount">
          AI 拍照计数
        </button>
        <button class="emp-btn-outline voice-btn" :loading="voiceParsing" @tap="handleVoiceInput">
          语音输入
        </button>
        <button class="emp-btn-primary" :loading="submitting" @tap="submit">提交报工</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { onUnload } from '@dcloudio/uni-app'
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
  } catch {
    /* cancel */
  }
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
  } catch {
    // 错误已在 useUpload 中提示
  }
}

async function handleAiCount() {
  if (!task.value?.id) {
    uni.showToast({ title: '请先加载任务', icon: 'none' })
    return
  }
  if (!attachmentIds.value.length) {
    uni.showToast({ title: '请先上传照片', icon: 'none' })
    return
  }
  aiCounting.value = true
  try {
    const image_urls = attachmentIds.value.map((id) => attachmentIdToUrl(id))
    const res = await photoAiCount({ image_urls, task_id: task.value.id })
    if (!res.ok) {
      uni.showToast({ title: res.error || 'AI 计数不可用', icon: 'none' })
      return
    }
    const cur = Number(res.count || 0)
    if (cur <= 0) {
      uni.showToast({ title: 'AI 未识别到零件', icon: 'none' })
      return
    }
    goodQty.value = cur
    uni.showModal({
      title: 'AI 计数完成',
      content: `识别 ${res.image_count} 张照片，共 ${cur} 件。${res.note || ''}`,
      showCancel: false,
    })
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
        title: '语音输入',
        content: '请用系统输入法的语音键说话',
        editable: true,
        placeholderText: '说：10个良品，2个不良...',
        success: (r) => {
          if (r.confirm) resolve({ content: r.content?.trim() || '' })
          else reject(new Error('cancel'))
        },
        fail: () => reject(new Error('cancel')),
      })
    })
    if (!content) {
      uni.showToast({ title: '未输入内容', icon: 'none' })
      return
    }
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
    if ((e as Error).message !== 'cancel') {
      uni.showToast({ title: (e as Error).message || '语音解析失败', icon: 'none' })
    }
  } finally {
    voiceParsing.value = false
  }
}

async function submit() {
  if (goodQty.value + badQty.value <= 0) {
    uni.showToast({ title: '请填写数量', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    await submitReport({
      task_code: taskCode.value.trim(),
      good_qty: goodQty.value,
      bad_qty: badQty.value,
      remark: remark.value || undefined,
      attachment_ids: attachmentIdsStr() || undefined,
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

function hasDraft() {
  return !!(reportQty.value || attachmentIds.value.length || remark.value.trim())
}

onUnload(() => {
  if (hasDraft() && taskCode.value) {
    uni.setStorageSync('report_scan_draft_' + taskCode.value, {
      reportQty: reportQty.value,
      resultType: resultType.value,
      attachmentIds: attachmentIds.value,
      remark: remark.value,
      timestamp: Date.now(),
    })
  }
})

</script>

<style scoped lang="scss">
.input {
  background: #f8fafc;
  padding: 20rpx;
  margin: 16rpx 0;
  border-radius: 12rpx;
  border: 1rpx solid #e2e8f0;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20rpx 0;
}
.title {
  font-size: 32rpx;
  font-weight: 700;
  display: block;
  margin-bottom: 20rpx;
  color: #1e293b;
}
.section {
  font-size: 28rpx;
  font-weight: 600;
  display: block;
  margin-bottom: 16rpx;
}
.hint {
  font-size: 24rpx;
  color: #64748b;
  display: block;
  margin: 8rpx 0 16rpx;
}
.emp-btn-outline {
  margin-bottom: 16rpx;
}
.ai-count {
  border-color: #f59e0b;
  color: #b45309;
}
.voice-btn {
  border-color: #8b5cf6;
  color: #7c3aed;
}
</style>
