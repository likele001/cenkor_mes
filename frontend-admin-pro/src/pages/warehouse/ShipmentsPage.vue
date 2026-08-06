<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { http } from '@/utils/http'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()

interface ShipmentItem {
  sku_id: number
  sku_code: string | null
  sku_name: string | null
  qty: number
}

interface Shipment {
  id: number
  order_id: number
  order_code: string | null
  code: string
  logistics_company: string | null
  logistics_no: string | null
  status: string
  shipped_at: string | null
  signed_at: string | null
  remark: string | null
  items: ShipmentItem[]
  created_at: string | null
}

const loading = ref(false)
const items = ref<Shipment[]>([])
const dialogVisible = ref(false)
const editMode = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)
const detail = ref<Shipment | null>(null)
const detailVisible = ref(false)

const form = ref({
  order_id: null as number | null,
  code: '',
  logistics_company: '',
  logistics_no: '',
  remark: '',
  items: [] as { sku_id: number; qty: number }[],
})

const { label: statusLabel, type: statusTagType } = useStatus('shipment')

async function load() {
  loading.value = true
  try {
    const data = await http.get<{ items: Shipment[] }>('/admin/warehouse/shipments')
    items.value = (data.items || []) as Shipment[]
  } catch { items.value = [] } finally { loading.value = false }
}

function resetForm() {
  form.value = { order_id: null, code: '', logistics_company: '', logistics_no: '', remark: '', items: [] }
  editId.value = null
  editMode.value = false
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function addItem() {
  form.value.items.push({ sku_id: 0, qty: 1 })
}

function removeItem(idx: number) {
  form.value.items.splice(idx, 1)
}

async function save() {
  if (!form.value.code.trim()) { ElMessage.warning(t('warehouse.shipments.codeRequired')); return }
  if (!form.value.items.length) { ElMessage.warning(t('warehouse.shipments.itemsRequired')); return }
  saving.value = true
  try {
    await http.post('/admin/warehouse/shipments', form.value)
    ElMessage.success(t('warehouse.shipments.createSuccess'))
    dialogVisible.value = false
    await load()
  } catch { ElMessage.error(t('warehouse.shipments.saveFailed')) } finally { saving.value = false }
}

async function shipOut(row: Shipment) {
  try {
    await ElMessageBox.confirm(t('warehouse.shipments.confirmShip', { code: row.code }), t('warehouse.shipments.confirm'), { type: 'warning' })
    await http.post(`/admin/warehouse/shipments/${row.id}/ship`)
    ElMessage.success(t('warehouse.shipments.shippedSuccess'))
    await load()
  } catch { /* cancel */ }
}

async function sign(row: Shipment) {
  try {
    await http.post(`/admin/warehouse/shipments/${row.id}/sign`)
    ElMessage.success(t('warehouse.shipments.signedSuccess'))
    await load()
  } catch { ElMessage.error(t('warehouse.shipments.operationFailed')) }
}

function viewDetail(row: Shipment) {
  detail.value = row
  detailVisible.value = true
}

onMounted(load)
</script>

<template>
  <AdminPage :title="t('warehouse.shipments.title')">
    <template #actions>
      <el-button type="primary" @click="openCreate">{{ t('warehouse.shipments.createNew') }}</el-button>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table class="hidden lg:block w-full" :data="items" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="code" :label="t('warehouse.shipments.code')" width="160" />
        <el-table-column :label="t('warehouse.shipments.order')" width="130">
          <template #default="{ row }">{{ row.order_code || row.order_id }}</template>
        </el-table-column>
        <el-table-column prop="logistics_company" :label="t('warehouse.shipments.logistics')" width="120" />
        <el-table-column prop="logistics_no" :label="t('warehouse.shipments.trackingNo')" width="150" />
        <el-table-column :label="t('warehouse.shipments.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('warehouse.shipments.items')" min-width="200">
          <template #default="{ row }">
            <div v-for="it in row.items" :key="it.sku_id" class="text-xs">
              {{ it.sku_code || `#${it.sku_id}` }} x {{ it.qty }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="shipped_at" :label="t('warehouse.shipments.shippedAt')" width="160" />
        <el-table-column :label="t('warehouse.shipments.actions')" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">{{ t('warehouse.shipments.detail') }}</el-button>
            <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="shipOut(row)">
              {{ t('warehouse.shipments.ship') }}
            </el-button>
            <el-button v-if="row.status === 'shipped'" size="small" type="success" @click="sign(row)">
              {{ t('warehouse.shipments.sign') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="font-semibold">{{ row.code }}</div>
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </div>
          <dl class="admin-mobile-kv">
            <dt>{{ t('warehouse.shipments.order') }}</dt><dd>{{ row.order_code || row.order_id }}</dd>
            <dt>{{ t('warehouse.shipments.logistics') }}</dt><dd>{{ row.logistics_company || '—' }} {{ row.logistics_no || '' }}</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" @click="viewDetail(row)">{{ t('warehouse.shipments.detail') }}</el-button>
            <el-button v-if="row.status === 'pending'" size="small" type="primary" @click="shipOut(row)">{{ t('warehouse.shipments.ship') }}</el-button>
            <el-button v-if="row.status === 'shipped'" size="small" type="success" @click="sign(row)">{{ t('warehouse.shipments.sign') }}</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" :description="t('warehouse.shipments.empty')" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="t('warehouse.shipments.createTitle')" width="600px">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="订单ID" required>
              <el-input-number v-model="form.order_id" :min="1" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('warehouse.shipments.code')" required>
              <el-input v-model="form.code" :placeholder="t('warehouse.shipments.codePlaceholder')" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="t('warehouse.shipments.logisticsCompany')">
              <el-input v-model="form.logistics_company" :placeholder="t('warehouse.shipments.logisticsCompanyPlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('warehouse.shipments.trackingNo')">
              <el-input v-model="form.logistics_no" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="t('warehouse.shipments.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider>{{ t('warehouse.shipments.shipmentDetails') }}</el-divider>
        <div v-for="(it, idx) in form.items" :key="idx" class="flex items-center gap-2 mb-2">
          <el-input-number v-model="it.sku_id" :min="1" :placeholder="t('warehouse.shipments.skuIdPlaceholder')" style="width:120px" />
          <span class="text-xs text-zinc-400">×</span>
          <el-input-number v-model="it.qty" :min="1" style="width:100px" />
          <el-button size="small" type="danger" text @click="removeItem(idx)">{{ t('warehouse.shipments.delete') }}</el-button>
        </div>
        <el-button size="small" @click="addItem">+ {{ t('warehouse.shipments.addDetail') }}</el-button>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('warehouse.shipments.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('warehouse.shipments.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" :title="t('warehouse.shipments.detailTitle')" width="500px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('warehouse.shipments.code')">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item :label="t('warehouse.shipments.order')">{{ detail.order_code }}</el-descriptions-item>
          <el-descriptions-item :label="t('warehouse.shipments.logistics')">{{ detail.logistics_company || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('warehouse.shipments.trackingNo')">{{ detail.logistics_no || '—' }}</el-descriptions-item>
          <el-descriptions-item :label="t('warehouse.shipments.status')">
            <el-tag :type="statusTagType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('warehouse.shipments.shippedAt')">{{ detail.shipped_at || '—' }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="mt-3 mb-2 font-medium">{{ t('warehouse.shipments.shipmentDetails') }}</h4>
        <el-table :data="detail.items" size="small" border>
          <el-table-column prop="sku_code" :label="t('warehouse.shipments.skuCode')" />
          <el-table-column prop="sku_name" :label="t('warehouse.shipments.skuName')" />
          <el-table-column prop="qty" :label="t('warehouse.shipments.quantity')" width="80" />
        </el-table>
        <p v-if="detail.remark" class="mt-2 text-sm text-zinc-500">{{ t('warehouse.shipments.remarkLabel') }}{{ detail.remark }}</p>
      </template>
    </el-dialog>
  </AdminPage>
</template>
