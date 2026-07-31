<template>
  <view class="adm-page">
    <view class="hero">
      <text class="hero-title">AI 深度分析</text>
      <text class="hero-sub">规则/统计基础版 · 近 30～90 日报工与设备点检</text>
      <button class="btn ghost" size="mini" :loading="loading" @tap="load">刷新</button>
    </view>

    <view v-if="loading && !data" class="tip">加载中...</view>

    <view v-if="causalRows.length" class="card">
      <text class="card-title">因果分析（工序不良率）</text>
      <view v-for="(row, i) in causalRows" :key="'c' + i" class="row">
        <text class="row-main">工序 #{{ row.process_id }} · 不良率 {{ formatBadRate(row.bad_rate) }}</text>
        <text class="row-sub">样本 {{ row.sample_size ?? 0 }} · {{ row.hypothesis || '—' }}</text>
      </view>
    </view>

    <view v-if="geneRows.length" class="card">
      <text class="card-title">质量基因库</text>
      <view v-for="(row, i) in geneRows" :key="'g' + i" class="row">
        <text class="row-main">{{ row.tag }} · {{ row.count }} 次</text>
        <text class="row-sub">{{ row.sample_remarks?.[0] || '—' }}</text>
      </view>
    </view>

    <view v-if="workshopRows.length" class="card">
      <text class="card-title">数字孪生快照</text>
      <text v-if="twinAsOf" class="hint">截至 {{ twinAsOf }}</text>
      <view v-for="(row, i) in workshopRows" :key="'w' + i" class="row">
        <text class="row-main">{{ row.workshop }}</text>
        <text class="row-sub">待开始 {{ row.pending ?? 0 }} · 进行中 {{ row.working ?? 0 }} · 合计 {{ row.total ?? 0 }}</text>
      </view>
    </view>

    <view v-if="equipmentRows.length" class="card">
      <text class="card-title">设备健康评分</text>
      <view v-for="(row, i) in equipmentRows" :key="'e' + i" class="row">
        <text class="row-main">{{ row.name || row.code }} · 健康分 {{ row.health_score ?? '—' }}</text>
        <text class="row-sub">{{ row.suggestion || '—' }}</text>
      </view>
    </view>

    <view v-if="!loading && !hasData" class="tip">暂无分析数据</view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { aiAdminApi } from '@/api/admin/ai'

type CauseRow = { process_id?: number; bad_rate?: number; sample_size?: number; hypothesis?: string }
type GeneRow = { tag?: string; count?: number; sample_remarks?: string[] }
type WorkshopRow = { workshop?: string; pending?: number; working?: number; total?: number }
type EquipmentRow = { code?: string; name?: string; health_score?: number; suggestion?: string }

const loading = ref(false)
const data = ref<Record<string, unknown> | null>(null)

const causalRows = computed(() => ((data.value?.causal as { causes?: CauseRow[] })?.causes) || [])
const geneRows = computed(() => ((data.value?.quality_genes as { genes?: GeneRow[] })?.genes) || [])
const workshopRows = computed(() => ((data.value?.digital_twin as { workshops?: WorkshopRow[] })?.workshops) || [])
const equipmentRows = computed(() => ((data.value?.equipment_health as { items?: EquipmentRow[] })?.items) || [])
const twinAsOf = computed(() => (data.value?.digital_twin as { as_of?: string })?.as_of || '')
const hasData = computed(
  () => causalRows.value.length + geneRows.value.length + workshopRows.value.length + equipmentRows.value.length > 0,
)

function formatBadRate(v: unknown) {
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(2)}%`
}

async function load() {
  loading.value = true
  try {
    data.value = await aiAdminApi.deepOverview()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.hero { padding: 24rpx; }
.hero-title { display: block; font-size: 34rpx; font-weight: 700; }
.hero-sub { display: block; font-size: 24rpx; color: #64748b; margin: 8rpx 0 16rpx; }
.tip { padding: 24rpx; text-align: center; color: #94a3b8; font-size: 26rpx; }
.card { background: #fff; border-radius: 16rpx; margin: 0 24rpx 20rpx; padding: 24rpx; }
.card-title { display: block; font-size: 28rpx; font-weight: 600; margin-bottom: 16rpx; }
.row { padding: 12rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.row-main { display: block; font-size: 26rpx; color: #334155; }
.row-sub { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }
.hint { display: block; font-size: 22rpx; color: #94a3b8; margin-bottom: 12rpx; }
.btn.ghost { background: #f1f5f9; color: #475569; }
</style>
