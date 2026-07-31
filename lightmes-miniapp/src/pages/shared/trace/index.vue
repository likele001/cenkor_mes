<template>
  <view class="trace-page">
    <view class="hero">
      <text class="hero-title">{{ t('trace.title') }}</text>
      <text class="hero-sub">{{ t('trace.subtitle') }}</text>
    </view>

    <view class="search-box">
      <input v-model="codeInput" class="input" :placeholder="t('trace.codePlaceholder')" />
      <button class="btn" @tap="load">{{ t('trace.queryBtn') }}</button>
    </view>

    <view v-if="loading" class="empty">{{ t('trace.loading') }}</view>
    <template v-else-if="detail">
      <view class="card">
        <text class="code">{{ detail.product_code }}</text>
        <text v-if="detail.piece_no" class="sub">{{ t('trace.pieceNo', { n: detail.piece_no }) }}</text>
        <view class="kv"><text class="k">{{ t('trace.product') }}</text><text class="v">{{ detail.product_name || '—' }}</text></view>
        <view class="kv"><text class="k">{{ t('trace.sku') }}</text><text class="v">{{ detail.sku_code }} {{ detail.sku_name }}</text></view>
        <view class="kv"><text class="k">{{ t('trace.order') }}</text><text class="v">{{ detail.order_name || detail.order_code || '—' }}</text></view>
        <view v-if="detail.customer_name" class="kv"><text class="k">{{ t('trace.customer') }}</text><text class="v">{{ detail.customer_name }}</text></view>
      </view>

      <view v-if="detail.flow_steps?.length" class="card">
        <text class="section">{{ t('trace.flowSteps') }}</text>
        <view v-for="(step, idx) in detail.flow_steps" :key="idx" class="step">
          <text class="step-name">{{ step.process_name || '—' }}</text>
          <text class="step-meta">{{ fmtTime(step.time) }} · {{ step.operator || '—' }}</text>
        </view>
      </view>

      <view v-if="detail.media?.length" class="card">
        <text class="section">{{ t('trace.media') }}</text>
        <view class="media-grid">
          <template v-for="m in detail.media" :key="m.id">
            <image
              v-if="m.kind === 'image'"
              class="media-img"
              :src="mediaSrc(m)"
              mode="aspectFill"
              @tap="preview(m)"
            />
          </template>
        </view>
      </view>
    </template>
    <view v-else-if="queried" class="empty">{{ t('trace.notFound') }}</view>
    <view v-else class="empty">{{ t('trace.enterCode') }}</view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useI18n } from 'vue-i18n'
import { getPublicTrace, publicTraceMediaUrl, type PublicTraceDetail, type PublicTraceMedia } from '@/api/h5/publicTrace'
import { useCustomerLocale } from '@/composables/useCustomerLocale'

const { t } = useI18n()
const { setNavTitle } = useCustomerLocale()

const codeInput = ref('')
const traceCode = ref('')
const loading = ref(false)
const queried = ref(false)
const detail = ref<PublicTraceDetail | null>(null)

function fmtTime(v: string | null | undefined) {
  if (!v) return '—'
  return String(v).slice(0, 19).replace('T', ' ')
}

function mediaSrc(m: PublicTraceMedia) {
  return publicTraceMediaUrl(m.id, traceCode.value, m.url)
}

function preview(m: PublicTraceMedia) {
  const url = mediaSrc(m)
  uni.previewImage({ urls: [url] })
}

async function load() {
  const code = codeInput.value.trim()
  if (!code) {
    uni.showToast({ title: t('trace.enterCode'), icon: 'none' })
    return
  }
  traceCode.value = code
  loading.value = true
  queried.value = true
  detail.value = null
  try {
    detail.value = await getPublicTrace(code)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

onLoad((q) => {
  const c = (q?.code || q?.id || '') as string
  if (c) {
    codeInput.value = c
    load()
  }
})

onShow(() => setNavTitle('trace.title'))
</script>

<style scoped lang="scss">
.trace-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #e0e7ff, #f8fafc);
  padding-bottom: 40rpx;
}
.hero {
  padding: 48rpx 32rpx 32rpx;
  text-align: center;
  color: #312e81;
}
.hero-title {
  font-size: 40rpx;
  font-weight: 800;
  display: block;
}
.hero-sub {
  margin-top: 12rpx;
  font-size: 24rpx;
  opacity: 0.85;
  display: block;
}
.search-box {
  display: flex;
  gap: 16rpx;
  padding: 0 24rpx 24rpx;
}
.input {
  flex: 1;
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
}
.btn {
  background: #4f46e5;
  color: #fff;
  border-radius: 12rpx;
  font-size: 28rpx;
  padding: 0 28rpx;
}
.card {
  background: #fff;
  margin: 0 24rpx 24rpx;
  border-radius: 20rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(79, 70, 229, 0.08);
}
.code {
  font-family: monospace;
  font-size: 32rpx;
  font-weight: 700;
  color: #4338ca;
  word-break: break-all;
}
.sub {
  display: block;
  margin-top: 8rpx;
  color: #64748b;
  font-size: 24rpx;
}
.kv {
  display: flex;
  margin-top: 12rpx;
  font-size: 26rpx;
}
.k {
  width: 120rpx;
  color: #64748b;
  flex-shrink: 0;
}
.v {
  flex: 1;
}
.section {
  font-weight: 600;
  display: block;
  margin-bottom: 16rpx;
}
.step {
  padding: 12rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}
.step-name {
  font-weight: 600;
  display: block;
}
.step-meta {
  font-size: 22rpx;
  color: #94a3b8;
}
.media-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.media-img {
  width: 200rpx;
  height: 200rpx;
  border-radius: 12rpx;
}
.empty {
  text-align: center;
  color: #94a3b8;
  padding: 80rpx 40rpx;
}
</style>
