<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showLoadingToast, closeToast, showDialog } from 'vant'
import { getTaskDetail, submitReport, type H5Task } from '@/api/tasks'
import { uploadFile } from '@/api/files'
import { photoAiCount, defectAiClassify, voiceParseReport, attachmentIdToUrl } from '@/api/ai'
import { VoiceInput, isVoiceInputSupported } from '@/utils/voice-input'
import ScanTaskCodeButton from '@/components/ScanTaskCodeButton.vue'
import { parseTaskCodeFromScan } from '@/utils/parseTaskCode'
import { tenantH5Path } from '@/utils/tenant'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const task = ref<H5Task | null>(null)
const scanned = ref(!!route.query.task_code)

const form = reactive({
  task_code: route.query.task_code as string || '',
  good_qty: 0,
  bad_qty: 0,
  remark: '',
  attachment_ids: '',
})

const uploads = ref<{ id: number | string; url?: string; name: string }[]>([])

const totalQty = computed(() => form.good_qty + form.bad_qty)

function onScanned(raw: string) {
  const code = parseTaskCodeFromScan(raw)
  if (!code) {
    showToast('无法识别任务码')
    return
  }
  form.task_code = code
  loadTask()
}

async function loadTask() {
  if (!form.task_code.trim()) return
  try {
    task.value = await getTaskDetail(form.task_code.trim())
    scanned.value = true
    if (task.value?.use_unit_report === true) {
      router.replace({ path: tenantH5Path('/report-unit'), query: { task_code: form.task_code.trim() } })
      return
    }
  } catch {
    showToast('查询任务失败')
    task.value = null
  }
}

async function handleUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*,video/*'
  input.multiple = false
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    const toast = showLoadingToast({ message: '上传中...', duration: 0 })
    try {
      const resp = (await uploadFile(file)) as any
      const id = resp?.id ?? resp?.file_id
      if (id) {
        uploads.value.push({ id, name: file.name })
        form.attachment_ids = uploads.value.map((u) => u.id).join(',')
        showToast('上传成功')
      }
    } catch {
      showToast('上传失败')
    } finally {
      closeToast()
    }
  }
  input.click()
}

function removeUpload(idx: number) {
  uploads.value.splice(idx, 1)
  form.attachment_ids = uploads.value.map((u) => u.id).join(',')
}

// AI：语音报工 — 按住按钮录音，结束调用 voice-parse 解析为结构化字段
const voiceInput = ref<VoiceInput | null>(null)
const voiceRecording = ref(false)
const voiceInterim = ref('')
const showTextVoice = ref(false)
const textVoiceContent = ref('')
const voiceParsing = ref(false)

function handleVoiceToggle() {
  if (voiceRecording.value) {
    voiceInput.value?.stop()
    return
  }
  if (!isVoiceInputSupported()) {
    // 降级：弹出文字输入框，用系统输入法语音键或手动输入
    textVoiceContent.value = ''
    showTextVoice.value = true
    return
  }
  voiceInterim.value = ''
  const vi = new VoiceInput({ lang: 'zh-CN', interim: true, continuous: false })
  voiceInput.value = vi
  vi.on('onStart', () => {
    voiceRecording.value = true
  })
  vi.on('onResult', (text, isFinal) => {
    voiceInterim.value = text
    if (isFinal) {
      voiceRecording.value = false
      parseVoiceText(text)
    }
  })
  vi.on('onError', (_code, msg) => {
    voiceRecording.value = false
    voiceInterim.value = ''
    // Web Speech API 失败（常见于国内网络），降级到文字输入
    showTextVoice.value = true
    showToast('语音识别服务不可用，已切换为文字输入')
  })
  vi.on('onEnd', () => {
    voiceRecording.value = false
    voiceInterim.value = ''
  })
  vi.start()
}

async function handleTextVoiceSubmit() {
  // 优先用弹层文字，其次用备注框内容
  const text = (textVoiceContent.value.trim() || form.remark.trim())
  if (!text) {
    showToast('请输入报工内容')
    return
  }
  showTextVoice.value = false
  voiceParsing.value = true
  try {
    await parseVoiceText(text)
  } finally {
    voiceParsing.value = false
  }
}

async function parseVoiceText(text: string) {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  if (!text.trim()) return
  showLoadingToast({ message: 'AI 解析中...', duration: 0 })
  try {
    const res = await voiceParseReport({ text: text.trim(), task_id: task.value.id })
    closeToast()
    // 将解析结果填入表单（仅在用户尚未填写时）
    if (typeof res.good_qty === 'number' && res.good_qty > 0 && form.good_qty === 0) {
      form.good_qty = res.good_qty
    }
    if (typeof res.bad_qty === 'number' && res.bad_qty > 0 && form.bad_qty === 0) {
      form.bad_qty = res.bad_qty
    }
    if (res.remark && !form.remark) {
      form.remark = res.remark
    } else if (res.defect_keywords?.length) {
      form.remark = form.remark
        ? `${form.remark}\n缺陷关键词: ${res.defect_keywords.join('、')}`
        : `缺陷关键词: ${res.defect_keywords.join('、')}`
    }
    await showDialog({
      title: '语音解析完成',
      message: res.summary
        ? `${res.summary}\n\n原文：${text}`
        : `原文：${text}\n\n解析：合格 ${res.good_qty ?? '-'} 件，不良 ${res.bad_qty ?? '-'} 件${res.defect_keywords?.length ? '\n关键词: ' + res.defect_keywords.join('、') : ''}`,
    })
  } catch (e: unknown) {
    closeToast()
    showToast(e instanceof Error ? e.message : 'AI 解析失败')
  } finally {
    voiceInput.value?.destroy()
    voiceInput.value = null
  }
}

onMounted(() => {
  // 深链直达：有 task_code 就跳过扫码直接加载任务
  if (form.task_code) loadTask()
})

onUnmounted(() => {
  voiceInput.value?.destroy()
  voiceInput.value = null
})

// AI：拍照计数后填入合格数
const aiCounting = ref(false)
async function handleAiCount() {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  if (!uploads.value.length) {
    showToast('请先上传零件照片')
    return
  }
  aiCounting.value = true
  try {
    const image_urls = uploads.value.map((u) => attachmentIdToUrl(Number(u.id), u.name))
    const res = await photoAiCount({ image_urls, task_id: task.value.id })
    if (!res.ok) {
      showToast(res.error || 'AI 计数不可用')
      return
    }
    const cur = Number(res.count || 0)
    if (cur <= 0) {
      showToast('AI 未识别到零件，请检查照片')
      return
    }
    form.good_qty = cur
    showDialog({
      title: 'AI 计数完成',
      message: `识别 ${res.image_count} 张照片，共 ${cur} 件。可信度：${res.confidence || 'unknown'}\n${res.note || ''}`,
    })
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : 'AI 计数失败')
  } finally {
    aiCounting.value = false
  }
}

// AI：识别缺陷后填入备注
const aiClassifying = ref(false)
async function handleAiDefect() {
  if (!task.value?.id) {
    showToast('请先加载任务')
    return
  }
  if (!uploads.value.length) {
    showToast('请先上传不良品照片')
    return
  }
  if (form.bad_qty <= 0) {
    showToast('请先填写不良数')
    return
  }
  aiClassifying.value = true
  try {
    const image_urls = uploads.value.map((u) => attachmentIdToUrl(Number(u.id), u.name))
    const res = await defectAiClassify({
      image_urls,
      task_id: task.value.id,
      remark: form.remark || undefined,
    })
    if (!res.ok) {
      showToast(res.error || 'AI 识别不可用')
      return
    }
    const parts: string[] = []
    if (res.defect_name) parts.push(`【${res.defect_name}】`)
    if (res.severity) parts.push(`严重度:${res.severity}`)
    if (res.description) parts.push(res.description)
    const aiText = parts.join(' / ')
    if (aiText) {
      form.remark = form.remark ? `${form.remark}\n${aiText}` : aiText
    }
    showToast(`已识别为 ${res.defect_name ?? '未知缺陷'}`)
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : 'AI 识别失败')
  } finally {
    aiClassifying.value = false
  }
}

async function handleSubmit() {
  if (!form.task_code.trim()) {
    showToast('请输入任务码')
    return
  }
  if (totalQty.value <= 0) {
    showToast('合格数+不良数必须大于0')
    return
  }
  if (task.value?.assigned_qty && totalQty.value > (task.value.remaining_qty ?? 0)) {
    showToast(`报工数量超出派工上限，最多还可报 ${task.value.remaining_qty ?? 0} 件`)
    return
  }
  if (!scanned.value) {
    // 用户手动输入的任务码，先查询再提交
    try {
      await getTaskDetail(form.task_code.trim())
    } catch {
      showToast('任务码无效')
      return
    }
  }
  submitting.value = true
  showLoadingToast({ message: '提交中...', duration: 0 })
  try {
    const result = await submitReport({
      task_code: form.task_code.trim(),
      good_qty: form.good_qty,
      bad_qty: form.bad_qty,
      remark: form.remark || undefined,
      attachment_ids: form.attachment_ids || undefined,
    })
    closeToast()
    await showDialog({
      title: '报工成功',
      message: `合格 ${result.good_qty} 件，不良 ${result.bad_qty} 件\n状态：${result.status}`,
      confirmButtonText: '继续报工',
    })
    // 重置表单，保留任务码
    form.good_qty = 0
    form.bad_qty = 0
    form.remark = ''
    uploads.value = []
    form.attachment_ids = ''
  } catch {
    // toast already shown in interceptor
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div>
    <!-- 任务码 -->
    <div class="rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 p-4 text-white">
      <div class="text-sm opacity-80">扫码报工</div>
      <div class="mt-2">扫描任务标签上的二维码，或手动输入任务码</div>
    </div>

    <!-- 任务码输入 -->
    <div class="mx-4 -mt-3 space-y-3 rounded-xl bg-white p-3 shadow-sm">
      <ScanTaskCodeButton @scan="onScanned" />
      <div class="flex items-center gap-2">
        <input
          v-model="form.task_code"
          type="text"
          placeholder="输入或粘贴任务码"
          class="min-w-0 flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm outline-none focus:border-blue-400"
          @change="loadTask"
        />
        <van-button size="small" type="primary" plain @click="loadTask">查询</van-button>
      </div>
      <van-button block plain type="success" @click="router.push(tenantH5Path('/tasks'))">
        去「我的任务」选任务报工（已派工列表）
      </van-button>
    </div>

    <!-- 任务信息 -->
    <div v-if="task" class="mx-4 mt-3 rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-center gap-2 text-sm">
        <van-icon name="info-o" class="text-blue-500" />
        <span class="font-medium">{{ task.process?.name || `工序#${task.process_id}` }}</span>
        <van-tag v-if="task.status === 'done'" type="success" size="medium">已完成</van-tag>
      </div>
      <div v-if="task.work_order?.sku" class="mt-1 text-xs text-zinc-500">
        型号：{{ task.work_order.sku.code }} {{ task.work_order.sku.name }}
      </div>
      <div class="mt-1 text-xs text-zinc-500">任务计划：{{ task.planned_qty }} 件</div>
      <div v-if="task.assigned_qty" class="mt-1 text-xs text-zinc-500">
        我的派工：{{ task.assigned_qty }} 件 · 已报 {{ task.reported_qty ?? 0 }} · 还可报
        <span class="font-medium text-blue-600">{{ task.remaining_qty ?? 0 }}</span> 件
      </div>
    </div>

    <!-- 数量输入 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">报工数量</div>
      <div class="grid grid-cols-2 gap-3">
        <div class="rounded-xl bg-white p-3 shadow-sm">
          <div class="text-xs text-zinc-500">合格数</div>
          <input
            v-model.number="form.good_qty"
            type="number"
            min="0"
            placeholder="0"
            class="mt-1 w-full text-2xl font-bold text-green-600 outline-none"
          />
        </div>
        <div class="rounded-xl bg-white p-3 shadow-sm">
          <div class="text-xs text-zinc-500">不良数</div>
          <input
            v-model.number="form.bad_qty"
            type="number"
            min="0"
            placeholder="0"
            class="mt-1 w-full text-2xl font-bold text-red-500 outline-none"
          />
        </div>
      </div>
      <div v-if="totalQty > 0" class="mt-2 text-center text-sm text-zinc-500">
        共计 <span class="font-semibold text-zinc-800">{{ totalQty }}</span> 件
      </div>
    </div>

    <!-- 备注 -->
    <div class="mx-4 mt-4">
      <div class="mb-1 flex items-center justify-between">
        <div class="text-sm font-medium text-zinc-700">备注</div>
        <van-button
          size="mini"
          :type="voiceRecording ? 'danger' : 'primary'"
          :loading="voiceRecording"
          icon="volume-o"
          class="!px-2"
          @click="handleVoiceToggle"
        >
          {{ voiceRecording ? '录音中…点击停止' : '语音输入' }}
        </van-button>
      </div>
      <textarea
        v-model="form.remark"
        :placeholder="voiceRecording ? `正在识别: ${voiceInterim || '...'}` : '可选备注信息，如：做了50个好的，2个有划痕'"
        rows="2"
        class="w-full rounded-xl border border-zinc-200 bg-white p-3 text-sm outline-none focus:border-blue-400"
      />
      <!-- AI 解析备注按钮 -->
      <van-button
        v-if="form.remark.trim() && form.good_qty === 0 && form.bad_qty === 0 && !voiceParsing"
        size="mini"
        type="primary"
        plain
        class="mt-1"
        :loading="voiceParsing"
        @click="handleTextVoiceSubmit"
      >
        AI 解析备注
      </van-button>

    <!-- 文字输入语音降级弹层 -->
    <van-overlay :show="showTextVoice" @click="showTextVoice = false" z-index="200">
      <div class="fixed inset-x-4 top-24 rounded-2xl bg-white p-5 shadow-xl" @click.stop>
        <div class="mb-3 text-base font-semibold text-zinc-800">语音报工（文字输入）</div>
        <div class="mb-2 text-xs text-zinc-500">可用手机键盘的🎙语音键输入，或直接打字</div>
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

    <!-- 附件上传 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">图片/视频证据</div>
      <div class="flex flex-wrap gap-2">
        <div
          v-for="(u, idx) in uploads"
          :key="idx"
          class="relative flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-600"
        >
          <van-icon name="photograph" />
          <span class="max-w-[120px] truncate">{{ u.name }}</span>
          <van-icon name="cross" class="cursor-pointer" @click="removeUpload(idx)" />
        </div>
        <div
          class="flex cursor-pointer items-center gap-1 rounded-lg border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-500"
          @click="handleUpload"
        >
          <van-icon name="plus" />
          添加文件
        </div>
      </div>
      <!-- AI 按钮组 -->
      <div v-if="uploads.length" class="mt-3 grid grid-cols-2 gap-2">
        <van-button
          size="small"
          plain
          type="primary"
          :loading="aiCounting"
          icon="aim"
          @click="handleAiCount"
        >
          AI 数一下零件
        </van-button>
        <van-button
          size="small"
          plain
          type="warning"
          :loading="aiClassifying"
          :disabled="form.bad_qty <= 0"
          icon="warning-o"
          @click="handleAiDefect"
        >
          AI 识别缺陷
        </van-button>
      </div>
    </div>

    <!-- 提交按钮：不按数量禁用按钮，便于点击后出现 Toast 提示；禁用时观感像「失灵」 -->
    <div class="mx-4 mt-6 pb-[max(6rem,calc(env(safe-area-inset-bottom,0px)+5rem))]">
      <van-button block type="primary" size="large" :loading="submitting" native-type="button" @click="handleSubmit">
        提交报工
      </van-button>
      <p v-if="totalQty <= 0" class="mt-2 text-center text-xs text-zinc-400">请先填写合格数或不良数（合计须大于 0）</p>
    </div>
  </div>
</template>
