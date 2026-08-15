<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { warehouseApi, type MaterialIssueOut, type IssueItemIn, type WarehouseOut } from '@/api/warehouse'
import { materialsApi } from '@/api/materials'

const { t } = useI18n()

const loading = ref(false)
const items = ref<MaterialIssueOut[]>([])
const warehouses = ref<WarehouseOut[]>([])
const materials = ref<{ id: number; code: string; name: string; sku_id: number | null; sku_code: string | null }[]>([])

const query = reactive({
  warehouse_id: undefined as number | undefined,
  status: '',
  keyword: '',
  offset: 0,
  limit: 50,
})

const detailVisible = ref(false)
const detail = ref<MaterialIssueOut | null>(null)
const detailLoading = ref(false)

const createVisible = ref(false)
const saving = ref(false)
const form = reactive({
  code: '',
  warehouse_id: undefined as number | undefined,
  work_order_id: undefined as number | undefined,
  remark: '',
  items: [] as { material_id?: number; sku_id?: number; qty: number }[],
})

const filtered = computed(() => {
  const kw = query.keyword.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((x) => {
    const a = (x.code || '').toLowerCase()
    const b = (x.warehouse_name || '').toLowerCase()
    return a.includes(kw) || b.includes(kw)
  })
})

async function loadWarehouses() {
  warehouses.value = (await warehouseApi.listWarehouses()).items ?? []
}

async function loadMaterials() {
  const res = await materialsApi.listMaterials({ offset: 0, limit: 200 })
  materials.value = (res.items ?? []).map((m: any) => ({
    id: m.id,
    code: m.code,
    name: m.name,
    sku_id: m.sku_id ?? null,
    sku_code: m.sku_code ?? null,
  }))
}

async function loadIssues() {
  loading.value = true
  try {
    const res = await warehouseApi.listIssues({
      warehouse_id: query.warehouse_id,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items ?? []
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.warehouse_id = undefined
  query.status = ''
  query.keyword = ''
  query.offset = 0
  loadIssues()
}

async function openDetail(row: MaterialIssueOut) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await warehouseApi.getIssue(row.id)
  } finally {
    detailLoading.value = false
  }
}

function openCreate() {
  form.code = ''
  form.warehouse_id = undefined
  form.work_order_id = undefined
  form.remark = ''
  form.items = [{ qty: 1 }]
  createVisible.value = true
}

function addItemRow() {
  form.items.push({ qty: 1 })
}

function removeItemRow(i: number) {
  form.items.splice(i, 1)
}

function onMaterialChange(i: number) {
  const m = materials.value.find((x) => x.id === form.items[i].material_id)
  form.items[i].sku_id = m?.sku_id ?? undefined
}

async function saveIssue() {
  if (!form.warehouse_id) {
    ElMessage.warning('请选择仓库')
    return
  }
  const payloadItems: IssueItemIn[] = []
  for (const it of form.items) {
    if (!it.material_id || !it.sku_id || !it.qty || it.qty < 1) {
      ElMessage.warning('请完整填写领料明细（物料/SKU/数量）')
      return
    }
    payloadItems.push({ material_id: it.material_id, sku_id: it.sku_id, qty: it.qty })
  }
  if (!payloadItems.length) {
    ElMessage.warning('请至少添加一条领料明细')
    return
  }
  saving.value = true
  try {
    await warehouseApi.createIssue({
      code: form.code || undefined,
      warehouse_id: form.warehouse_id,
      work_order_id: form.work_order_id || undefined,
      remark: form.remark || undefined,
      items: payloadItems,
    })
    ElMessage.success('创建成功')
    createVisible.value = false
    loadIssues()
  } finally {
    saving.value = false
  }
}

async function doIssue(row: MaterialIssueOut) {
  await ElMessageBox.confirm(`确认领料单 ${row.code}？确认后库存将扣减`, '确认领料', { type: 'warning' })
  await warehouseApi.issueMaterials(row.id)
  ElMessage.success('领料成功')
  loadIssues()
}

async function doCancel(row: MaterialIssueOut) {
  await ElMessageBox.confirm(`确认取消领料单 ${row.code}？`, '取消领料单', { type: 'warning' })
  await warehouseApi.cancelIssue(row.id)
  ElMessage.success('已取消')
  loadIssues()
}

const statusTag = (s: string) => {
  if (s === 'issued') return 'success'
  if (s === 'cancelled') return 'info'
  return 'warning'
}

onMounted(() => {
  loadWarehouses()
  loadMaterials()
  loadIssues()
})
</script>

<template>
  <AdminPage :title="t('menu.materialIssues')">
    <el-card shadow="never" class="mb-4">
      <div class="flex flex-wrap gap-3 items-center">
        <el-select v-model="query.warehouse_id" placeholder="仓库" clearable class="w-40" @change="loadIssues">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
        </el-select>
        <el-select v-model="query.status" placeholder="状态" clearable class="w-32" @change="loadIssues">
          <el-option label="草稿" value="draft" />
          <el-option label="已领料" value="issued" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-input v-model="query.keyword" placeholder="单号/仓库" clearable class="w-48" @keyup.enter="resetQuery" />
        <el-button @click="resetQuery">查询</el-button>
        <el-button type="primary" @click="openCreate">新建领料单</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="filtered" stripe>
        <el-table-column prop="code" label="单号" min-width="150" />
        <el-table-column prop="warehouse_name" label="仓库" min-width="120" />
        <el-table-column prop="work_order_code" label="工单" min-width="100">
          <template #default="{ row }">{{ row.work_order_code || '-' }}</template>
        </el-table-column>
        <el-table-column prop="total_qty" label="总数量" min-width="90" />
        <el-table-column label="总成本" min-width="100">
          <template #default="{ row }">¥{{ row.total_cost.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status === 'issued' ? '已领料' : row.status === 'cancelled' ? '已取消' : '草稿' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'draft'" link type="success" @click="doIssue(row)">确认领料</el-button>
            <el-button v-if="row.status === 'draft'" link type="danger" @click="doCancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="领料单详情" width="720px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border class="mb-4">
            <el-descriptions-item label="单号">{{ detail.code }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
            <el-descriptions-item label="仓库">{{ detail.warehouse_name }}</el-descriptions-item>
            <el-descriptions-item label="工单">{{ detail.work_order_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="总数量">{{ detail.total_qty }}</el-descriptions-item>
            <el-descriptions-item label="总成本">¥{{ detail.total_cost.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="领料时间">{{ detail.issued_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-table :data="detail.items ?? []" size="small" stripe>
            <el-table-column prop="material_code" label="物料编码" min-width="120" />
            <el-table-column prop="material_name" label="物料名称" min-width="140" />
            <el-table-column prop="sku_code" label="SKU" min-width="120" />
            <el-table-column prop="qty" label="数量" width="80" />
            <el-table-column label="单价" width="100">
              <template #default="{ row }">¥{{ row.unit_cost.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="金额" width="110">
              <template #default="{ row }">¥{{ row.cost_amount.toFixed(2) }}</template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-dialog>

    <!-- 新建 -->
    <el-dialog v-model="createVisible" title="新建领料单" width="720px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="单号">
          <el-input v-model="form.code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="仓库" required>
          <el-select v-model="form.warehouse_id" placeholder="选择仓库" class="w-full">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单">
          <el-input v-model.number="form.work_order_id" placeholder="工单ID（可选）" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="明细" required>
          <div class="w-full">
            <div v-for="(it, i) in form.items" :key="i" class="flex gap-2 mb-2 items-center">
              <el-select v-model="it.material_id" placeholder="物料" filterable class="flex-1" @change="onMaterialChange(i)">
                <el-option v-for="m in materials" :key="m.id" :label="`${m.code} ${m.name}`" :value="m.id" />
              </el-select>
              <el-input v-model.number="it.qty" placeholder="数量" class="w-24" type="number" min="1" />
              <el-button link type="danger" @click="removeItemRow(i)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addItemRow">+ 添加明细</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveIssue">保存</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
