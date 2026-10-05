<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage title="MRP 物料需求计划">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-button type="primary" :loading="computing" @click="openComputeDialog">计算 MRP</el-button>
        <el-button @click="reload(true)">刷新</el-button>
      </div>
    </template>

    <!-- 计划批次列表 -->
    <div class="mt-4" v-loading="loading">
      <el-table class="hidden lg:block w-full" :data="items" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="code" label="计划单号" width="180" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源" width="120">
          <template #default="{ row }">
            {{ row.source_type === 'work_order' ? '工单' : row.source_type }}
          </template>
        </el-table-column>
        <el-table-column prop="total_skus" label="涉及型号" width="100" align="center" />
        <el-table-column prop="total_materials" label="涉及物料" width="100" align="center" />
        <el-table-column prop="total_purchase_qty" label="建议采购量" width="120" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row.id)">查看明细</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="min-w-0">
              <div class="font-semibold text-el-primary">{{ row.code }}</div>
              <div class="text-xs text-el-placeholder">#{{ row.id }} · {{ row.created_at }}</div>
            </div>
            <el-tag :type="statusTag(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </div>
          <dl class="admin-mobile-kv">
            <dt>涉及型号</dt>
            <dd>{{ row.total_skus }}</dd>
            <dt>涉及物料</dt>
            <dd>{{ row.total_materials }}</dd>
            <dt>建议采购量</dt>
            <dd class="text-left font-semibold text-el-danger">{{ row.total_purchase_qty }}</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" type="primary" @click="viewDetail(row.id)">查看明细</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" description="暂无 MRP 计划" />
      </div>
    </div>

    <div class="mt-4 flex justify-end">
      <el-pagination
        background
        layout="prev, pager, next"
        :page-size="query.limit"
        :total="total"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>

    <!-- 计算 MRP 对话框 -->
    <el-dialog v-model="computeDialogVisible" title="计算 MRP 物料需求" width="520px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item label="工单 ID">
          <el-input
            v-model="workOrderIdsText"
            placeholder="多个工单用逗号分隔，如 1,2,3"
            clearable
          />
          <div class="text-xs text-el-placeholder mt-1">从「生产工单」页面获取工单 ID，支持批量计算</div>
        </el-form-item>
        <el-form-item label="库存仓库">
          <el-select v-model="warehouseIds" multiple clearable collapse-tags placeholder="留空＝全部启用中的仓库">
            <el-option v-for="w in warehouseOptions" :key="w.id" :label="`${w.name}（${w.code}）`" :value="w.id" />
          </el-select>
          <div class="text-xs text-el-placeholder mt-1">只统计所选仓库的库存，停用仓默认不算</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="computeRemark" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="computeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="computing" @click="doCompute">开始计算</el-button>
      </template>
    </el-dialog>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" title="MRP 计划明细" size="80%">
      <template v-if="detail">
        <el-descriptions :column="4" border class="mb-4">
          <el-descriptions-item label="计划单号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="涉及型号">{{ detail.total_skus }}</el-descriptions-item>
          <el-descriptions-item label="涉及物料">{{ detail.total_materials }}</el-descriptions-item>
          <el-descriptions-item label="建议采购总量">
            <span class="font-semibold text-el-danger">{{ detail.total_purchase_qty }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>

        <div class="flex items-center gap-3 mb-3 flex-wrap">
          <el-button
            type="primary"
            :loading="converting"
            :disabled="convertDisabled"
            @click="doConvert"
          >
            {{ selectedRows.length ? `转采购草稿单（选中 ${selectedRows.length} 行）` : '转采购草稿单（全部未转行）' }}
          </el-button>
          <span class="text-xs text-el-placeholder">
            还有 {{ convertibleRows.length }} 行待转；勾行只转所选，不勾转全部。落的是草稿单，确认那一步仍在采购页由人点
          </span>
        </div>

        <el-table
          :data="detail.items"
          border
          v-loading="detailLoading"
          max-height="600"
          row-key="id"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="46" :selectable="isConvertible" fixed />
          <el-table-column prop="material_code" label="物料编码" width="140" fixed />
          <el-table-column prop="material_name" label="物料名称" width="180" />
          <el-table-column prop="material_unit" label="单位" width="70" align="center" />
          <el-table-column prop="sku_code" label="成品型号" width="120" />
          <el-table-column prop="order_code" label="订单号" width="150" />
          <el-table-column prop="work_order_id" label="工单" width="90" align="center">
            <template #default="{ row }">#{{ row.work_order_id ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="wo_qty" label="工单数量" width="100" align="right" />
          <el-table-column prop="qty_per" label="单件用量" width="100" align="right" />
          <el-table-column prop="gross_qty" label="毛需求" width="100" align="right">
            <template #default="{ row }">
              <span class="font-medium">{{ row.gross_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="stock_qty" label="可用库存" width="100" align="right">
            <template #default="{ row }">
              <span class="text-el-success">{{ row.stock_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="on_order_qty" label="在途" width="90" align="right">
            <template #default="{ row }">
              <span class="text-[var(--el-color-warning)]">{{ row.on_order_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="net_qty" label="净需求" width="100" align="right">
            <template #default="{ row }">
              <span class="font-semibold text-el-danger">{{ row.net_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="suggested_purchase_qty" label="建议采购" width="100" align="right">
            <template #default="{ row }">
              <span class="font-semibold text-el-primary">{{ row.suggested_purchase_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="落地" width="110" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.purchase_order_id" size="small" type="success">采购单 #{{ row.purchase_order_id }}</el-tag>
              <el-tag v-else-if="!row.suggested_purchase_qty" size="small" type="info">无需采购</el-tag>
              <el-tag v-else size="small" type="warning">未转</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="supplier_name" label="供应商" width="150" />
          <el-table-column prop="bom_scope" label="BOM来源" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="bomScopeTag(row.bom_scope)">{{ bomScopeLabel(row.bom_scope) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { mrpApi, type MrpItemOut, type MrpPlanBrief, type MrpPlanOut } from '@/api/mrp'
import { warehouseApi, type WarehouseOption } from '@/api/warehouse'

const loading = ref(false)
const items = ref<MrpPlanBrief[]>([])
const page = ref(1)
const total = ref(0)
const query = ref({ limit: 50, offset: 0 })

const computing = ref(false)
const computeDialogVisible = ref(false)
const workOrderIdsText = ref('')
const computeRemark = ref('')
const warehouseIds = ref<number[]>([])
const warehouseOptions = ref<WarehouseOption[]>([])

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<MrpPlanOut | null>(null)
const selectedRows = ref<MrpItemOut[]>([])
const converting = ref(false)

function statusLabel(s: string) {
  const map: Record<string, string> = {
    computed: '已计算',
    partial_converted: '部分已转采购',
    converted: '已转采购',
    released: '已下达',
    cancelled: '已取消',
  }
  return map[s] || s
}

function statusTag(s: string) {
  if (s === 'converted') return 'success'
  if (s === 'partial_converted') return 'warning'
  return 'info'
}

function isConvertible(row: MrpItemOut) {
  return row.suggested_purchase_qty > 0 && !row.purchase_order_id
}

const convertibleRows = computed(() => (detail.value?.items || []).filter(isConvertible))
const convertDisabled = computed(() => !convertibleRows.value.length)

function bomScopeLabel(s: string | null) {
  const map: Record<string, string> = { sku: '型号专属', product: '产品默认', global: '全厂默认' }
  return (s && map[s]) || s || '—'
}

function bomScopeTag(s: string | null) {
  if (s === 'sku') return 'primary'
  if (s === 'product') return 'warning'
  return 'info'
}

async function reload(resetPage = false) {
  if (resetPage) page.value = 1
  loading.value = true
  try {
    const resp = await mrpApi.listPlans({ ...query.value, offset: (page.value - 1) * query.value.limit })
    items.value = resp.items || []
    total.value = resp.total ?? items.value.length
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  reload()
}

function openComputeDialog() {
  computeDialogVisible.value = true
}

async function doCompute() {
  const ids = workOrderIdsText.value
    .split(/[,，\s]+/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map(Number)
  if (!ids.length) {
    ElMessage.warning('请至少输入一个工单 ID')
    return
  }
  computing.value = true
  try {
    const resp = await mrpApi.compute({
      work_order_ids: ids,
      remark: computeRemark.value || null,
      warehouse_ids: warehouseIds.value.length ? warehouseIds.value : null,
    })
    ElMessage.success(`MRP 计算完成：${resp.code}，建议采购 ${resp.total_purchase_qty}`)
    computeDialogVisible.value = false
    workOrderIdsText.value = ''
    computeRemark.value = ''
    reload(true)
  } finally {
    computing.value = false
  }
}

function onSelectionChange(rows: MrpItemOut[]) {
  selectedRows.value = rows
}

async function doConvert() {
  if (!detail.value) return
  const picked = selectedRows.value.filter(isConvertible).map((r) => r.id)
  converting.value = true
  try {
    const resp = await mrpApi.convertPlan(detail.value.id, { item_ids: picked.length ? picked : null })
    const codes = resp.purchase_orders.map((p) => p.code).join('、')
    const skip = resp.skipped_no_supplier ? `，${resp.skipped_no_supplier} 行无供应商已跳过` : ''
    ElMessage.success(`已生成 ${resp.purchase_orders.length} 张采购草稿单：${codes}${skip}`)
    selectedRows.value = []
    await viewDetail(detail.value.id)
    reload()
  } finally {
    converting.value = false
  }
}

async function viewDetail(id: number) {
  detailVisible.value = true
  detailLoading.value = true
  selectedRows.value = []
  try {
    detail.value = await mrpApi.getPlan(id)
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  reload()
  warehouseApi
    .listWarehouseOptions()
    .then((resp) => {
      warehouseOptions.value = resp.items || []
    })
    .catch(() => {
      // 拉不到仓库只是少一个筛选口子：留空＝全部启用中的仓库
    })
})
</script>
