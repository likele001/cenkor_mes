<template>
  <view class="emp-page">
    <view v-if="slip" class="emp-card emp-card--brand slip-card">
      <view class="slip-head">
        <text class="slip-month">{{ slip.month || month || '当月' }}</text>
        <text class="emp-tag" :class="signed ? 'ok' : 'warn'">{{ signed ? '已签收' : '待签收' }}</text>
      </view>
      <view class="slip-amount">
        <text class="amount-label">净额</text>
        <text class="amount-value">¥{{ slip.net_amount }}</text>
      </view>
      <view class="slip-detail">
        <view class="detail-row">
          <text class="d-label">基本工资</text>
          <text class="d-value">¥{{ slip.base_amount ?? '—' }}</text>
        </view>
        <view class="detail-row">
          <text class="d-label">补贴</text>
          <text class="d-value">¥{{ slip.allowance ?? '—' }}</text>
        </view>
        <view class="detail-row">
          <text class="d-label">扣除</text>
          <text class="d-value">¥{{ slip.deduction ?? '—' }}</text>
        </view>
      </view>
    </view>

    <view v-if="slip && !signed" class="emp-card sign-card">
      <text class="emp-section-title">签名确认</text>
      <SignaturePad @done="onSign" />
      <button class="emp-btn-outline reject-btn" @tap="reject">拒签</button>
    </view>

    <view v-if="!slip" class="emp-empty">
      <text class="emp-empty-icon">◌</text>
      暂无工资条
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import SignaturePad from '@/components/employee-ui/SignaturePad.vue'
import { getSalarySlip, rejectSalarySlip, signSalarySlip } from '@/api/h5/salary'
import { uploadFile } from '@/api/files'

const slip = ref<Record<string, unknown> | null>(null)
const month = ref('')
const signed = ref(false)

onLoad((q) => {
  if (q?.month) month.value = String(q.month)
  load()
})

async function load() {
  slip.value = (await getSalarySlip(month.value || undefined)) as Record<string, unknown>
  signed.value = slip.value?.confirm_status === 'signed'
}

async function onSign(path: string) {
  const up = await uploadFile(path, 'signature')
  const id = up.id ?? up.file_id
  if (id) {
    await signSalarySlip(month.value || (slip.value?.month as string), Number(id))
    uni.showToast({ title: '签名成功', icon: 'success' })
    load()
  }
}

function reject() {
  uni.showModal({
    title: '拒签',
    editable: true,
    placeholderText: '请输入拒签原因',
    success: async (r) => {
      if (r.confirm && r.content) {
        await rejectSalarySlip(month.value || '', r.content)
        load()
      }
    },
  })
}
</script>

<style scoped lang="scss">
.slip-card {
  padding: $space-6;
  border-radius: $radius-xl;
}
.slip-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-5;
}
.slip-month {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: rgba(255, 255, 255, 0.92);
}
.slip-amount {
  text-align: center;
  margin-bottom: $space-5;
}
.amount-label {
  display: block;
  font-size: $text-sm;
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: $space-1;
}
.amount-value {
  font-size: 64rpx;
  font-weight: $fw-bold;
  color: #fff;
  letter-spacing: -2rpx;
  font-variant-numeric: tabular-nums;
}
.slip-detail {
  background: rgba(255, 255, 255, 0.12);
  border-radius: $radius-md;
  padding: $space-4 $space-5;
  backdrop-filter: blur(8rpx);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: $space-1 0;
}
.d-label {
  font-size: $text-sm;
  color: rgba(255, 255, 255, 0.72);
}
.d-value {
  font-size: $text-sm;
  color: #fff;
  font-weight: $fw-semibold;
  font-variant-numeric: tabular-nums;
}

.sign-card {
  padding: $space-5;
}
.reject-btn {
  margin-top: $space-4;
  color: $danger;
  border-color: $danger-bg;
  &:active {
    background: $danger-bg;
  }
}
</style>
