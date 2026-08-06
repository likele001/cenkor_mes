<template>
  <AdminPage title="外协工序管理">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-input
          v-model="query.keyword"
          placeholder="搜索单号"
          clearable
          style="width: 220px"
          @keyup.enter="reload(true)"
        />
        <el-select
          v-model="query.supplier_id"
          clearable
          filterable
          placeholder="供应商"
          style="width: 220px"
          @change="reload(true)"
        >
          <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select
          v-model="query.status"
          clearable
          placeholder="状态"
          style="width: 160px"
          @change="reload(true)"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="已发料" value="sent" />
          <el-option label="部分收货" value="partial_received" />
          <el-option label="已收货" value="received" />
          <el-option label="已结算" value="settled" />
        </el-select>
        <el-button type="primary" @click="openCreateDialog">新建委外单</el-button>
        <el-button @click="reload(true)">刷新</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table class="w-full" :data="items" border @row-click="openDetail" style="cursor: pointer">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="code" label="单号" width="220" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="供应商" min-width="200">
          <template #default="{ row }">
            <span>{{ row.supplier_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </div>

    <div class="mt-4 flex justify-end">
      <el-pagination
        background
        layout="prev, pager, next"
        :page-size="query.limit"
        :total="fakeTotal"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>

    <!-- 新建委外单 Dialog -->
    <el-dialog v-model="createDialogVisible" title="新建委外单" width="850px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="单号">
          <el-input v-model="createForm.code" placeholder="请输入单号" style="width: 300px" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-select
            v-model="createForm.supplier_id"
            filterable
            placeholder="请选择供应商"
            style="width: 300px"
          >
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
        <el-form-item label="工序明细">
          <el-table :data="createForm.items" border size="small">
            <el-table-column label="SKU" min-width="200">
              <template #default="{ row, $index }">
                <el-select
                  v-model="row.sku_id"
                  filterable
                  placeholder="选择SKU"
                  style="width: 100%"
                  @change="onCreateSkuChange($index)"
                >
                  <el-option
                    v-for="s in skus"
                    :key="s.id"
                    :label="s.display_label || `${s.code} - ${s.name}`"
                    :value="s.id"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="工序" width="180">
              <template #default="{ row }">
                <el-select
                  v-model="row.process_id"
                  clearable
                  filterable
                  placeholder="选择工序"
                  style="width: 100%"
                >
                  <el-option
                    v-for="p in processes"
                    :key="p.id"
                    :label="p.display_name || p.name"
                    :value="p.id"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.qty" :min="0" :precision="2" controls-position="right" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column label="单价" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.unit_price" :min="0" :precision="2" controls-position="right" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="150">
              <template #default="{ row }">
                <el-input v-model="row.remark" placeholder="备注" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ $index }">
                <el-button type="danger" size="small" text @click="removeCreateItem($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button class="mt-2" size="small" @click="addCreateItem">+ 添加明细</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 详情 Drawer -->
    <el-drawer v-model="detailDrawerVisible" title="委外单详情" size="75%">
      <div v-if="detail" v-loading="detailLoading" class="space-y-6">
        <!-- 订单信息 -->
        <el-descriptions :column="3" border>
          <el-descriptions-item label="单号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="供应商">{{ detail.supplier_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.created_by ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ detail.updated_at }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 操作按钮 -->
        <div class="flex items-center gap-2 flex-wrap">
          <el-button
            v-if="detail.status === 'draft'"
            type="warning"
            :loading="statusUpdating"
            @click="changeStatus('sent')"
          >发料启动</el-button>
          <el-button
            v-if="detail.status === 'received'"
            type="primary"
            :loading="statusUpdating"
            @click="changeStatus('settled')"
          >结算</el-button>
          <el-button
            v-if="['sent', 'partial_received'].includes(detail.status)"
            type="warning"
            @click="openSendDialog"
          >发料</el-button>
          <el-button
            v-if="['sent', 'partial_received'].includes(detail.status)"
            type="success"
            @click="openReceiveDialog"
          >收货</el-button>
        </div>

        <!-- 工序明细 -->
        <div>
          <h4 class="text-[15px] font-semibold mb-2">工序明细</h4>
          <el-table :data="detail.items" border size="small">
            <el-table-column prop="sku_code" label="SKU编码" width="160" />
            <el-table-column prop="sku_name" label="SKU名称" min-width="180" />
            <el-table-column prop="process_name" label="工序" width="140">
              <template #default="{ row }">
                <span>{{ row.process_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="qty" label="数量" width="100" />
            <el-table-column prop="unit_price" label="单价" width="100">
              <template #default="{ row }">
                <span>{{ row.unit_price || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="sent_qty" label="已发料" width="100" />
            <el-table-column prop="received_qty" label="已收货" width="100" />
            <el-table-column prop="remark" label="备注" min-width="120">
              <template #default="{ row }">
                <span>{{ row.remark || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 发料记录 -->
        <div>
          <h4 class="text-[15px] font-semibold mb-2">发料记录</h4>
          <el-table :data="detail.send_logs" border size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="sku_code" label="SKU编码" width="160" />
            <el-table-column prop="sku_name" label="SKU名称" min-width="180" />
            <el-table-column prop="qty" label="数量" width="100" />
            <el-table-column prop="remark" label="备注" min-width="150">
              <template #default="{ row }">
                <span>{{ row.remark || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
          <el-empty v-if="!detail.send_logs?.length" description="暂无发料记录" :image-size="60" />
        </div>

        <!-- 收货记录 -->
        <div>
          <h4 class="text-[15px] font-semibold mb-2">收货记录</h4>
          <el-table :data="detail.receive_logs" border size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="sku_code" label="SKU编码" width="160" />
            <el-table-column prop="sku_name" label="SKU名称" min-width="180" />
            <el-table-column prop="qty" label="数量" width="100" />
            <el-table-column prop="remark" label="备注" min-width="150">
              <template #default="{ row }">
                <span>{{ row.remark || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
          <el-empty v-if="!detail.receive_logs?.length" description="暂无收货记录" :image-size="60" />
        </div>
      </div>
    </el-drawer>

    <!-- 发料 Dialog -->
    <el-dialog v-model="sendDialogVisible" title="发料" width="500px" :close-on-click-modal="false">
      <el-form :model="sendForm" label-width="80px">
        <el-form-item label="明细">
          <el-select v-model="sendForm.item_id" placeholder="请选择明细" style="width: 100%">
            <el-option
              v-for="item in detail?.items || []"
              :key="item.id"
              :label="`${item.sku_code || ''} - ${item.sku_name || ''}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="sendForm.qty" :min="0" :precision="2" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="sendForm.remark" type="textarea" :rows="2" placeholder="备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sendDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="submitSend">确定发料</el-button>
      </template>
    </el-dialog>

    <!-- 收货 Dialog -->
    <el-dialog v-model="receiveDialogVisible" title="收货" width="500px" :close-on-click-modal="false">
      <el-form :model="receiveForm" label-width="80px">
        <el-form-item label="明细">
          <el-select v-model="receiveForm.item_id" placeholder="请选择明细" style="width: 100%">
            <el-option
              v-for="item in detail?.items || []"
              :key="item.id"
              :label="`${item.sku_code || ''} - ${item.sku_name || ''}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="receiveForm.qty" :min="0" :precision="2" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="receiveForm.remark" type="textarea" :rows="2" placeholder="备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="receiveDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="submitting" @click="submitReceive">确定收货</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  subcontractApi,
  type SubcontractOrderBrief,
  type SubcontractOrderOut,
} from '@/api/subcontract'
import { materialsApi, type SupplierOut } from '@/api/materials'
import { masterApi, type SkuOut, type ProcessOut } from '@/api/master'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const items = ref<SubcontractOrderBrief[]>([])
const suppliers = ref<SupplierOut[]>([])
const skus = ref<SkuOut[]>([])
const processes = ref<ProcessOut[]>([])

const query = reactive({
  keyword: '',
  supplier_id: null as number | null,
  status: '',
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(
  () => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0)
)

const statusLabel = (status: string): string => {
  const map: Record<string, string> = {
    draft: '草稿',
    sent: '已发料',
    partial_received: '部分收货',
    received: '已收货',
    settled: '已结算',
  }
  return map[status] || status
}

const statusTagType = (status: string): '' | 'info' | 'warning' | 'success' | 'primary' => {
  const map: Record<string, '' | 'info' | 'warning' | 'success' | 'primary'> = {
    draft: 'info',
    sent: 'warning',
    partial_received: 'warning',
    received: 'success',
    settled: 'primary',
  }
  return map[status] || ''
}

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({
    keyword: '',
    offset: 0,
    limit: 200,
    include_inactive: true,
  })
  suppliers.value = res.items
}

async function loadSkus() {
  const res = await masterApi.listSkus({ offset: 0, limit: 200, include_inactive: false })
  skus.value = res.items
}

async function loadProcesses() {
  const res = await masterApi.listProcesses({ offset: 0, limit: 200, include_inactive: false })
  processes.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await subcontractApi.listOrders({
      keyword: query.keyword || undefined,
      supplier_id: query.supplier_id || undefined,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

/* ==================== 新建委外单 ==================== */

const createDialogVisible = ref(false)
const submitting = ref(false)

const createForm = reactive<{
  code: string
  supplier_id: number | null
  remark: string
  items: {
    sku_id: number | null
    process_id: number | null
    qty: number
    unit_price: string | null
    remark: string
  }[]
}>({
  code: '',
  supplier_id: null,
  remark: '',
  items: [],
})

function openCreateDialog() {
  createForm.code = ''
  createForm.supplier_id = null
  createForm.remark = ''
  createForm.items = []
  addCreateItem()
  createDialogVisible.value = true
}

function addCreateItem() {
  createForm.items.push({
    sku_id: null,
    process_id: null,
    qty: 0,
    unit_price: null,
    remark: '',
  })
}

function removeCreateItem(index: number) {
  createForm.items.splice(index, 1)
}

function onCreateSkuChange(_index: number) {
  // placeholder for future auto-fill logic
}

async function submitCreate() {
  if (!createForm.code.trim()) {
    ElMessage.warning('请输入单号')
    return
  }
  if (!createForm.supplier_id) {
    ElMessage.warning('请选择供应商')
    return
  }
  if (!createForm.items.length) {
    ElMessage.warning('请至少添加一条明细')
    return
  }
  for (const item of createForm.items) {
    if (!item.sku_id) {
      ElMessage.warning('请选择所有明细的SKU')
      return
    }
    if (item.qty <= 0) {
      ElMessage.warning('数量必须大于0')
      return
    }
  }
  submitting.value = true
  try {
    await subcontractApi.createOrder({
      supplier_id: createForm.supplier_id,
      code: createForm.code.trim(),
      remark: createForm.remark || null,
      items: createForm.items.map((item) => ({
        sku_id: item.sku_id!,
        process_id: item.process_id || null,
        qty: item.qty,
        unit_price: item.unit_price || null,
        remark: item.remark || null,
      })),
    })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    await reload(true)
  } finally {
    submitting.value = false
  }
}

/* ==================== 详情 Drawer ==================== */

const detailDrawerVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<SubcontractOrderOut | null>(null)

async function openDetail(row: SubcontractOrderBrief) {
  detailDrawerVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await subcontractApi.getOrder(row.id)
  } finally {
    detailLoading.value = false
  }
}

async function refreshDetail() {
  if (!detail.value) return
  detailLoading.value = true
  try {
    detail.value = await subcontractApi.getOrder(detail.value.id)
  } finally {
    detailLoading.value = false
  }
}

/* ==================== 状态变更 ==================== */

const statusUpdating = ref(false)

async function changeStatus(status: string) {
  if (!detail.value) return
  statusUpdating.value = true
  try {
    await subcontractApi.updateStatus(detail.value.id, status)
    ElMessage.success('状态更新成功')
    await refreshDetail()
    await reload(false)
  } finally {
    statusUpdating.value = false
  }
}

/* ==================== 发料 ==================== */

const sendDialogVisible = ref(false)
const sendForm = reactive({
  item_id: null as number | null,
  qty: 0,
  remark: '',
})

function openSendDialog() {
  sendForm.item_id = null
  sendForm.qty = 0
  sendForm.remark = ''
  sendDialogVisible.value = true
}

async function submitSend() {
  if (!detail.value) return
  if (!sendForm.item_id) {
    ElMessage.warning('请选择明细')
    return
  }
  if (sendForm.qty <= 0) {
    ElMessage.warning('数量必须大于0')
    return
  }
  submitting.value = true
  try {
    await subcontractApi.sendLog(detail.value.id, {
      item_id: sendForm.item_id,
      qty: sendForm.qty,
      remark: sendForm.remark || null,
    })
    ElMessage.success('发料成功')
    sendDialogVisible.value = false
    await refreshDetail()
    await reload(false)
  } finally {
    submitting.value = false
  }
}

/* ==================== 收货 ==================== */

const receiveDialogVisible = ref(false)
const receiveForm = reactive({
  item_id: null as number | null,
  qty: 0,
  remark: '',
})

function openReceiveDialog() {
  receiveForm.item_id = null
  receiveForm.qty = 0
  receiveForm.remark = ''
  receiveDialogVisible.value = true
}

async function submitReceive() {
  if (!detail.value) return
  if (!receiveForm.item_id) {
    ElMessage.warning('请选择明细')
    return
  }
  if (receiveForm.qty <= 0) {
    ElMessage.warning('数量必须大于0')
    return
  }
  submitting.value = true
  try {
    await subcontractApi.receiveLog(detail.value.id, {
      item_id: receiveForm.item_id,
      qty: receiveForm.qty,
      remark: receiveForm.remark || null,
    })
    ElMessage.success('收货成功')
    receiveDialogVisible.value = false
    await refreshDetail()
    await reload(false)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadSuppliers(), loadSkus(), loadProcesses()])
  await reload(true)
})
</script>
