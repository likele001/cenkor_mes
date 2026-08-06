<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { traceApi, type TraceTree, type TreeNode } from '@/api/trace'

const productCode = ref('')
const loading = ref(false)
const treeResult = ref<TraceTree | null>(null)

/** 默认展开的节点 key（首次查询后全部展开） */
const defaultExpandedKeys = ref<(string | number)[]>([])
const defaultExpandAll = ref(true)

const treeData = computed<TreeNode[]>(() => treeResult.value?.tree ?? [])

/** QR 占位矩阵：基于成品码生成的确定性伪二维码图案 */
const qrMatrix = computed<boolean[][]>(() => {
  const text = treeResult.value?.product_code || productCode.value || ''
  const size = 21
  const matrix: boolean[][] = []
  let seed = 2166136261
  for (let i = 0; i < text.length; i++) {
    seed ^= text.charCodeAt(i)
    seed = Math.imul(seed, 16777619) >>> 0
  }
  const rand = () => {
    seed = (Math.imul(seed, 1103515245) + 12345) & 0x7fffffff
    return seed / 0x7fffffff
  }
  for (let r = 0; r < size; r++) {
    const row: boolean[] = []
    for (let c = 0; c < size; c++) row.push(rand() > 0.5)
    matrix.push(row)
  }
  // 绘制三个定位角标（7x7 探测图形）
  const drawFinder = (sr: number, sc: number) => {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const border = r === 0 || r === 6 || c === 0 || c === 6
        const center = r >= 2 && r <= 4 && c >= 2 && c <= 4
        const ring = (r === 1 || r === 5 || c === 1 || c === 5) && !center
        matrix[sr + r][sc + c] = border || center
        if (ring) matrix[sr + r][sc + c] = false
      }
    }
  }
  drawFinder(0, 0)
  drawFinder(0, size - 7)
  drawFinder(size - 7, 0)
  // 定时图案（清空固定行/列，模拟真实 QR 的分隔）
  for (let i = 8; i < size - 8; i++) {
    matrix[6][i] = i % 2 === 0
    matrix[i][6] = i % 2 === 0
  }
  return matrix
})

/** 递归收集所有节点 id 作为默认展开 key */
function collectKeys(nodes: TreeNode[], acc: (string | number)[] = []): (string | number)[] {
  for (const n of nodes) {
    acc.push(n.id)
    if (n.children?.length) collectKeys(n.children, acc)
  }
  return acc
}

/** 递归统计节点数量 */
function countNodes(nodes: TreeNode[]): number {
  let n = 0
  for (const node of nodes) {
    n += 1
    if (node.children?.length) n += countNodes(node.children)
  }
  return n
}

const totalNodes = computed(() => {
  if (treeResult.value?.total_nodes != null) return treeResult.value.total_nodes
  return countNodes(treeData.value)
})

const orderInfo = computed(() => treeResult.value?.order ?? null)
const skuInfo = computed(() => treeResult.value?.sku ?? null)

function reportStatusType(status?: string | null) {
  if (!status) return 'info'
  if (status === 'qc_approved' || status === 'approved') return 'success'
  if (status === 'qc_rejected' || status === 'rejected') return 'danger'
  if (status === 'pending' || status === 'draft') return 'warning'
  return 'info'
}

const REPORT_STATUS_TEXT: Record<string, string> = {
  qc_approved: '质检通过',
  approved: '已通过',
  qc_rejected: '质检驳回',
  rejected: '已驳回',
  pending: '待审核',
  draft: '草稿',
  submitted: '已提交',
  in_progress: '进行中',
}

function reportStatusText(status?: string | null) {
  if (!status) return '—'
  return REPORT_STATUS_TEXT[status] || status
}

const ORDER_STATUS_TEXT: Record<string, string> = {
  draft: '草稿',
  confirmed: '已确认',
  in_progress: '生产中',
  completed: '已完成',
  cancelled: '已取消',
  paused: '已暂停',
}

function orderStatusText(status?: string | null) {
  if (!status) return '—'
  return ORDER_STATUS_TEXT[status] || status
}

function orderStatusType(status?: string | null) {
  if (!status) return 'info'
  if (status === 'completed') return 'success'
  if (status === 'in_progress' || status === 'confirmed') return 'primary'
  if (status === 'cancelled') return 'danger'
  if (status === 'paused') return 'warning'
  return 'info'
}

function userName(node: TreeNode) {
  return node.user?.full_name || node.user?.username || '—'
}

function processName(node: TreeNode) {
  return node.process?.name || node.process?.code || '—'
}

function nodeLabel(node: TreeNode) {
  const parts = [processName(node)]
  if (node.task_seq != null) parts.push(`#${node.task_seq}`)
  return parts.join(' ')
}

function formatDate(s?: string | null) {
  if (!s) return '—'
  return String(s).slice(0, 19).replace('T', ' ')
}

async function handleQuery() {
  const code = productCode.value.trim()
  if (!code) {
    ElMessage.warning('请输入成品码')
    return
  }
  loading.value = true
  treeResult.value = null
  try {
    const res = await traceApi.getTree(code)
    treeResult.value = res
    if (res?.tree?.length) {
      defaultExpandedKeys.value = collectKeys(res.tree)
    }
  } catch (e: unknown) {
    treeResult.value = null
    ElMessage.error((e as Error).message || '查询失败')
  } finally {
    loading.value = false
  }
}

function handleEnter() {
  handleQuery()
}
</script>

<template>
  <AdminPage title="层级追溯查询">
    <!-- 查询表单 -->
    <el-form inline class="mb-4">
      <el-form-item label="成品码">
        <el-input
          v-model="productCode"
          placeholder="请输入或扫描成品码（FP...）"
          style="width: 320px"
          clearable
          @keyup.enter="handleEnter"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleQuery">查询</el-button>
      </el-form-item>
    </el-form>

    <!-- 查询结果 -->
    <template v-if="treeResult">
      <!-- 汇总卡片 -->
      <el-row :gutter="16" class="mb-4">
        <el-col :xs="24" :sm="12" :md="8">
          <el-card shadow="never" class="summary-card h-full">
            <template #header><span class="font-medium">订单信息</span></template>
            <template v-if="orderInfo">
              <div class="text-sm">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-zinc-500">订单号：</span>
                  <span class="font-mono">{{ orderInfo.code }}</span>
                  <el-tag :type="orderStatusType(orderInfo.status)" size="small">
                    {{ orderStatusText(orderInfo.status) }}
                  </el-tag>
                </div>
                <div class="text-zinc-500">订单 ID：#{{ orderInfo.id }}</div>
              </div>
            </template>
            <el-empty v-else description="无订单信息" :image-size="48" />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="12" :md="8">
          <el-card shadow="never" class="summary-card h-full">
            <template #header><span class="font-medium">产品型号（SKU）</span></template>
            <template v-if="skuInfo">
              <div class="text-sm">
                <div class="mb-2">
                  <span class="text-zinc-500">名称：</span>
                  <span class="font-medium">{{ skuInfo.name }}</span>
                </div>
                <div class="text-zinc-500">编码：{{ skuInfo.code }} · ID：#{{ skuInfo.id }}</div>
              </div>
            </template>
            <el-empty v-else description="无型号信息" :image-size="48" />
          </el-card>
        </el-col>

        <el-col :xs="24" :sm="24" :md="8">
          <el-card shadow="never" class="summary-card h-full">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="font-medium">成品码二维码</span>
                <el-tag size="small" type="info">追溯标识</el-tag>
              </div>
            </template>
            <div class="flex items-center gap-4">
              <!-- QR 占位图 -->
              <div class="qr-box">
                <div
                  v-for="(row, ri) in qrMatrix"
                  :key="ri"
                  class="qr-row"
                >
                  <span
                    v-for="(cell, ci) in row"
                    :key="ci"
                    class="qr-cell"
                    :class="{ 'qr-cell--on': cell }"
                  />
                </div>
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-xs text-zinc-500 mb-1">成品码</div>
                <div class="font-mono text-sm font-semibold break-all">{{ treeResult.product_code }}</div>
                <div class="mt-2 text-xs text-zinc-400">节点总数：{{ totalNodes }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 树形追溯 -->
      <el-card shadow="never">
        <template #header>
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span class="font-medium">层级追溯树（共 {{ totalNodes }} 个节点）</span>
            <el-checkbox v-model="defaultExpandAll">默认展开全部</el-checkbox>
          </div>
        </template>

        <el-empty v-if="!treeData.length" description="暂无追溯数据" />

        <el-tree
          v-else
          :data="treeData"
          :props="{ children: 'children', label: 'code' }"
          node-key="id"
          :default-expand-all="defaultExpandAll"
          :default-expanded-keys="defaultExpandAll ? [] : defaultExpandedKeys"
          :expand-on-click-node="true"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <!-- 主信息行 -->
              <div class="tree-node__main">
                <span class="tree-node__process">{{ processName(data) }}</span>
                <el-tag v-if="data.task_seq != null" size="small" type="primary" effect="plain">
                  工序 #{{ data.task_seq }}
                </el-tag>
                <el-tag size="small">数量 {{ data.qty }}</el-tag>
                <el-tag
                  v-if="data.report"
                  size="small"
                  :type="reportStatusType(data.report.status)"
                >
                  {{ reportStatusText(data.report.status) }}
                </el-tag>
                <span class="tree-node__user">{{ userName(data) }}</span>
                <span class="tree-node__date">{{ formatDate(data.created_at) }}</span>
              </div>
              <!-- 次要信息行 -->
              <div class="tree-node__sub">
                <span class="font-mono text-xs text-zinc-400">{{ data.product_code || data.code }}</span>
                <template v-if="data.piece_no">
                  <span class="text-xs text-zinc-400">件次：{{ data.piece_no }}</span>
                </template>
                <template v-if="data.report">
                  <span class="text-xs text-emerald-600">合格 {{ data.report.good_qty }}</span>
                  <span class="text-xs text-red-500">不良 {{ data.report.bad_qty }}</span>
                </template>
                <template v-if="data.report_unit">
                  <span class="text-xs text-zinc-400">
                    单元 #{{ data.report_unit.unit_seq ?? '—' }}（{{ data.report_unit.result_type || '—' }}）
                  </span>
                </template>
                <template v-if="data.remark">
                  <span class="text-xs text-amber-600">备注：{{ data.remark }}</span>
                </template>
              </div>
            </div>
          </template>
        </el-tree>
      </el-card>
    </template>

    <!-- 空状态 -->
    <el-empty v-else-if="!loading" description="请输入成品码进行层级追溯查询" />
  </AdminPage>
</template>

<style scoped>
.summary-card {
  margin-bottom: 0;
}

/* QR 占位图样式 */
.qr-box {
  display: flex;
  flex-direction: column;
  padding: 6px;
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  flex-shrink: 0;
}

.qr-row {
  display: flex;
}

.qr-cell {
  width: 6px;
  height: 6px;
  background: #fff;
}

.qr-cell--on {
  background: #18181b;
}

/* 树节点自定义渲染 */
.tree-node {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
  flex: 1;
}

.tree-node__main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tree-node__process {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.tree-node__user {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.tree-node__date {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.tree-node__sub {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding-left: 2px;
}

@media (max-width: 640px) {
  .tree-node__main {
    gap: 6px;
  }

  .tree-node__sub {
    gap: 8px;
  }
}
</style>
