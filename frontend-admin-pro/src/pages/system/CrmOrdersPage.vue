<template>
  <AdminPage
    :title="t('system.crmOrders.title')"
    :subtitle="t('system.crmOrders.subtitle')"
  >
    <template #extra>
      <el-button type="primary" :icon="Refresh" @click="load">{{ t('system.crmOrders.refresh') }}</el-button>
    </template>

    <el-alert
      v-if="!configured"
      type="warning"
      :closable="false"
      show-icon
      :title="t('system.crmOrders.configMissing')"
      style="margin-bottom: 16px"
    />

    <el-table v-loading="loading" :data="orders" border stripe empty-text="暂无 CRM 推送订单">
      <el-table-column prop="order_code" :label="t('system.crmOrders.orderCode')" min-width="160" />
      <el-table-column prop="customer_name" :label="t('system.crmOrders.customer')" min-width="160" />
      <el-table-column prop="delivery_date" :label="t('system.crmOrders.delivery')" width="130" />
      <el-table-column :label="t('system.crmOrders.items')" min-width="220">
        <template #default="{ row }">
          <el-popover trigger="hover" placement="top" :width="320">
            <template #default>
              <div v-for="(it, i) in row.items" :key="i" style="padding: 2px 0">
                {{ it.product_name }} <span style="color:#999">（{{ it.spec || '-' }}）</span>
                × {{ it.quantity }}
              </div>
            </template>
            <template #reference>
              <span>{{ row.items?.length || 0 }} 项</span>
            </template>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column label="MES 工单" min-width="200">
        <template #default="{ row }">
          <span v-if="row.mes_order_id" style="color:#67c23a">已关联 #{{ row.mes_order_id }}</span>
          <span v-else style="color:#909399">未关联</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('system.crmOrders.status')" width="200">
        <template #default="{ row }">
          <el-select
            :model-value="row.status"
            size="small"
            style="width: 150px"
            @change="(val: string) => onChangeStatus(row, val)"
          >
            <el-option
              v-for="opt in STATUS_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
            <el-option v-if="!knownStatus(row.status)" :label="row.status" :value="row.status" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" :label="t('system.crmOrders.updatedAt')" min-width="170" />
    </el-table>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import AdminPage from '@/components/admin/AdminPage.vue'
import { crmAdapterApi, type CrmInboundOrder } from '@/api/crm-adapter'

const { t } = useI18n()

const STATUS_OPTIONS = [
  { value: 'pending', label: t('system.crmOrders.stPending') },
  { value: 'producing', label: t('system.crmOrders.stProducing') },
  { value: 'part_done', label: t('system.crmOrders.stPartDone') },
  { value: 'completed', label: t('system.crmOrders.stCompleted') },
  { value: 'cancelled', label: t('system.crmOrders.stCancelled') },
]

const orders = ref<CrmInboundOrder[]>([])
const loading = ref(false)
const configured = ref(true)

function knownStatus(s: string) {
  return STATUS_OPTIONS.some((o) => o.value === s)
}

async function load() {
  loading.value = true
  try {
    orders.value = await crmAdapterApi.listOrders()
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
  try {
    const cfg = await crmAdapterApi.getConfig()
    configured.value = !!cfg.configured
  } catch {
    configured.value = false
  }
}

async function onChangeStatus(row: CrmInboundOrder, val: string) {
  try {
    const res = await crmAdapterApi.updateOrderStatus(row.order_code, val)
    row.status = val
    if (res.notified) {
      ElMessage.success(t('system.crmOrders.syncedToCrm'))
    } else {
      ElMessage.warning(t('system.crmOrders.syncFailed'))
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败')
    await load()
  }
}

onMounted(load)
</script>
