<template>
  <AdminPage :title="t('purchase.orderDetail.title')" :description="item?.code || ''">
    <el-card v-loading="loading">
          <template #actions>
      <div class="flex items-center gap-2">
          <el-button @click="router.back()">{{ t('purchase.orderDetail.back') }}</el-button>
          <el-button v-if="item" type="primary" @click="onPrint">{{ t('purchase.orderDetail.print') }}</el-button>
          <el-button v-if="item" type="warning" @click="onExportPdf">{{ t('purchase.orderDetail.exportPdf') }}</el-button>
          <el-button v-if="canConfirm" type="warning" :loading="confirming" @click="onConfirm">{{ t('purchase.orderDetail.confirm') }}</el-button>
          <el-button v-if="canReceive" type="primary" @click="openReceive">{{ t('purchase.orderDetail.receive') }}</el-button>
          <el-button v-if="canReturn" type="danger" plain @click="openReturn">{{ t('purchase.orderDetail.return') }}</el-button>
          <el-popconfirm v-if="canCancel" :title="t('purchase.orderDetail.cancelConfirm')" @confirm="onCancel">
            <template #reference>
              <el-button type="danger" :loading="canceling">{{ t('purchase.orderDetail.cancel') }}</el-button>
            </template>
          </el-popconfirm>
        </div>
    </template>


      <el-descriptions class="mt-4" :column="3" border v-if="item">
        <el-descriptions-item :label="t('purchase.orderDetail.code')">{{ item.code }}</el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.supplier')">{{ item.supplier_name || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.status')">
          <el-tag :type="statusTagType(item.status)">{{ statusLabel(item.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.remark')" :span="3">{{ item.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.confirmedAt')">{{ item.confirmed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.createdAt')">{{ item.created_at }}</el-descriptions-item>
        <el-descriptions-item :label="t('purchase.orderDetail.updatedAt')">{{ item.updated_at }}</el-descriptions-item>
      </el-descriptions>

      <div class="mt-4 font-medium">{{ t('purchase.orderDetail.detail') }}</div>
      <el-table class="hidden lg:block mt-2 w-full" :data="item?.items || []" border>
        <el-table-column prop="material_code" :label="t('purchase.orderDetail.materialCode')" width="180" />
        <el-table-column prop="material_name" :label="t('purchase.orderDetail.materialName')" min-width="220" />
        <el-table-column prop="qty" :label="t('purchase.orderDetail.purchaseQty')" width="100" />
        <el-table-column prop="received_qty" :label="t('purchase.orderDetail.received')" width="100" />
        <el-table-column prop="returned_qty" :label="t('purchase.orderDetail.returned')" width="100" />
        <el-table-column :label="t('purchase.orderDetail.remainQty')" width="100">
          <template #default="{ row }">
            <span>{{ remainQty(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit_price" :label="t('purchase.orderDetail.unitPrice')" width="100" />
        <el-table-column prop="remark" :label="t('purchase.orderDetail.remark')" min-width="140" />
      </el-table>
      <div class="lg:hidden space-y-3 mt-2">
        <div v-for="(row, idx) in item?.items || []" :key="idx" class="admin-mobile-row">
          <div class="font-medium text-sm">{{ row.material_code }} {{ row.material_name }}</div>
          <dl class="admin-mobile-kv mt-2">
            <dt>{{ t('purchase.orderDetail.purchase') }}</dt>
            <dd>{{ row.qty }}</dd>
            <dt>{{ t('purchase.orderDetail.receivedShort') }}</dt>
            <dd>{{ row.received_qty }}</dd>
            <dt>{{ t('purchase.orderDetail.returnedShort') }}</dt>
            <dd>{{ row.returned_qty }}</dd>
            <dt>{{ t('purchase.orderDetail.remain') }}</dt>
            <dd>{{ remainQty(row) }}</dd>
            <dt>{{ t('purchase.orderDetail.unitPrice') }}</dt>
            <dd>{{ row.unit_price }}</dd>
            <dt>{{ t('purchase.orderDetail.remark') }}</dt>
            <dd class="text-left">{{ row.remark || '—' }}</dd>
          </dl>
        </div>
      </div>
    </el-card>

    <!-- 入库弹窗 -->
    <el-dialog v-model="recv.open" :title="t('purchase.orderDetail.receiveTitle')" width="920px" destroy-on-close>
      <el-form :model="recv.form" label-width="80px">
        <el-form-item :label="t('purchase.orderDetail.warehouse')">
          <el-select v-model="recv.form.warehouse_id" filterable :placeholder="t('purchase.orderDetail.selectWarehouse')" style="width: 420px">
            <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
          </el-select>
          <el-input-number v-model="recv.form.warehouse_id" :min="1" :controls="false" style="width: 180px; margin-left: 8px" />
        </el-form-item>
      </el-form>

      <el-table class="hidden lg:block w-full" :data="recv.form.items" border>
        <el-table-column :label="t('purchase.orderDetail.material')" min-width="320">
          <template #default="{ row }">
            <div class="font-medium">{{ row.material_code || '-' }}</div>
            <div class="text-xs text-zinc-500">{{ row.material_name || '' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="qty" :label="t('purchase.orderDetail.purchase')" width="110" />
        <el-table-column prop="received_qty" :label="t('purchase.orderDetail.received')" width="110" />
        <el-table-column :label="t('purchase.orderDetail.remain')" width="110">
          <template #default="{ row }">
            <span>{{ remainQty(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('purchase.orderDetail.batchNo')" width="120">
          <template #default="{ row }">
            <el-input v-model="row.batch_no" :placeholder="t('purchase.orderDetail.batchPlaceholder')" size="small" style="width:100px" />
          </template>
        </el-table-column>
        <el-table-column :label="t('purchase.orderDetail.receiveQty')" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.receive_qty"
              :min="0"
              :max="remainQty(row)"
              :disabled="remainQty(row) <= 0"
              :controls="false"
              style="width: 100%"
            />
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-3 mt-2">
        <div v-for="(row, idx) in recv.form.items" :key="idx" class="admin-mobile-row">
          <div class="font-medium">{{ row.material_code || '-' }}</div>
          <div class="text-xs text-zinc-500">{{ row.material_name || '' }}</div>
          <dl class="admin-mobile-kv mt-2">
            <dt>{{ t('purchase.orderDetail.purchase') }}</dt>
            <dd>{{ row.qty }}</dd>
            <dt>{{ t('purchase.orderDetail.receivedShort') }}</dt>
            <dd>{{ row.received_qty }}</dd>
            <dt>{{ t('purchase.orderDetail.remain') }}</dt>
            <dd>{{ remainQty(row) }}</dd>
          </dl>
          <div class="mt-2 text-sm text-el-regular">{{ t('purchase.orderDetail.receiveQty') }}</div>
          <el-input-number
            v-model="row.receive_qty"
            :min="0"
            :max="remainQty(row)"
            :disabled="remainQty(row) <= 0"
            :controls="false"
            class="w-full"
            style="width: 100%"
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="recv.open = false">{{ t('purchase.orderDetail.cancel') }}</el-button>
        <el-button type="primary" :loading="recv.saving" @click="onReceive">{{ t('purchase.orderDetail.submitReceive') }}</el-button>
      </template>
    </el-dialog>

    <!-- 退货弹窗 -->
    <el-dialog v-model="ret.open" :title="t('purchase.orderDetail.returnTitle')" width="920px" destroy-on-close>
      <el-form :model="ret.form" label-width="80px">
        <el-form-item :label="t('purchase.orderDetail.outWarehouse')">
          <el-select v-model="ret.form.warehouse_id" filterable :placeholder="t('purchase.orderDetail.selectOutWarehouse')" style="width: 420px">
            <el-option v-for="w in warehouses" :key="w.id" :label="partyOptionLabel(w)" :value="w.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table class="hidden lg:block w-full" :data="ret.form.items" border>
        <el-table-column :label="t('purchase.orderDetail.material')" min-width="320">
          <template #default="{ row }">
            <div class="font-medium">{{ row.material_code || '-' }}</div>
            <div class="text-xs text-zinc-500">{{ row.material_name || '' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="qty" :label="t('purchase.orderDetail.purchase')" width="90" />
        <el-table-column prop="received_qty" :label="t('purchase.orderDetail.received')" width="90" />
        <el-table-column prop="returned_qty" :label="t('purchase.orderDetail.returned')" width="90" />
        <el-table-column :label="t('purchase.orderDetail.returnable')" width="90">
          <template #default="{ row }">
            <span>{{ maxReturnQty(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('purchase.orderDetail.returnQty')" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.return_qty"
              :min="0"
              :max="maxReturnQty(row)"
              :disabled="maxReturnQty(row) <= 0"
              :controls="false"
              style="width: 100%"
            />
          </template>
        </el-table-column>
      </el-table>
      <div class="lg:hidden space-y-3 mt-2">
        <div v-for="(row, idx) in ret.form.items" :key="idx" class="admin-mobile-row">
          <div class="font-medium">{{ row.material_code || '-' }}</div>
          <div class="text-xs text-zinc-500">{{ row.material_name || '' }}</div>
          <dl class="admin-mobile-kv mt-2">
            <dt>{{ t('purchase.orderDetail.purchase') }}</dt>
            <dd>{{ row.qty }}</dd>
            <dt>{{ t('purchase.orderDetail.receivedShort') }}</dt>
            <dd>{{ row.received_qty }}</dd>
            <dt>{{ t('purchase.orderDetail.returnedShort') }}</dt>
            <dd>{{ row.returned_qty }}</dd>
            <dt>{{ t('purchase.orderDetail.returnable') }}</dt>
            <dd>{{ maxReturnQty(row) }}</dd>
          </dl>
          <div class="mt-2 text-sm">{{ t('purchase.orderDetail.returnQty') }}</div>
          <el-input-number
            v-model="row.return_qty"
            :min="0"
            :max="maxReturnQty(row)"
            :disabled="maxReturnQty(row) <= 0"
            :controls="false"
            style="width: 100%"
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="ret.open = false">{{ t('purchase.orderDetail.cancel') }}</el-button>
        <el-button type="danger" :loading="ret.saving" @click="onReturn">{{ t('purchase.orderDetail.submitReturn') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { purchaseApi, type PurchaseOrderOut, type WarehouseOut } from '@/api/purchase'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'
import { partyOptionLabel } from '@/utils/display'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()

type ReceiveRow = {
  item_id: number
  material_code: string | null
  material_name: string | null
  qty: number
  received_qty: number
  receive_qty: number
  batch_no: string
}

type ReturnRow = {
  item_id: number
  material_code: string | null
  material_name: string | null
  qty: number
  received_qty: number
  returned_qty: number
  return_qty: number
}

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const item = ref<PurchaseOrderOut | null>(null)
const confirming = ref(false)
const canceling = ref(false)
const warehouses = ref<WarehouseOut[]>([])

const recv = reactive({
  open: false,
  saving: false,
  form: { warehouse_id: 0, items: [] as ReceiveRow[] },
})

const ret = reactive({
  open: false,
  saving: false,
  form: { warehouse_id: 0, items: [] as ReturnRow[] },
})

const id = computed(() => Number(route.params.id))

const { label: statusLabel, type: statusTagType } = useStatus('purchase_order')

function remainQty(x: { qty: number; received_qty: number; returned_qty?: number }) {
  return Math.max(0, Number(x.qty) - (Number(x.received_qty) - Number(x.returned_qty || 0)))
}

function maxReturnQty(x: { received_qty: number; returned_qty: number }) {
  return Math.max(0, Number(x.received_qty) - Number(x.returned_qty))
}

const canConfirm = computed(() => item.value?.status === 'draft')
const canReceive = computed(() => item.value?.status === 'confirmed' || item.value?.status === 'partial_received')
const canReturn = computed(() => item.value?.status === 'partial_received' || item.value?.status === 'received')
const canCancel = computed(() => {
  const s = item.value?.status
  return s === 'draft' || s === 'confirmed' || s === 'partial_received'
})

async function loadWarehouses() {
  try {
    const res = await purchaseApi.listWarehouses()
    warehouses.value = res.items
    if (warehouses.value.length && !recv.form.warehouse_id) recv.form.warehouse_id = warehouses.value[0].id
  } catch {
    warehouses.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    item.value = await purchaseApi.getOrder(id.value)
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  if (!item.value) return
  confirming.value = true
  try {
    item.value = await purchaseApi.confirmOrder(item.value.id)
    ElMessage.success(t('purchase.orderDetail.confirmedSuccess'))
  } finally {
    confirming.value = false
  }
}

async function onCancel() {
  if (!item.value) return
  canceling.value = true
  try {
    item.value = await purchaseApi.cancelOrder(item.value.id)
    ElMessage.success(t('purchase.orderDetail.canceledSuccess'))
  } finally {
    canceling.value = false
  }
}

async function onPrint() {
  if (!item.value) return
  const resp = await purchaseApi.printOrder(item.value.id, { template_code: 'purchase_order' })
  const html = resp?.html || ''
  if (!html) return
  openPrintWindow(html, { title: `purchase_order_${item.value.id}`, autoPrint: true })
}

async function onExportPdf() {
  if (!item.value) return
  const res = await purchaseApi.exportOrderPdf(item.value.id, { template_code: 'purchase_order' })
  const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = res.filename || `purchase_order_${item.value.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function openReceive() {
  if (!item.value) return
  recv.form.items = item.value.items.map((x) => {
    const remain = remainQty(x)
    return {
      item_id: x.id,
      material_code: x.material_code,
      material_name: x.material_name,
      qty: x.qty,
      received_qty: x.received_qty,
      receive_qty: remain,
      batch_no: '',
    }
  })
  recv.open = true
  loadWarehouses()
}

async function onReceive() {
  if (!item.value) return
  const whId = Number(recv.form.warehouse_id || 0)
  if (!whId || whId < 1) {
    ElMessage.error(t('purchase.orderDetail.selectWarehouseError'))
    return
  }
  const rows = recv.form.items
    .map((x) => ({ ...x, receive_qty: Number(x.receive_qty || 0) }))
    .filter((x) => x.receive_qty > 0)
    .map((x) => ({ item_id: x.item_id, receive_qty: x.receive_qty, batch_no: x.batch_no?.trim() || undefined }))
  if (rows.length === 0) {
    ElMessage.error(t('purchase.orderDetail.inputReceiveQty'))
    return
  }

  recv.saving = true
  try {
    item.value = await purchaseApi.receiveOrder(item.value.id, { warehouse_id: whId, items: rows })
    recv.open = false
    ElMessage.success(t('purchase.orderDetail.receiveSuccess'))
  } finally {
    recv.saving = false
  }
}

function openReturn() {
  if (!item.value) return
  ret.form.items = item.value.items.map((x) => {
    const maxRet = maxReturnQty(x)
    return {
      item_id: x.id,
      material_code: x.material_code,
      material_name: x.material_name,
      qty: x.qty,
      received_qty: x.received_qty,
      returned_qty: x.returned_qty,
      return_qty: maxRet,
    }
  })
  ret.open = true
  loadWarehouses()
}

async function onReturn() {
  if (!item.value) return
  const whId = Number(ret.form.warehouse_id || 0)
  if (!whId || whId < 1) {
    ElMessage.error(t('purchase.orderDetail.selectOutWarehouseError'))
    return
  }
  const rows = ret.form.items
    .map((x) => ({ ...x, return_qty: Number(x.return_qty || 0) }))
    .filter((x) => x.return_qty > 0)
    .map((x) => ({ item_id: x.item_id, return_qty: x.return_qty }))
  if (rows.length === 0) {
    ElMessage.error(t('purchase.orderDetail.inputReturnQty'))
    return
  }

  ret.saving = true
  try {
    item.value = await purchaseApi.returnOrder(item.value.id, { warehouse_id: whId, items: rows })
    ret.open = false
    ElMessage.success(t('purchase.orderDetail.returnSuccess'))
  } finally {
    ret.saving = false
  }
}

onMounted(reload)
</script>
