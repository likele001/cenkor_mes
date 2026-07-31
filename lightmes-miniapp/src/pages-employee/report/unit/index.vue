<template>
  <view class="emp-page">
    <view v-if="!taskCode" class="emp-card">
      <button class="emp-btn-primary" @tap="scan">扫码识别任务</button>
      <input v-model="manualCode" class="input" placeholder="或输入任务码" @confirm="setCode" />
      <button class="emp-btn-outline" @tap="setCode">确认</button>
    </view>

    <template v-else>
      <view class="emp-card">
        <text class="title">{{ taskTitle }}</text>
        <view class="emp-kv-grid">
          <view class="emp-kv">
            <text class="k">订单号</text>
            <text class="v">{{ orderLabel }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">工序</text>
            <text class="v">{{ taskInfo?.process?.name || '—' }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">分配数量</text>
            <text class="v">{{ assignedQty }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">已报数量</text>
            <text class="v">{{ reportedQty }}</text>
          </view>
          <view class="emp-kv">
            <text class="k">剩余数量</text>
            <text class="v">{{ remainingQty }}</text>
          </view>
        </view>
      </view>

      <view class="emp-card">
        <text class="section">逐件报工</text>
        <view v-if="poolMode" class="pool-hint">
          <text>可领 {{ flow?.pool_available ?? 0 }} / 共 {{ flow?.pool_total ?? 0 }} 套</text>
          <text class="sub">谁有空谁领下一套，提交后自动绑定成品码</text>
        </view>
        <picker v-else :range="draftUnits" range-key="label" @change="onPick">
          <view class="picker">选择件次: {{ selectedSeq || '请选择' }}</view>
        </picker>
        <view class="row">
          <button :class="{ active: resultType === 'good' }" @tap="resultType = 'good'">合格</button>
          <button :class="{ active: resultType === 'bad' }" @tap="resultType = 'bad'">不良</button>
        </view>
        <textarea v-model="remark" class="remark" placeholder="备注（可选）" maxlength="500" />
        <button class="emp-btn-outline" @tap="pickMedia">现场拍照</button>
        <view v-if="attachmentIds.length" class="preview-grid">
          <image
            v-for="id in attachmentIds"
            :key="id"
            :src="attachmentUrls[id] || ''"
            class="preview-img"
            mode="aspectFill"
            @tap="previewImage(id)"
          />
        </view>
        <text v-if="uploadCount" class="hint">附件 {{ uploadCount }}</text>
        <button v-if="canAiCheck" class="emp-btn-outline ai-check" :loading="aiChecking" @tap="handleAiCheck">
          AI 检查一下
        </button>
        <button
          v-if="resultType === 'bad' && uploadCount"
          class="emp-btn-outline ai-defect"
          :loading="aiClassifying"
          @tap="handleAiClassify"
        >
          AI 识别缺陷类型
        </button>
        <button class="emp-btn-outline voice-btn" :loading="voiceParsing" @tap="handleVoiceInput">
          语音输入
        </button>
        <button class="emp-btn-primary" :loading="submitting" @tap="submit">
          {{ poolMode ? '领取下一套并提交' : '提交逐件报工' }}
        </button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { onUnload } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { getTaskUnits, submitReportUnit } from '@/api/h5/reportUnits'
import { reportAiCheck, defectAiClassify, voiceParseReport, attachmentIdToUrl } from '@/api/h5/ai'
import { getTaskDetail, type H5Task } from '@/api/h5/tasks'
import { parseTaskCodeFromScan } from '@/utils/parseTaskCode'
import { taskOrderLabel, taskSkuTitle } from '@/utils/taskDisplay'
import { useUpload } from '@/composables/useUpload'
import { usePermission } from '@/composables/usePermission'
import { PermissionCode } from '@/constants/permissions'

const { hasPermission } = usePermission()

const taskCode = ref('')
const manualCode = ref('')
const taskInfo = ref<H5Task | null>(null)
const assignedQty = ref(0)
const reportedQty = ref(0)
const remainingQty = ref(0)
const units = ref<{ unit_seq: number; status: string }[]>([])
const flow = ref<{ piece_pool_enabled?: boolean; pool_available?: number; pool_total?: number } | null>(null)
const selectedSeq = ref<number | null>(null)
const resultType = ref<'good' | 'bad'>('good')
const remark = ref('')
const submitting = ref(false)
const aiChecking = ref(false)
const aiClassifying = ref(false)
const voiceParsing = ref(false)
const { pickAndUpload, attachmentIdsStr, attachmentIds, attachmentUrls, clearAttachments } = useUpload()
const uploadCount = ref(0)

const canAiCheck = computed(() => hasPermission(PermissionCode.AI_REPORT_ASSIST))

const poolMode = computed(() => flow.value?.piece_pool_enabled === true)
const taskTitle = computed(() => (taskInfo.value ? taskSkuTitle(taskInfo.value) : taskCode.value))
const orderLabel = computed(() => (taskInfo.value ? taskOrderLabel(taskInfo.value) : '—'))

const draftUnits = computed(() =>
  units.value.filter((u) => u.status === 'draft').map((u) => ({ ...u, label: `第 ${u.unit_seq} 件` })),
)

onLoad((q) => {
  if (q?.task_code) {
    taskCode.value = String(q.task_code)
    loadUnits()
  }
})

async function scan() {
  const res = await uni.scanCode({})
  const code = parseTaskCodeFromScan(res.result)
  if (code) {
    taskCode.value = code
    loadUnits()
  }
}

function setCode() {
  taskCode.value = manualCode.value.trim()
  if (taskCode.value) loadUnits()
}

async function loadUnits() {
  try {
    const [detail, r] = await Promise.all([
      getTaskDetail(taskCode.value),
      getTaskUnits(taskCode.value),
    ])
    taskInfo.value = detail
    units.value = r.items || []
    flow.value = r.flow ?? null
    assignedQty.value = r.assigned_qty ?? 0
    reportedQty.value = r.reported_qty ?? 0
    remainingQty.value = r.remaining_qty ?? 0
    if (!poolMode.value) {
      const d = draftUnits.value[0]
      if (d) selectedSeq.value = d.unit_seq
    }
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function onPick(e: { detail: { value: string } }) {
  const idx = Number(e.detail.value)
  selectedSeq.value = draftUnits.value[idx]?.unit_seq ?? null
}

async function pickMedia() {
  try {
    await pickAndUpload(1)
    uploadCount.value = attachmentIds.value.length
  } catch {
    // 错误已在 useUpload 中提示
  }
}

function previewImage(currentId: number) {
  const urls = attachmentIds.value.map((id) => attachmentUrls.value[id]).filter(Boolean)
  const current = urls.findIndex((u) => u === attachmentUrls.value[currentId])
  uni.previewImage({
    urls,
    current: current >= 0 ? current : 0,
  })
}

async function handleAiCheck() {
  if (!taskInfo.value?.id) {
    uni.showToast({ title: '请先加载任务', icon: 'none' })
    return
  }
  aiChecking.value = true
  try {
    const res = await reportAiCheck({
      task_id: taskInfo.value.id,
      result_type: resultType.value,
      remark: remark.value.trim() || undefined,
    })
    if (res.suggest_remark && !remark.value.trim()) {
      remark.value = res.suggest_remark
    }
    const msg = (res.hints?.length ? res.hints.join('\n') : res.reply) || '无特别建议'
    uni.showModal({
      title: res.ok === false ? '建议修改' : 'AI 检查',
      content: msg,
      showCancel: false,
    })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || 'AI 暂不可用', icon: 'none' })
  } finally {
    aiChecking.value = false
  }
}

async function handleAiClassify() {
  if (!taskInfo.value?.id) {
    uni.showToast({ title: '请先加载任务', icon: 'none' })
    return
  }
  if (!attachmentIds.value.length) {
    uni.showToast({ title: '请先上传不良品照片', icon: 'none' })
    return
  }
  aiClassifying.value = true
  try {
    const image_urls = attachmentIds.value.map((id) => attachmentIdToUrl(id))
    const res = await defectAiClassify({
      image_urls,
      task_id: taskInfo.value.id,
      remark: remark.value.trim() || undefined,
    })
    if (!res.ok) {
      uni.showToast({ title: res.error || 'AI 分类不可用', icon: 'none' })
      return
    }
    let msg = `识别 ${res.image_count} 张照片`
    if (res.defect_name) msg += `\n缺陷类型：${res.defect_name}`
    if (res.severity) msg += `\n严重程度：${res.severity}`
    if (res.description) msg += `\n说明：${res.description}`
    if (res.confidence) msg += `\n可信度：${res.confidence}`
    uni.showModal({ title: 'AI 缺陷分类', content: msg, showCancel: false })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || 'AI 分类失败', icon: 'none' })
  } finally {
    aiClassifying.value = false
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
        placeholderText: '说：1个良品...',
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
    const res = await voiceParseReport({ text: content, task_id: taskInfo.value?.id })
    if (res.remark && !remark.value.trim()) remark.value = res.remark
    // 根据解析结果自动选择合格/不良
    if (res.result_type === 'bad') resultType.value = 'bad'
    else if (res.result_type === 'good') resultType.value = 'good'
    const msg = res.summary || content
    uni.showModal({
      title: '语音解析完成',
      content: `${msg}${res.remark ? `\n备注：${res.remark}` : ''}${res.defect_keywords?.length ? `\n缺陷：${res.defect_keywords.join('、')}` : ''}`,
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
  if (!poolMode.value && !selectedSeq.value) {
    uni.showToast({ title: '请选择件次', icon: 'none' })
    return
  }
  if (!attachmentIdsStr()) {
    uni.showToast({ title: '请现场拍照', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    await submitReportUnit({
      task_code: taskCode.value,
      unit_seq: poolMode.value ? undefined : selectedSeq.value ?? undefined,
      result_type: resultType.value,
      attachment_ids: attachmentIdsStr(),
      remark: remark.value.trim() || undefined,
    })
    clearAttachments()
    uploadCount.value = 0
    remark.value = ''
    uni.showToast({ title: '提交成功', icon: 'success' })
    loadUnits()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function hasDraft() {
  return !!((!poolMode.value && selectedSeq.value) || attachmentIds.value.length || remark.value.trim())
}

onUnload(() => {
  if (hasDraft() && taskCode.value) {
    uni.setStorageSync('report_unit_draft_' + taskCode.value, {
      selectedSeq: selectedSeq.value,
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
  margin-top: 16rpx;
  border-radius: 12rpx;
  border: 1rpx solid #e2e8f0;
}
.title {
  font-size: 32rpx;
  font-weight: 700;
  display: block;
  margin-bottom: 20rpx;
}
.section {
  font-size: 28rpx;
  font-weight: 600;
  display: block;
  margin-bottom: 16rpx;
}
.picker {
  padding: 24rpx;
  background: #f8fafc;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
}
.pool-hint {
  padding: 16rpx 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  color: #334155;
}
.pool-hint .sub {
  font-size: 24rpx;
  color: #64748b;
}
.row {
  display: flex;
  gap: 16rpx;
  margin: 16rpx 0;
}
.row button {
  flex: 1;
  font-size: 28rpx;
}
.row button.active {
  background: #2563eb;
  color: #fff;
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
.remark {
  width: 100%;
  min-height: 120rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
  background: #f8fafc;
  border-radius: 12rpx;
  border: 1rpx solid #e2e8f0;
  font-size: 26rpx;
  box-sizing: border-box;
}
.ai-check {
  border-color: #f59e0b;
  color: #b45309;
}
.ai-defect {
  border-color: #ef4444;
  color: #b91c1c;
}
.voice-btn {
  border-color: #8b5cf6;
  color: #7c3aed;
}
</style>
