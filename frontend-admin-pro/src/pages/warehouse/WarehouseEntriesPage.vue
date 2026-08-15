<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { warehouseApi, type WarehouseEntryOut, type EntryItemIn, type WarehouseOut } from '@/api/warehouse'

const { t } = useI18n()

const loading = ref(false)
const items = ref<WarehouseEntryOut[]>([])
const warehouses = ref<WarehouseOut[]>([])

const query = reactive({
  warehouse_id: undefined as number | undefined,
  source_type: '',
  status: '',
  offset: 0,
  limit: 10,
})

const statusMap: Record<string, string> = {
  draft: '草稿',
  confirmed: '已入库',
  cancelled: '已取消',
}
const sourceTypeMap: Record<string, string> = {
  purchase: '采购入库',
  material_return: '退料入库',
  other: '其他入库',
}
const statusTag: Record<string, string> = {
  draft: 'warning',
  confirmed: 'success',
  cancelled: 'info',
}

async function load() {
  loading.value = true
  try {
    const res = await warehouseApi.listEntries({
      warehouse_id: query.warehouse_id,
      source_type: query.source_type || undefined,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items ?? []
  } finally {
    loading.value = false
  }
}

function onSearch() {
  query.offset = 0
  load()
}

function onReset() {
  query.warehouse_id = undefined
  query.source_type = ''
  query.status = ''
  query.offset = 0
  load()
}

async function loadWarehouses() {
  const res = await warehouseApi.listWarehouses()
  warehouses.value = res.items ?? []
}

// ---------- 创建入库单 ----------
const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive({
  code: '',
  source_type: 'other',
  warehouse_id: undefined as number | undefined,
  purchase_order_id: undefined as number | undefined,
  material_return_id: undefined as number | undefined,
  remark: '',
  rows: [] as { material_id?: number; sku_id?: number; qty?: number }[],
})

function openCreate() {
  form.code = ''
  form.source_type = 'other'
  form.warehouse_id = undefined
  form.purchase_order_id = undefined
  form.material_return_id = undefined
  form.remark = ''
  form.rows = [{ material_id: undefined, sku_id: undefined, qty: undefined }]
  dialogVisible.value = true
}

function addRow() {
  form.rows.push({ material_id: undefined, sku_id: undefined, qty: undefined })
}

function removeRow(i: number) {
  form.rows.splice(i, 1)
}

async function save() {
  if (!form.warehouse_id) {
    ElMessage.warning('请选择仓库')
    return
  }
  const rows = form.rows.filter((r) => r.material_id && r.sku_id && r.qty && r.qty > 0)
  if (!rows.length) {
    ElMessage.warning('请填写入库明细')
    return
  }
  if (form.source_type === 'purchase' && !form.purchase_order_id) {
    ElMessage.warning('采购入库必须关联采购单')
    return
  }
  if (form.source_type === 'material_return' && !form.material_return_id) {
    ElMessage.warning('退料入库必须关联退料单')
    return
  }
  saving.value = true
  try {
    const payload: any = {
      code: form.code || undefined,
      source_type: form.source_type,
      warehouse_id: form.warehouse_id,
      remark: form.remark || undefined,
      items: rows.map((r) => ({ material_id: r.material_id, sku_id: r.sku_id, qty: r.qty }) as EntryItemIn),
    }
    if (form.purchase_order_id) payload.purchase_order_id = form.purchase_order_id
    if (form.material_return_id) payload.material_return_id = form.material_return_id
    await warehouseApi.createEntry(payload)
    ElMessage.success('入库单已创建')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function confirmEntry(row: WarehouseEntryOut) {
  try {
    await ElMessageBox.confirm(`确认入库单 ${row.code} 入库？将增加库存并记账。`, '确认入库', { type: 'warning' })
  } catch {
    return
  }
  await warehouseApi.confirmEntry(row.id)
  ElMessage.success('已确认入库')
  load()
}

async function cancelEntry(row: WarehouseEntryOut) {
  try {
    await ElMessageBox.confirm(`取消入库单 ${row.code}？`, '取消', { type: 'warning' })
  } catch {
    return
  }
  await warehouseApi.cancelEntry(row.id)
  ElMessage.success('已取消')
  load()
}

onMounted(() => {
  load()
  loadWarehouses()
})
</script>

<template>
  <AdminPage :title="t('menu.warehouseEntries')">
    <template #actions>
      <el-button type="primary" @click="openCreate">新建入库单</el-button>
    </template>

    <el-card shadow="never" class="mb-3">
      <el-form inline>
        <el-form-item label="仓库">
          <el-select v-model="query.warehouse_id" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="query.source_type" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="(v, k) in sourceTypeMap" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.status" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="(v, k) in statusMap" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="code" label="入库单号" width="160" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ sourceTypeMap[row.source_type] ?? row.source_type }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="(statusTag[row.status] as any) ?? 'info'">{{ statusMap[row.status] ?? row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="仓库" width="120">
          <template #default="{ row }">{{ row.warehouse_name }}</template>
        </el-table-column>
        <el-table-column label="关联单据">
          <template #default="{ row }">
            <el-tag v-if="row.purchase_order_code" size="small" type="primary">{{ row.purchase_order_code }}</el-tag>
            <el-tag v-if="row.material_return_code" size="small" type="success">{{ row.material_return_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_qty" label="数量" width="90" />
        <el-table-column label="成本金额" width="120">
          <template #default="{ row }">¥{{ row.total_cost }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" type="primary" link @click="confirmEntry(row)">入库</el-button>
            <el-button v-if="row.status === 'draft'" type="danger" link @click="cancelEntry(row)">取消</el-button>
            <el-button type="primary" link @click="dialogVisible = true; form.rows = []; form.purchase_order_id = row.purchase_order_id ?? undefined; form.material_return_id = row.material_return_id ?? undefined; form.warehouse_id = row.warehouse_id; form.source_type = row.source_type">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="mt-3"
        layout="total, prev, pager, next"
        :total="items.length"
        :page-size="query.limit"
        :current-page="query.offset / query.limit + 1"
        @current-change="(p: number) => { query.offset = (p - 1) * query.limit; load() }"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建入库单" width="640px">
      <el-form label-width="90px">
        <el-form-item label="入库类型">
          <el-select v-model="form.source_type" style="width: 200px">
            <el-option v-for="(v, k) in sourceTypeMap" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="form.warehouse_id" style="width: 200px">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.source_type === 'purchase'" label="采购单号">
          <el-input v-model="form.purchase_order_id" type="number" placeholder="采购单 ID" />
        </el-form-item>
        <el-form-item v-if="form.source_type === 'material_return'" label="退料单号">
          <el-input v-model="form.material_return_id" type="number" placeholder="退料单 ID" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" placeholder="备注" />
        </el-form-item>
        <el-form-item label="入库明细">
          <div class="w-full">
            <div v-for="(row, i) in form.rows" :key="i" class="flex gap-2 mb-2 items-center">
              <el-input v-model="row.material_id" type="number" placeholder="物料ID" style="width: 110px" />
              <el-input v-model="row.sku_id" type="number" placeholder="SKU ID" style="width: 110px" />
              <el-input v-model="row.qty" type="number" placeholder="数量" style="width: 100px" />
              <el-button type="danger" link @click="removeRow(i)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addRow">+ 添加明细</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
