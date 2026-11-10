<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { getMyReportUnits, getReportUnitDetail, type ReportUnitItem } from '@/api/reportUnits'

// 后端一次最多 200 条，这里按 20 条一页翻，剩下的留给「加载更多」
const PAGE_SIZE = 20

type AuditRow = {
  id: number
  audit_level?: string | null
  action?: string | null
  reason?: string | null
  attachment_ids?: string | null
  created_at?: string | null
}
type UnitDetail = ReportUnitItem & { audits?: AuditRow[] }

const loading = ref(false)
const loadingMore = ref(false)
const items = ref<ReportUnitItem[]>([])
const hasMore = ref(true)
const offset = ref(0)
const status = ref('')
const loaded = ref(false)

const STATUS_TABS = [
  { v: '', label: '全部' },
  { v: 'submitted', label: '待初审' },
  { v: 'leader_approved', label: '待终审' },
  { v: 'qc_approved', label: '已通过' },
  { v: 'rejected', label: '已驳回' },
]

const STATUS_TEXT: { [key: string]: string } = {
  draft: '待报',
  submitted: '待初审',
  leader_approved: '待终审',
  qc_approved: '已通过',
  rejected: '已驳回',
}

function statusText(s: string) {
  return STATUS_TEXT[s] || s
}

function statusType(s: string): 'success' | 'danger' | 'warning' | 'default' {
  if (s === 'qc_approved') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'submitted' || s === 'leader_approved') return 'warning'
  return 'default'
}

function resultText(r: string | null) {
  if (r === 'good') return '合格'
  if (r === 'bad') return '不良'
  return '—'
}

// 合格/不良按「已加载的这部分」统计，不假装是全量（后端没有聚合接口）
const summary = computed(() => {
  let good = 0
  let bad = 0
  for (const r of items.value) {
    if (r.result_type === 'good') good += 1
    else if (r.result_type === 'bad') bad += 1
  }
  return { good, bad }
})

async function load(reset = true) {
  if (reset) {
    loading.value = true
    offset.value = 0
    hasMore.value = true
  } else {
    loadingMore.value = true
  }
  try {
    // 多取一条判断有没有下一页，省掉一个额外的 count 接口
    const res = await getMyReportUnits({
      status: status.value || undefined,
      exclude_draft: true,
      offset: offset.value,
      limit: PAGE_SIZE + 1,
    })
    const rows = res.items || []
    const more = rows.length > PAGE_SIZE
    const pageRows = more ? rows.slice(0, PAGE_SIZE) : rows
    items.value = reset ? pageRows : [...items.value, ...pageRows]
    hasMore.value = more
    offset.value += pageRows.length
    loaded.value = true
  } catch (e: unknown) {
    if (reset) items.value = []
    showToast(e instanceof Error ? e.message : '报工记录加载失败')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function pickStatus(v: string) {
  if (status.value === v) return
  status.value = v
  void load()
}

// 详情：列表上看不到驳回原因，得进审核轨迹才看得见，这是员工改单前最需要的信息
const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref<UnitDetail | null>(null)

async function openDetail(id: number) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = (await getReportUnitDetail(id)) as UnitDetail
  } catch (e: unknown) {
    detailOpen.value = false
    showToast(e instanceof Error ? e.message : '记录详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

function auditTitle(a: AuditRow) {
  const level = a.audit_level === 'leader' ? '班组长' : a.audit_level === 'qc' ? '质检' : (a.audit_level || '审核')
  const action = a.action === 'approve' ? '通过' : a.action === 'reject' ? '驳回' : (a.action || '处理')
  return `${level}${action}`
}

function fmtTime(v: string | null | undefined) {
  if (!v) return ''
  return String(v).slice(0, 16).replace('T', ' ')
}

onMounted(() => void load())
</script>

<template>
  <div class="p-3">
    <div class="rounded-xl bg-white p-3 shadow-sm">
      <div class="flex items-end justify-between">
        <div>
          <div class="text-sm font-medium text-zinc-800">报工记录</div>
          <div class="mt-1 text-[11px] text-zinc-500">只列已提交的件次，未报工的占位槽位不显示</div>
        </div>
        <div class="flex gap-3 text-right">
          <div>
            <div class="text-base font-semibold text-emerald-600">{{ summary.good }}</div>
            <div class="text-[10px] text-zinc-400">合格</div>
          </div>
          <div>
            <div class="text-base font-semibold text-rose-600">{{ summary.bad }}</div>
            <div class="text-[10px] text-zinc-400">不良</div>
          </div>
        </div>
      </div>
      <div class="mt-2 flex flex-wrap gap-1">
        <span
          v-for="s in STATUS_TABS"
          :key="s.v"
          class="cursor-pointer rounded-full border px-2 py-0.5 text-[11px]"
          :class="status === s.v ? 'border-indigo-500 text-indigo-600' : 'border-zinc-200 text-zinc-500'"
          @click="pickStatus(s.v)"
        >{{ s.label }}</span>
      </div>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-zinc-400">加载中...</div>

    <van-empty v-else-if="loaded && !items.length" description="暂无报工记录" />

    <div v-else class="mt-3 space-y-2">
      <div
        v-for="row in items"
        :key="row.id"
        class="rounded-xl bg-white p-3 shadow-sm active:bg-zinc-50"
        @click="openDetail(row.id)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium text-zinc-800">
              {{ row.task_code || `任务#${row.task_id}` }}
            </div>
            <div class="mt-1 text-[11px] text-zinc-500">
              第 {{ row.unit_seq }} 件 · {{ resultText(row.result_type) }}
              <span v-if="row.unit_label"> · {{ row.unit_label }}</span>
            </div>
            <div v-if="row.remark" class="mt-1 line-clamp-2 text-[11px] text-zinc-400">备注：{{ row.remark }}</div>
            <div class="mt-1 text-[10px] text-zinc-400">{{ fmtTime(row.submitted_at || row.created_at) }}</div>
          </div>
          <van-tag :type="statusType(row.status)" size="medium" class="shrink-0">
            {{ statusText(row.status) }}
          </van-tag>
        </div>
      </div>

      <div v-if="hasMore" class="pt-1 text-center">
        <van-button size="small" plain :loading="loadingMore" @click="load(false)">加载更多</van-button>
      </div>
      <div v-else-if="items.length" class="pt-1 text-center text-[10px] text-zinc-400">没有更多了</div>
    </div>

    <van-popup v-model:show="detailOpen" position="bottom" round class="pb-safe" :style="{ height: '78%' }">
      <div class="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div class="text-sm font-medium text-zinc-800">报工详情</div>
        <van-button size="mini" plain @click="detailOpen = false">关闭</van-button>
      </div>
      <div class="h-[calc(100%-49px)] overflow-y-auto px-4 py-3">
        <div v-if="detailLoading" class="py-8 text-center text-sm text-zinc-400">加载中...</div>
        <template v-else-if="detail">
          <div class="rounded-xl bg-zinc-50 p-3">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-zinc-800">
                  {{ detail.task_code || `任务#${detail.task_id}` }}
                </div>
                <div class="mt-1 text-[11px] text-zinc-500">
                  第 {{ detail.unit_seq }} 件 · {{ resultText(detail.result_type) }}
                </div>
              </div>
              <van-tag :type="statusType(detail.status)" size="medium">{{ statusText(detail.status) }}</van-tag>
            </div>
            <div class="mt-2 space-y-1 text-[11px] text-zinc-600">
              <div v-if="detail.product_code">产品：{{ detail.product_code }}</div>
              <div v-if="detail.unit_label">件号：{{ detail.unit_label }}</div>
              <div v-if="detail.piece_no">编号：{{ detail.piece_no }}</div>
              <div>提交：{{ fmtTime(detail.submitted_at || detail.created_at) || '—' }}</div>
              <div v-if="detail.remark">备注：{{ detail.remark }}</div>
            </div>
          </div>

          <div class="mt-3 text-[11px] font-medium text-zinc-700">审核轨迹</div>
          <div v-if="!detail.audits || !detail.audits.length" class="mt-1 text-[11px] text-zinc-400">
            还没有审核记录
          </div>
          <div v-else class="mt-1 space-y-2">
            <div v-for="a in detail.audits" :key="a.id" class="rounded-xl border border-zinc-100 p-2">
              <div class="flex items-center justify-between gap-2">
                <span
                  class="text-[11px] font-medium"
                  :class="a.action === 'reject' ? 'text-rose-600' : 'text-emerald-600'"
                >{{ auditTitle(a) }}</span>
                <span class="text-[10px] text-zinc-400">{{ fmtTime(a.created_at) }}</span>
              </div>
              <div v-if="a.reason" class="mt-1 whitespace-pre-wrap break-words text-[11px] text-zinc-600">
                原因：{{ a.reason }}
              </div>
            </div>
          </div>
        </template>
        <van-empty v-else description="没有找到这条记录" />
      </div>
    </van-popup>
  </div>
</template>
