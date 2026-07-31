<template>
  <view class="emp-page">
    <view v-if="slip" class="emp-card">
      <text>净额 ¥{{ slip.net_amount }}</text>
      <text class="sub">状态 {{ slip.confirm_status }}</text>
      <SignaturePad v-if="!signed" @done="onSign" />
      <button v-if="!signed" class="link" @tap="reject">拒签</button>
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
    placeholderText: '原因',
    success: async (r) => {
      if (r.confirm && r.content) {
        await rejectSalarySlip(month.value || '', r.content)
        load()
      }
    },
  })
}
</script>

<style scoped>
.sub {
  display: block;
  color: #64748b;
  margin: 12rpx 0 24rpx;
}
.link {
  background: transparent;
  color: #ef4444;
}
</style>
