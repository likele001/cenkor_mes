<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showDialog, showToast } from 'vant'
import { getTaskDetail, type H5Task } from '@/api/tasks'
import { getTaskUnits, submitReportUnit, type AnomalyWarning, type ReportUnitItem, type TaskFlowContext } from '@/api/reportUnits'
import { getReportMediaSettings, type ReportMediaSettings } from '@/api/settings'
import { reportAiCheck, defectAiClassify, photoAiCount, voiceParseReport, attachmentIdToUrl, type DefectClassifyOut } from '@/api/ai'
import { VoiceInput, isVoiceInputSupported } from '@/utils/voice-input'
import { tenantH5Path } from '@/utils/tenant'
import CameraPhotoCapture from '@/components/CameraPhotoCapture.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const aiChecking = ref(false)
const aiHints = ref<string[]>([])
const aiClassifying = ref(false)
const aiClassifyResult = ref<DefectClassifyOut | null>(null)
const task = ref<H5Task | null>(null)
const units = ref<ReportUnitItem[]>([])
const assignedQty = ref(0)
const reportedQty = ref(0)
const remainingQty = ref(0)

const flow = ref<TaskFlowContext | null>(null)

const form = ref({
  task_code: (route.query.task_code as string) || '',
  unit_seq: null as number | null,
  result_type: 'good' as 'good' | 'bad',
  remark: '',
})

const uploads = ref<{ id: number; name: string }[]>([])
const mediaCfg = ref<ReportMediaSettings | null>(null)

// Voice reporting
const voiceInput = ref<VoiceInput | null>(null)
const voiceRecording = ref(false)
const voiceInterim = ref('')
const aiCounting = ref(false)

const currentUnit = computed(() => {
  if (form.value.unit_seq) {
    return units.value.find((u) => u.unit_seq === form.value.unit_seq)
  }
  return units.value.find((u) => u.status === 'draft')
})

const progressLabel = computed(() => {
  if (flow.value?.piece_pool_enabled) {
    const avail = flow.value.pool_available ?? 0
    const total = flow.value.pool_total ?? assignedQty.value
    return `可领 ${avail} / 共 ${total} 套`
  }
  const cur = currentUnit.value?.unit_seq ?? '—'
  return `第 ${cur} / ${assignedQty.value} 件`
})

const poolMode = computed(() => flow.value?.piece_pool_enabled === true)

const currentProductCode = computed(() => currentUnit.value?.product_code || null)

function unitStatusText(s: string) {
  if (s === 'draft') return '待报'
  if (s === 'submitted') return '待初审'
  if (s === 'leader_approved') return '待终审'
  if (s === 'qc_approved') return '已通过'
  if (s === 'rejected') return '已驳回'
  return s
}

function unitStatusType(s: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  if (s === 'draft') return 'primary'
  if (s === 'qc_approved') return 'success'
  if (s === 'submitted' || s === 'leader_approved') return 'warning'
  return 'default'
}

async function loadTask() {
  if (!form.value.task_code.trim()) return
  loading.value = true
  try {
    task.value = await getTaskDetail(form.value.task_code.trim())
    const res = await getTaskUnits(form.value.task_code.trim())
    units.value = res.items
    assignedQty.value = res.assigned_qty
    reportedQty.value = res.reported_qty
    remainingQty.value = res.remaining_qty
    flow.value = res.flow ?? null
    if (task.value?.report_mode === 'batch' || task.value?.use_unit_report !== true) {
      showToast('当前为批量报工模式')
      router.replace({ path: tenantH5Path('/report'), query: { task_code: form.value.task_code.trim() } })
      return
    }
    if (!form.value.unit_seq && !res.flow?.piece_pool_enabled) {
      const draft = res.items.find((u) => u.status === 'draft')
      if (draft) form.value.unit_seq = draft.unit_seq
    }
  } catch {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleAiClassify() {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  if (!uploads.value.length) {
    showToast('请先上传照片')
    return
  }
  aiClassifying.value = true
  try {
    const image_urls = uploads.value.map((u) => attachmentIdToUrl(u.id, u.name))
    const res = await defectAiClassify({
      image_urls,
      task_id: task.value.id,
      remark: form.value.remark || undefined,
    })
    aiClassifyResult.value = res
    if (!res.ok) {
      showToast(res.error || 'AI 识别不可用')
      return
    }
    // 拼接备注：AI 识别 + 原始备注
    const parts: string[] = []
    if (res.defect_name) parts.push(`【${res.defect_name}】`)
    if (res.severity) parts.push(`严重度:${res.severity}`)
    if (res.description) parts.push(res.description)
    const aiText = parts.join(' / ')
    if (aiText) {
      form.value.remark = form.value.remark ? `${form.value.remark}\n${aiText}` : aiText
    }
    if (res.confidence === 'low') {
      showToast('识别可信度较低，请人工确认')
    } else {
      showToast(`已识别为 ${res.defect_name ?? '未知缺陷'}`)
    }
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : 'AI 识别失败')
  } finally {
    aiClassifying.value = false
  }
}

// ── Voice reporting ──
const showTextVoice = ref(false)
const textVoiceContent = ref('')
const voiceParsing = ref(false)

function handleVoiceToggle() {
  if (voiceRecording.value) {
    voiceInput.value?.stop()
    return
  }
  if (!isVoiceInputSupported()) {
    textVoiceContent.value = ''
    showTextVoice.value = true
    return
  }
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  voiceInterim.value = ''
  const vi = new VoiceInput({ lang: 'zh-CN', interim: true, continuous: false })
  vi.on('onResult', (text, isFinal) => {
    voiceInterim.value = text
    if (isFinal) {
      voiceRecording.value = false
      parseVoiceResult(text)
    }
  })
  vi.on('onError', (_code, msg) => {
    voiceRecording.value = false
    voiceInterim.value = ''
    showTextVoice.value = true
    showToast('语音识别服务不可用，已切换为文字输入')
  })
  vi.on('onEnd', () => {
    voiceRecording.value = false
    voiceInterim.value = ''
  })
  voiceInput.value = vi
  voiceRecording.value = true
  vi.start()
}

async function handleTextVoiceSubmit() {
  const text = (textVoiceContent.value.trim() || form.value.remark.trim())
  if (!text) {
    showToast('请输入报工内容')
    return
  }
  showTextVoice.value = false
  voiceParsing.value = true
  try {
    await parseVoiceResult(text)
  } finally {
    voiceParsing.value = false
  }
}

async function parseVoiceResult(text: string) {
  if (!task.value?.id || !text.trim()) return
  try {
    const res = await voiceParseReport({ text: text.trim(), task_id: task.value.id })
    if (res.remark) form.value.remark = form.value.remark ? `${form.value.remark}\n${res.remark}` : res.remark
    // 根据解析结果自动选择合格/不良
    if (res.result_type === 'bad') form.value.result_type = 'bad'
    else if (res.result_type === 'good') form.value.result_type = 'good'
    await showDialog({
      title: '语音解析完成',
      message: res.summary || text,
    })
  } catch {
    form.value.remark = form.value.remark ? `${form.value.remark}\n${text}` : text
    showToast('语音已填入备注')
  }
}

// ── AI photo counting ──
async function handleAiCount() {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  if (!uploads.value.length) {
    showToast('请先拍摄照片')
    return
  }
  aiCounting.value = true
  try {
    const image_urls = uploads.value.map((u) => attachmentIdToUrl(u.id, u.name))
    const res = await photoAiCount({ image_urls, task_id: task.value.id })
    if (res.count !== null && res.count !== undefined) {
      if (form.value.result_type === 'good') {
        showToast(`AI 识别到 ${res.count} 件合格品`)
      } else {
        showToast(`AI 识别到 ${res.count} 件`)
      }
    } else {
      showToast(res.error || 'AI 无法计数')
    }
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : 'AI 计数失败')
  } finally {
    aiCounting.value = false
  }
}

async function handleAiCheck() {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  aiChecking.value = true
  aiHints.value = []
  try {
    const res = await reportAiCheck({
      task_id: task.value.id,
      result_type: form.value.result_type,
      remark: form.value.remark,
      good_qty: form.value.result_type === 'good' ? 1 : 0,
      bad_qty: form.value.result_type === 'bad' ? 1 : 0,
    })
    aiHints.value = res.hints || []
    if (res.suggest_remark && !form.value.remark) form.value.remark = res.suggest_remark
    await showDialog({
      title: res.ok === false ? '建议修改' : 'AI 检查',
      message: (res.hints?.length ? res.hints.join('\n') : res.reply) || '无特别建议',
    })
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : 'AI 暂不可用')
  } finally {
    aiChecking.value = false
  }
}

/** 展示 AI 风险分流反馈 */
function showRiskTip(r: Record<string, unknown>) {
  if (r.auto_passed === true) {
    showToast('AI 已自动审核通过')
  } else if (r.risk_level === 'high') {
    showToast('⚠️ 高风险报工，已提交班组长审核')
  } else if (r.risk_level === 'medium') {
    showToast('已提交班组长审核')
  }
}

async function handleSubmit() {
  if (!form.value.task_code.trim()) {
    showToast('请输入任务码')
    return
  }
  if (!uploads.value.length) {
    showToast('请至少上传1张照片')
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const res = await submitReportUnit({
      task_code: form.value.task_code.trim(),
      unit_seq: poolMode.value ? undefined : form.value.unit_seq ?? undefined,
      result_type: form.value.result_type,
      attachment_ids: uploads.value.map((u) => u.id).join(','),
      remark: form.value.remark || undefined,
    })

    // ── 异常检测拦截：发现可疑/异常，需用户二次确认 ──
    if (res && typeof res === 'object' && 'anomaly_warning' in res) {
      const warning = res as unknown as AnomalyWarning
      const isAbnormal = warning.anomaly_level === 'abnormal'
      submitting.value = false
      try {
        await showDialog({
          title: isAbnormal ? '⚠️ 报工异常' : '⚡ 报工提醒',
          message: warning.anomaly_reason + '\n\n确认继续提交还是取消？',
          confirmButtonText: '确认提交',
          cancelButtonText: '取消',
          showCancelButton: true,
        })
        // 用户点了"确认提交" → 带 anomaly_confirmed=true 重新提交
        submitting.value = true
        // 二次提交成功
        const res2 = await submitReportUnit({
          task_code: form.value.task_code.trim(),
          unit_seq: poolMode.value ? undefined : form.value.unit_seq ?? undefined,
          result_type: form.value.result_type,
          attachment_ids: uploads.value.map((u) => u.id).join(','),
          remark: form.value.remark || undefined,
          anomaly_confirmed: true,
        })
        showRiskTip(res2 as unknown as Record<string, unknown>)
        uploads.value = []
        form.value.remark = ''
        await loadTask()
        if (remainingQty.value <= 0) {
          await showDialog({ title: '完成', message: '本任务件次已全部报完' })
        } else {
          showToast('提交成功，请继续下一件')
        }
      } catch {
        // 用户点了"取消" → 不做任何操作
      }
      submitting.value = false
      return
    }

    uploads.value = []
    form.value.remark = ''
    showRiskTip(res as unknown as Record<string, unknown>)
    await loadTask()
    if (remainingQty.value <= 0) {
      await showDialog({ title: '完成', message: '本任务件次已全部报完' })
    } else {
      showToast('提交成功，请继续下一件')
    }
  } finally {
    submitting.value = false
  }
}

function selectUnit(u: ReportUnitItem) {
  if (u.status !== 'draft') return
  form.value.unit_seq = u.unit_seq
  uploads.value = []
}

onMounted(async () => {
  try {
    mediaCfg.value = await getReportMediaSettings()
  } catch {
    mediaCfg.value = null
  }
  if (form.value.task_code) loadTask()
})

onUnmounted(() => {
  voiceInput.value?.destroy()
  voiceInput.value = null
})

watch(
  () => route.query.task_code,
  (code) => {
    if (code) {
      form.value.task_code = String(code)
      loadTask()
    }
  },
)
</script>

<template>
  <div class="pb-24">
    <div v-if="!route.query.task_code" class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="text-sm text-zinc-600 mb-2">输入任务码（主动报工）</div>
      <van-field v-model="form.task_code" placeholder="任务码" />
      <van-button block type="primary" class="mt-2" :loading="loading" @click="loadTask">查询任务</van-button>
    </div>

    <van-loading v-if="loading" class="py-8" vertical>加载中...</van-loading>
    <div v-else-if="task" class="mx-4 mt-3 space-y-3">
      <div class="rounded-xl bg-gradient-to-r from-green-500 to-emerald-600 p-4 text-white">
        <div class="text-sm opacity-90">{{ task.process?.name }}</div>
        <div class="mt-1 font-mono text-lg">{{ task.task_code }}</div>
        <div v-if="task.work_order?.sku" class="mt-1 text-sm opacity-90">
          {{ task.work_order.sku.code }} {{ task.work_order.sku.name }}
        </div>
        <div class="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
          <div><div class="text-xl font-bold">{{ assignedQty }}</div><div class="opacity-80">分配</div></div>
          <div><div class="text-xl font-bold">{{ reportedQty }}</div><div class="opacity-80">已报</div></div>
          <div><div class="text-xl font-bold">{{ remainingQty }}</div><div class="opacity-80">待报</div></div>
        </div>
      </div>

      <div class="rounded-xl bg-white p-3 shadow-sm">
        <div class="text-sm font-medium text-zinc-700">{{ progressLabel }}</div>
        <div v-if="poolMode" class="mt-2 text-sm text-zinc-500">
          系统按套号顺序自动分配，谁有空谁领下一套；客户扫码每一套的成品码即可溯源。
        </div>
        <div v-else class="mt-2 flex flex-wrap gap-2">
          <van-tag
            v-for="u in units"
            :key="u.id"
            :type="unitStatusType(u.status)"
            size="medium"
            :plain="u.status === 'draft'"
            class="cursor-pointer"
            @click="selectUnit(u)"
          >
            #{{ u.unit_seq }} {{ unitStatusText(u.status) }}
          </van-tag>
        </div>
      </div>

      <div v-if="remainingQty > 0 && (poolMode || currentUnit?.status === 'draft')" class="rounded-xl bg-white p-3 shadow-sm space-y-3">
        <van-radio-group v-model="form.result_type" direction="horizontal">
          <van-radio name="good">合格</van-radio>
          <van-radio name="bad">不良</van-radio>
        </van-radio-group>
        <div
          v-if="poolMode && flow?.is_first_process"
          class="rounded-lg bg-green-50 p-3 border border-green-200 text-sm text-green-800"
        >
          首道工序：提交后将自动领取下一套并绑定成品码（派工时已预生成 FP 码，终审后写入溯源链）。
        </div>
        <div
          v-else-if="poolMode && flow?.auto_bind_piece"
          class="rounded-lg bg-blue-50 p-3 border border-blue-200 text-sm text-blue-800"
        >
          提交后将自动领取上道已完成的下一套并绑定成品码（{{ flow?.prev_process_name }} 已终审通过的套号）。
        </div>
        <div
          v-else-if="flow?.auto_bind_piece && form.result_type === 'good'"
          class="rounded-lg bg-blue-50 p-3 border border-blue-200 text-sm text-blue-800"
        >
          <template v-if="currentProductCode">
            已绑定成品码：<span class="font-mono font-medium">{{ currentProductCode }}</span>
          </template>
          <template v-else>
            报工后将自动绑定首道工序成品码（请确认第 {{ currentUnit?.unit_seq }} 件已在「{{ flow?.prev_process_name }}」完成）
          </template>
        </div>
        <div
          v-else-if="flow?.is_first_process && form.result_type === 'good'"
          class="rounded-lg bg-green-50 p-3 border border-green-200 text-sm text-green-800"
        >
          首道工序：终审通过后将自动生成成品码 FP...
        </div>
        <van-field v-model="form.remark" label="备注" type="textarea" rows="2" placeholder="可选">
          <template #button>
            <van-button
              size="mini"
              :type="voiceRecording ? 'danger' : 'primary'"
              :loading="voiceRecording"
              icon="volume-o"
              class="!px-2"
              @click="handleVoiceToggle"
            >
              {{ voiceRecording ? '停止' : '语音' }}
            </van-button>
          </template>
        </van-field>
        <div>
          <div class="text-sm text-zinc-600 mb-2">报工照片（必填，现场拍摄）</div>
          <CameraPhotoCapture
            v-model="uploads"
            :max-count="mediaCfg?.max_photo_count ?? 5"
            label="拍摄照片"
          />
        </div>
        <van-button
          v-if="uploads.length"
          block
          plain
          type="primary"
          :loading="aiCounting"
          icon="aim"
          class="mb-2"
          @click="handleAiCount"
        >
          AI 拍照计数
        </van-button>
        <van-button
          v-if="form.result_type === 'bad' && uploads.length"
          block
          plain
          type="warning"
          :loading="aiClassifying"
          class="mb-2"
          @click="handleAiClassify"
        >
          AI 识别缺陷类型
        </van-button>
        <van-button block plain type="primary" :loading="aiChecking" class="mb-2" @click="handleAiCheck">
          AI 检查一下
        </van-button>
        <van-button block type="primary" size="large" :loading="submitting" @click="handleSubmit">
          {{ poolMode ? '领取下一套并提交' : '提交本件报工' }}
        </van-button>
      </div>
      <van-empty v-else-if="!loading" description="暂无待报工件次" />
    </div>

    <!-- 文字输入语音降级弹层 -->
    <van-overlay :show="showTextVoice" @click="showTextVoice = false" z-index="200">
      <div class="fixed inset-x-4 top-24 rounded-2xl bg-white p-5 shadow-xl" @click.stop>
        <div class="mb-3 text-base font-semibold text-zinc-800">语音报工（文字输入）</div>
        <div class="mb-2 text-xs text-zinc-500">可用手机键盘的🎤语音键输入，或直接打字</div>
        <textarea
          v-model="textVoiceContent"
          rows="3"
          placeholder="例如：做了50个好的，2个有划痕"
          class="w-full rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm outline-none focus:border-blue-400"
          autofocus
        />
        <div class="mt-3 flex gap-3">
          <van-button block type="primary" :loading="voiceParsing" @click="handleTextVoiceSubmit">AI 解析填入</van-button>
          <van-button block @click="showTextVoice = false">取消</van-button>
        </div>
      </div>
    </van-overlay>
  </div>
</template>
