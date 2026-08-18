<template>
  <view class="emp-page">
    <!-- 未设置任务码：扫码入口 -->
    <view v-if="!taskCode" class="emp-card emp-card--brand scan-entry">
      <view class="scan-icon-wrap"><view class="scan-icon">⌘</view></view>
      <text class="scan-title">逐件报工</text>
      <text class="scan-hint">扫码或输入任务码开始逐件报工</text>
      <button class="emp-btn-primary scan-btn" @tap="scan">立即扫码</button>
      <view class="divider"><text class="divider-text">或手动输入</text></view>
      <input v-model="manualCode" class="input" placeholder="输入任务码" confirm-type="go" @confirm="setCode" />
      <button class="emp-btn-outline" @tap="setCode">确认</button>
    </view>

    <template v-else>
      <!-- 任务信息卡 -->
      <view class="emp-card emp-card--striped strip-info info-card">
        <text class="title">{{ taskTitle }}</text>
        <view class="emp-kv-grid">
          <view class="emp-kv"><text class="k">订单号</text><text class="v">{{ orderLabel }}</text></view>
          <view class="emp-kv"><text class="k">工序</text><text class="v">{{ taskInfo?.process?.name || '—' }}</text></view>
          <view class="emp-kv"><text class="k">分配</text><text class="v">{{ assignedQty }}</text></view>
          <view class="emp-kv"><text class="k">已报</text><text class="v reported">{{ reportedQty }}</text></view>
          <view class="emp-kv"><text class="k">剩余</text><text class="v highlight">{{ remainingQty }}</text></view>
        </view>
      </view>

      <!-- 报工表单 -->
      <view class="emp-card form-card">
        <text class="emp-section-title">逐件报工</text>

        <!-- pool 模式提示 -->
        <view v-if="poolMode" class="pool-hint">
          <view class="pool-stats">
            <text class="pool-num">{{ flow?.pool_available ?? 0 }}</text>
            <text class="pool-lbl">/ {{ flow?.pool_total ?? 0 }} 可领</text>
          </view>
          <text class="pool-sub">谁有空谁领下一套，提交后自动绑定成品码</text>
        </view>
        <!-- 件次选择 -->
        <picker v-else :range="draftUnits" range-key="label" @change="onPick">
          <view class="picker-row">
            <text class="picker-label">选择件次</text>
            <text class="picker-value">{{ selectedSeq ? `第 ${selectedSeq} 件` : '请选择' }} ›</text>
          </view>
        </picker>

        <!-- 合格/不良 toggle -->
        <view class="result-toggle">
          <view class="toggle-item" :class="{ active: resultType === 'good' }" @tap="resultType = 'good'">
            <text class="toggle-icon">✓</text>
            <text class="toggle-text">合格</text>
          </view>
          <view class="toggle-item" :class="{ active: resultType === 'bad' }" @tap="resultType = 'bad'">
            <text class="toggle-icon">✗</text>
            <text class="toggle-text">不良</text>
          </view>
        </view>

        <textarea v-model="remark" class="remark" placeholder="备注（可选）" maxlength="500" />
        <button class="emp-btn-outline media-btn" @tap="pickMedia">📷 现场拍照</button>

        <!-- 附件预览 -->
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

        <button v-if="canAiCheck" class="emp-btn-outline ai-btn" :loading="aiChecking" @tap="handleAiCheck">
          ✨ AI 检查
        </button>
        <button
          v-if="resultType === 'bad' && uploadCount"
          class="emp-btn-outline defect-btn"
          :loading="aiClassifying"
          @tap="handleAiClassify"
        >
          🔍 AI 识别缺陷类型
        </button>
        <button class="emp-btn-outline voice-btn" :loading="voiceParsing" @tap="handleVoiceInput">
          🎤 语音输入
        </button>
        <button class="emp-btn-primary submit-btn" :loading="submitting" @tap="submit">
          {{ poolMode ? '领取下一套并提交' : '提交逐件报工' }}
        </button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onUnload } from '@dcloudio/uni-app'
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
    const [detail, r] = await Promise.all([getTaskDetail(taskCode.value), getTaskUnits(taskCode.value)])
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
  } catch { /* error handled in useUpload */ }
}

function previewImage(currentId: number) {
  const urls = attachmentIds.value.map((id) => attachmentUrls.value[id]).filter(Boolean)
  const current = urls.findIndex((u) => u === attachmentUrls.value[currentId])
  uni.previewImage({ urls, current: current >= 0 ? current : 0 })
}

async function handleAiCheck() {
  if (!taskInfo.value?.id) { uni.showToast({ title: '请先加载任务', icon: 'none' }); return }
  aiChecking.value = true
  try {
    const res = await reportAiCheck({
      task_id: taskInfo.value.id, result_type: resultType.value,
      remark: remark.value.trim() || undefined,
    })
    if (res.suggest_remark && !remark.value.trim()) remark.value = res.suggest_remark
    const msg = (res.hints?.length ? res.hints.join('\n') : res.reply) || '无特别建议'
    uni.showModal({ title: res.ok === false ? '建议修改' : 'AI 检查', content: msg, showCancel: false })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || 'AI 暂不可用', icon: 'none' })
  } finally {
    aiChecking.value = false
  }
}

async function handleAiClassify() {
  if (!taskInfo.value?.id) { uni.showToast({ title: '请先加载任务', icon: 'none' }); return }
  if (!attachmentIds.value.length) { uni.showToast({ title: '请先上传不良品照片', icon: 'none' }); return }
  aiClassifying.value = true
  try {
    const image_urls = attachmentIds.value.map((id) => attachmentIdToUrl(id))
    const res = await defectAiClassify({
      image_urls, task_id: taskInfo.value.id, remark: remark.value.trim() || undefined,
    })
    if (!res.ok) { uni.showToast({ title: res.error || 'AI 分类不可用', icon: 'none' }); return }
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
        title: '语音输入', content: '请用系统输入法的语音键说话', editable: true,
        placeholderText: '说：1个良品...',
        success: (r) => { if (r.confirm) resolve({ content: r.content?.trim() || '' }); else reject(new Error('cancel')) },
        fail: () => reject(new Error('cancel')),
      })
    })
    if (!content) { uni.showToast({ title: '未输入内容', icon: 'none' }); return }
    const res = await voiceParseReport({ text: content, task_id: taskInfo.value?.id })
    if (res.remark && !remark.value.trim()) remark.value = res.remark
    if (res.result_type === 'bad') resultType.value = 'bad'
    else if (res.result_type === 'good') resultType.value = 'good'
    const msg = res.summary || content
    uni.showModal({
      title: '语音解析完成',
      content: `${msg}${res.remark ? `\n备注：${res.remark}` : ''}${res.defect_keywords?.length ? `\n缺陷：${res.defect_keywords.join('、')}` : ''}`,
      showCancel: false,
    })
  } catch (e) {
    if ((e as Error).message !== 'cancel') uni.showToast({ title: (e as Error).message || '语音解析失败', icon: 'none' })
  } finally {
    voiceParsing.value = false
  }
}

async function submit() {
  if (!poolMode.value && !selectedSeq.value) { uni.showToast({ title: '请选择件次', icon: 'none' }); return }
  if (!attachmentIdsStr()) { uni.showToast({ title: '请现场拍照', icon: 'none' }); return }
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
      selectedSeq: selectedSeq.value, resultType: resultType.value,
      attachmentIds: attachmentIds.value, remark: remark.value, timestamp: Date.now(),
    })
  }
})
</script>

<style scoped lang="scss">
// 扫码入口（复用 scan 的样式）
.scan-entry {
  padding: $space-7 $space-6;
  border-radius: $radius-xl;
  text-align: center;
}
.scan-icon-wrap { width: 120rpx; height: 120rpx; margin: 0 auto $space-4; }
.scan-icon {
  width: 100%; height: 100%; border-radius: $radius-xl;
  background: rgba(255,255,255,0.18); border: 2rpx solid rgba(255,255,255,0.35);
  display: flex; align-items: center; justify-content: center;
  font-size: 56rpx; font-weight: $fw-bold; color: #fff;
}
.scan-title { display: block; font-size: $text-xl; font-weight: $fw-bold; color: #fff; }
.scan-hint { margin-top: $space-1; font-size: $text-sm; color: rgba(255,255,255,0.78); display: block; margin-bottom: $space-5; }
.scan-btn { background: #fff; color: $brand-600; box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.12); }
.divider { display: flex; align-items: center; margin: $space-5 0; }
.divider::before, .divider::after { content: ''; flex: 1; height: 1rpx; background: rgba(255,255,255,0.25); }
.divider-text { padding: 0 $space-3; font-size: $text-xs; color: rgba(255,255,255,0.72); }
.input {
  background: rgba(255,255,255,0.15); border: 1rpx solid rgba(255,255,255,0.25);
  padding: 22rpx 24rpx; border-radius: $radius-md; margin-bottom: $space-3;
  font-size: $text-md; color: #fff;
  &::placeholder { color: rgba(255,255,255,0.6); }
}

// 信息卡
.info-card { padding: $space-5; padding-left: 32rpx; }
.title { font-size: $text-lg; font-weight: $fw-bold; color: $slate-800; display: block; margin-bottom: $space-4; }
.reported { color: $brand-600; }
.highlight { color: $warn-deep; font-weight: $fw-bold; }

// 表单
.form-card { padding: $space-5; }
.pool-hint {
  background: $brand-50; border-radius: $radius-md; padding: $space-4; margin-bottom: $space-4;
  border: 1rpx solid rgba($brand-200, 0.5);
}
.pool-stats { display: flex; align-items: baseline; gap: 6rpx; }
.pool-num { font-size: $text-xl; font-weight: $fw-bold; color: $brand-600; }
.pool-lbl { font-size: $text-sm; color: $slate-500; }
.pool-sub { margin-top: 4rpx; font-size: $text-xs; color: $slate-500; display: block; }

.picker-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: $space-4; background: $slate-50; border-radius: $radius-md;
  margin-bottom: $space-4; border: 1rpx solid $slate-200;
}
.picker-label { font-size: $text-md; color: $slate-600; font-weight: $fw-medium; }
.picker-value { font-size: $text-md; color: $brand-600; font-weight: $fw-semibold; }

.result-toggle {
  display: flex; gap: $space-3; margin-bottom: $space-4;
}
.toggle-item {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: $space-2;
  padding: $space-4; border-radius: $radius-md; border: 2rpx solid $slate-200;
  background: #fff; transition: all $dur-fast $ease-smooth;
}
.toggle-item.active {
  border-color: $brand-600; background: $brand-50; color: $brand-600;
}
.toggle-item.active.bad-toggle { border-color: $danger; background: $danger-bg; color: $danger-deep; }
.toggle-icon { font-size: $text-lg; font-weight: $fw-bold; }
.toggle-text { font-size: $text-md; font-weight: $fw-semibold; }

.remark {
  width: 100%; min-height: 120rpx; padding: $space-3 $space-4;
  margin: $space-3 0; background: $slate-50; border-radius: $radius-md;
  border: 1rpx solid $slate-200; font-size: $text-base; box-sizing: border-box;
}

.preview-grid { display: flex; flex-wrap: wrap; gap: $space-2; margin-bottom: $space-3; }
.preview-img { width: 140rpx; height: 140rpx; border-radius: $radius-sm; }

.media-btn, .ai-btn, .defect-btn, .voice-btn { width: 100%; margin-bottom: $space-3; }
.ai-btn { border-color: $warn; color: $warn-deep; &:active { background: $warn-bg; } }
.defect-btn { border-color: $danger; color: $danger-deep; &:active { background: $danger-bg; } }
.voice-btn { border-color: #8b5cf6; color: #7c3aed; &:active { background: #ede9fe; } }
.submit-btn { width: 100%; margin-top: $space-3; }
</style>
