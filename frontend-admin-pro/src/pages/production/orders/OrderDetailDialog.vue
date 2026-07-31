<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('production.orders.detailTitle')"
    width="900px"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    :append-to-body="true"
  >
    <div v-loading="loading">
      <el-descriptions v-if="data" :column="3" border>
        <el-descriptions-item label="ID">{{ data.id }}</el-descriptions-item>
        <el-descriptions-item :label="t('production.orders.code')">{{ data.code }}</el-descriptions-item>
        <el-descriptions-item label="客户">
          <span v-if="data.customer">{{ data.customer.name }}（{{ data.customer.code }}）</span>
          <span v-else>{{ t('production.common.customer') }}#{{ data.customer_id }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusLabel(data.status) }}</el-descriptions-item>
        <el-descriptions-item :label="t('production.orders.dueDate')">{{ data.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ data.confirmed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="data.opportunity_id" label="来源商机">
          <router-link :to="{ name: 'production-customer-detail', params: { id: data.customer_id }, query: { tab: 'opps' } }">
            {{ data.opportunity_code || `#${data.opportunity_id}` }}
          </router-link>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="data?.order_plan_locked"
        class="mt-3"
        type="warning"
        :closable="false"
        show-icon
        :title="t('production.orders.planLockedAlert')"
      />
      <el-table v-if="data" class="hidden lg:block mt-4 w-full" :data="data.items" border>
        <el-table-column prop="line_no" :label="t('production.orders.lineNo')" width="90" />
        <el-table-column v-if="data.status === 'confirmed' || data.status === 'producing'" :label="t('production.orders.lockedLabel')" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.locked" type="warning" size="small">{{ row.lock_reason || '锁定' }}</el-tag>
            <span v-else class="text-zinc-400">—</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('production.orders.productSku')" min-width="280">
          <template #default="{ row }">
            <template v-if="row.sku">
              <div class="font-medium">{{ row.sku.product_name || row.sku.name }}</div>
              <div class="text-xs text-zinc-500">{{ row.sku.sku_name || row.sku.display_label || row.sku.name }}</div>
            </template>
            <span v-else>{{ t('production.common.customer') }}#{{ row.sku_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="qty" :label="t('production.orders.quantityLabel')" width="110" />
        <el-table-column prop="remark" :label="t('production.common.remark')" min-width="240" />
      </el-table>
      <div v-if="data" class="lg:hidden space-y-3 mt-4">
        <div v-for="row in data.items" :key="row.line_no" class="admin-mobile-row">
          <div class="text-xs text-el-placeholder">行 {{ row.line_no }}</div>
          <div v-if="row.sku" class="text-sm">
            <div class="font-medium">{{ row.sku.product_name || row.sku.name }}</div>
            <div class="text-xs text-zinc-500">{{ row.sku.sku_name || row.sku.display_label }}</div>
          </div>
          <div v-else class="font-medium text-sm">{{ t('production.common.customer') }}#{{ row.sku_id }}</div>
          <dl class="admin-mobile-kv mt-2">
            <dt>数量</dt>
            <dd>{{ row.qty }}</dd>
            <dt>备注</dt>
            <dd class="text-left">{{ row.remark || '—' }}</dd>
          </dl>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button v-if="data" type="primary" @click="onPrint">{{ t('production.orders.print') }}</el-button>
      <el-button v-if="data" type="warning" @click="onExportPdf">{{ t('production.orders.exportPdf') }}</el-button>
      <el-button @click="$emit('update:modelValue', false)">{{ t('production.common.close') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { productionApi, type OrderDetailOut } from '@/api/production'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'

const props = defineProps<{
  modelValue: boolean
  orderId: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const { label: statusLabel } = useStatus('order')
const loading = ref(false)
const data = ref<OrderDetailOut | null>(null)

watch(
  () => props.modelValue,
  async (open) => {
    if (open && props.orderId) {
      loading.value = true
      data.value = null
      try {
        data.value = await productionApi.getOrder(props.orderId)
      } finally {
        loading.value = false
      }
    }
  }
)

async function onPrint() {
  if (!data.value) return
  const resp = await productionApi.printOrder(data.value.id, { template_code: 'order_detail' })
  const html = resp?.html || ''
  if (!html) return
  openPrintWindow(html, { title: `order_${data.value.id}`, autoPrint: true })
}

async function onExportPdf() {
  if (!data.value) return
  const res = await productionApi.exportOrderPdf(data.value.id, { template_code: 'order_detail' })
  const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = res.filename || `order_${data.value.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
</script>
