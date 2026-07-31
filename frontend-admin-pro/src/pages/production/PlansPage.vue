<template>
  <AdminPage :title="t('production.plans.title')">
    <el-card>
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[16px] font-semibold">{{ t('production.plans.title') }}</div>
        <div class="flex items-center gap-2 flex-wrap">
          <el-button type="primary" @click="router.push('/plans/new')">{{ t('production.plans.addPlan') }}</el-button>
          <el-button @click="reload(true)">{{ t('production.common.refresh') }}</el-button>
        </div>
      </div>

      <el-alert
        v-if="automationSettings?.enabled"
        class="mt-4"
        type="success"
        :closable="false"
        show-icon
        :title="t('production.plans.automationEnabled')"
      >
        <span class="text-sm">
          订单确认可自动建计划；计划保存可自动排产/下发/派工。
          <el-button v-if="canAutomationSettings" link type="primary" @click="router.push('/system/automation-settings')">{{ t('production.plans.viewConfig') }}</el-button>
        </span>
      </el-alert>
      <el-alert
        v-else-if="canAutomationSettings"
        class="mt-4"
        type="info"
        :closable="true"
        show-icon
        :title="t('production.plans.enableAutomation')"
      >
        <el-button link type="primary" @click="router.push('/system/automation-settings')">{{ t('production.plans.goToSettings') }}</el-button>
      </el-alert>

      <div class="mt-4 flex items-center gap-2 flex-wrap">
        <el-input-number v-model="query.order_id" :min="1" :controls="false" :placeholder="t('production.plans.orderId')" style="width: 140px" @change="reload(true)" />
        <el-select v-model="query.status" clearable :placeholder="t('production.common.status')" style="width: 140px" @change="reload(true)">
          <el-option label="计划" value="planned" />
          <el-option label="进行中" value="in_progress" />
          <el-option label="已完成" value="done" />
          <el-option label="已取消" value="canceled" />
        </el-select>
        <el-date-picker
          v-model="query.range"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          @change="reload(true)"
        />
      </div>

      <el-tabs class="mt-4" v-model="activeTab">
        <el-tab-pane label="列表" name="list">
          <div class="mt-2" v-loading="loading">
            <el-table class="hidden lg:block w-full" :data="items" border>
              <el-table-column prop="id" label="ID" width="90" />
              <el-table-column prop="code" label="计划编号" width="180" />
              <el-table-column prop="order_code" label="订单号" width="220" />
              <el-table-column prop="customer_name" label="客户" width="180" />
              <el-table-column prop="qty" label="数量" width="110" />
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="start_date" label="开始" width="120" />
              <el-table-column prop="end_date" label="结束" width="120" />
              <el-table-column prop="work_days" label="工期(天)" width="110" />
              <el-table-column prop="remark" label="备注" min-width="220" />
              <el-table-column prop="created_at" label="创建时间" width="180" />
              <el-table-column label="操作" width="400" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
                  <el-button v-if="canAi" size="small" type="warning" plain :loading="aiPlanId === row.id && aiLoading" @click="openAiSchedule(row.id)">{{ t('production.plans.aiSchedule') }}</el-button>
                  <el-button size="small" @click="checkKit(row.id)">{{ t('production.plans.kitCheck') }}</el-button>
                  <el-button
                    v-if="row.can_release"
                    size="small"
                    type="primary"
                    :loading="releasingId === row.id"
                    @click="onReleasePlan(row)"
                  >
                    确认下发
                  </el-button>
                  <el-tag v-else-if="row.status === 'in_progress'" type="success" size="small">{{ t('production.plans.released') }}</el-tag>
                  <el-tag v-else-if="row.has_work_orders" type="warning" size="small">{{ t('production.plans.hasWorkOrders') }}</el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div class="lg:hidden space-y-3">
              <div v-for="row in items" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary truncate">{{ row.code }}</div>
                    <div class="text-xs text-el-placeholder">#{{ row.id }} · {{ row.order_code }}</div>
                  </div>
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>客户</dt>
                  <dd>{{ row.customer_name || '—' }}</dd>
                  <dt>数量</dt>
                  <dd>{{ row.qty }}</dd>
                  <dt>工期</dt>
                  <dd>{{ row.start_date }} ~ {{ row.end_date }}（{{ row.work_days }} 天）</dd>
                  <dt>备注</dt>
                  <dd>{{ row.remark || '—' }}</dd>
                  <dt>创建</dt>
                  <dd>{{ row.created_at }}</dd>
                </dl>
                <div class="admin-mobile-actions">
                  <el-button size="small" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
                  <el-button v-if="canAi" size="small" type="warning" plain @click="openAiSchedule(row.id)">{{ t('production.plans.aiSchedule') }}</el-button>
                  <el-button size="small" @click="checkKit(row.id)">{{ t('production.plans.kitCheck') }}</el-button>
                  <el-button
                    v-if="row.can_release"
                    size="small"
                    type="primary"
                    :loading="releasingId === row.id"
                    @click="onReleasePlan(row)"
                  >
                    确认下发
                  </el-button>
                </div>
              </div>
              <el-empty v-if="!loading && !items.length" description="暂无数据" />
            </div>
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
        </el-tab-pane>

        <el-tab-pane label="甘特图" name="gantt">
          <div class="mb-2 flex items-center gap-2 flex-wrap">
            <el-radio-group v-model="capacityUnit" size="small" @change="onCapacityUnitChange">
              <el-radio-button value="pieces">{{ t('production.plans.capacityPieces') }}</el-radio-button>
              <el-radio-button value="minutes">{{ t('production.plans.capacityMinutes') }}</el-radio-button>
            </el-radio-group>
            <div class="text-xs text-zinc-500">默认日产能（{{ capacityUnitLabel }}）</div>
            <el-input-number v-model="loadCapacity" :min="1" :max="10000" :controls="false" style="width: 140px" @change="loadLoad" />
            <el-button size="small" :loading="capacitySaving" @click="saveCapacity">{{ t('production.plans.saveAsDefault') }}</el-button>
            <el-button size="small" @click="openCalendar">{{ t('production.plans.workCalendar') }}</el-button>
            <el-button size="small" @click="openWorkshopCapacity">{{ t('production.plans.workshopCapacity') }}</el-button>
            <el-button size="small" @click="openUserCapacity">{{ t('production.plans.userCapacity') }}</el-button>
            <el-button size="small" @click="openEquipmentCapacity">{{ t('production.plans.equipmentCapacity') }}</el-button>
            <el-button size="small" type="primary" plain :loading="autoDispatch.loading" @click="runAutoDispatch">{{ t('production.plans.autoDispatch') }}</el-button>
            <div v-if="capacityUnit === 'pieces'" class="text-xs text-zinc-400">计件：每人/车间每天可完成的合格件数</div>
            <div v-else class="text-xs text-zinc-400">参考：480=8小时</div>
            <div class="hidden lg:block text-xs text-blue-600 w-full">{{ t('gantt.dragHint') }}</div>
          </div>
          <!-- 移动端：日负荷卡片 + 计划折叠面板（无横向甘特） -->
          <div class="lg:hidden space-y-3 mt-2" v-loading="planLoad.loading">
            <template v-if="ganttDays.length">
              <div class="text-sm font-medium text-zinc-700">日负荷（点行查看明细）</div>
              <div class="space-y-2">
                <div
                  v-for="d in ganttDays"
                  :key="`m-load-${d}`"
                  class="admin-mobile-row transition-colors"
                  :class="
                    loadMap.get(d)?.is_workday === false
                      ? 'opacity-60'
                      : 'active:bg-[var(--el-fill-color-light)] cursor-pointer'
                  "
                  @click="openLoadDetail(d)"
                >
                  <div class="flex justify-between items-center gap-2">
                    <span class="font-medium text-el-primary">{{ d }}</span>
                    <el-tag
                      v-if="loadMap.get(d)?.is_workday === false"
                      size="small"
                      type="info"
                    >休</el-tag>
                    <el-tag
                      v-else-if="loadMap.get(d)?.overload"
                      size="small"
                      type="danger"
                    >超负荷 {{ fmtLoad(loadMap.get(d)?.count) }}</el-tag>
                    <span v-else class="text-sm text-el-regular">{{ fmtLoad(loadMap.get(d)?.count) }}</span>
                  </div>
                </div>
              </div>
              <el-collapse class="border border-[var(--el-border-color-light)] rounded-lg overflow-hidden">
                <el-collapse-item v-for="p in items" :key="`m-gantt-${p.id}`" :name="String(p.id)">
                  <template #title>
                    <div class="flex flex-col items-start gap-0.5 min-w-0 py-0.5">
                      <span class="font-medium text-el-primary text-sm truncate max-w-[85vw]">{{ p.code }}</span>
                      <span class="text-xs text-zinc-500 truncate max-w-[85vw]">
                        <span v-if="p.order_code">{{ p.order_code }}</span>
                        <span v-if="p.customer_name"> · {{ p.customer_name }}</span>
                      </span>
                    </div>
                  </template>
                  <div class="space-y-2 pb-1">
                    <dl class="admin-mobile-kv">
                      <dt>状态</dt>
                      <dd>
                        <el-tag :type="statusTagType(p.status)" size="small">{{ statusLabel(p.status) }}</el-tag>
                      </dd>
                      <dt>数量</dt>
                      <dd>{{ p.qty }}</dd>
                      <dt>工期</dt>
                      <dd class="text-left">{{ p.start_date || '—' }} ~ {{ p.end_date || '—' }}（{{ p.work_days ?? '—' }} 天）</dd>
                    </dl>
                    <div v-if="barStyle(p)" class="space-y-1">
                      <div class="text-xs text-zinc-500">排产占比（相对当前视图）</div>
                      <div class="h-2 bg-zinc-100 rounded-full overflow-hidden">
                        <div class="h-full bg-blue-500/90 rounded-full transition-all" :style="{ width: barWidthPercent(p) }" />
                      </div>
                    </div>
                    <div class="admin-mobile-actions">
                      <el-button size="small" @click="router.push(`/plans/${p.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
                      <el-button size="small" @click="checkKit(p.id)">{{ t('production.plans.kitCheck') }}</el-button>
                      <el-button
                        v-if="p.can_release"
                        size="small"
                        type="primary"
                        :loading="releasingId === p.id"
                        @click="onReleasePlan(p)"
                      >
                        确认下发
                      </el-button>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </template>
            <el-empty v-else description="计划暂无起止日期，无法展示甘特" />
          </div>

          <div v-if="ganttDays.length" class="hidden lg:block border rounded overflow-x-auto">
            <div class="flex text-xs bg-zinc-50 border-b" :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }">
              <div class="shrink-0 px-2 py-2 font-medium border-r" :style="{ width: `${labelWidth}px` }">{{ t('production.plans.planned') }}</div>
              <div class="flex">
                <div
                  v-for="d in ganttDays"
                  :key="d"
                  class="px-1 py-2 text-center border-r last:border-r-0 text-zinc-600"
                  :style="{ width: `${dayWidth}px` }"
                >
                  {{ d.slice(5) }}
                </div>
              </div>
            </div>

            <div class="flex text-[11px] bg-white border-b" :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }">
              <div class="shrink-0 px-2 py-2 font-medium border-r text-zinc-600" :style="{ width: `${labelWidth}px` }">
                负荷（分钟/天）
              </div>
              <div class="flex">
                <div
                  v-for="d in ganttDays"
                  :key="`load-${d}`"
                  class="px-1 py-2 text-center border-r last:border-r-0"
                  :class="
                    loadMap.get(d)?.is_workday === false
                      ? 'bg-zinc-50 text-zinc-300'
                      : loadMap.get(d)?.overload
                        ? 'bg-red-50 text-red-600 font-medium cursor-pointer'
                        : 'text-zinc-500 cursor-pointer'
                  "
                  :style="{ width: `${dayWidth}px` }"
                  @click="openLoadDetail(d)"
                >
                  {{ loadMap.get(d)?.is_workday === false ? '休' : fmtLoad(loadMap.get(d)?.count) }}
                </div>
              </div>
            </div>

            <div
              v-for="p in items"
              :key="p.id"
              class="flex border-b last:border-b-0"
              :style="{ minWidth: `${labelWidth + ganttDays.length * dayWidth}px` }"
            >
              <div class="shrink-0 px-2 py-2 border-r text-sm" :style="{ width: `${labelWidth}px` }">
                <div class="font-medium">{{ p.code }}</div>
                <div class="text-xs text-zinc-500 truncate">
                  <span v-if="p.order_code">{{ p.order_code }}</span>
                  <span v-if="p.customer_name"> · {{ p.customer_name }}</span>
                </div>
              </div>
              <div class="relative" :style="{ width: `${ganttDays.length * dayWidth}px` }">
                <div class="absolute inset-0 flex">
                  <div v-for="d in ganttDays" :key="`${p.id}-${d}`" class="border-r last:border-r-0" :style="{ width: `${dayWidth}px` }" />
                </div>
                <div
                  v-if="barStyleWithDrag(p)"
                  class="absolute top-[10px] h-[14px] rounded bg-blue-500/80 cursor-grab active:cursor-grabbing hover:bg-blue-600/90 transition-colors"
                  :class="{ 'ring-2 ring-blue-300': ganttDrag.planId === p.id }"
                  :style="barStyleWithDrag(p) as any"
                  @pointerdown.stop.prevent="onGanttBarDown($event, p)"
                />
              </div>
            </div>
          </div>
          <el-empty v-else class="hidden lg:block" description="暂无可展示计划" />
          <el-empty v-if="!items.length" class="lg:hidden mt-2" description="暂无可展示计划" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-drawer v-model="loadDetail.open" size="720px" :title="`负荷明细：${loadDetail.day || '-'}`" destroy-on-close>
      <div v-loading="loadDetail.loading">
        <!-- PC：表格 -->
        <div class="hidden lg:block">
          <el-table v-if="loadDetail.workshops.length" class="mb-3" :data="loadDetail.workshops" border>
            <el-table-column prop="workshop" label="车间" min-width="160" />
            <el-table-column label="负荷" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.minutes) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="产能" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.capacity) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-if="loadDetail.users.length" class="mb-3" :data="loadDetail.users" border>
            <el-table-column prop="name" label="人员" min-width="160" />
            <el-table-column label="负荷" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.minutes) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="产能" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.capacity) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-if="loadDetail.equipments.length" class="mb-3" :data="loadDetail.equipments" border>
            <el-table-column prop="name" label="设备" min-width="160" />
            <el-table-column label="负荷" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.minutes) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="产能" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.capacity) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-if="loadDetail.items.length" :data="loadDetail.items" border>
            <el-table-column prop="code" label="计划编号" width="180" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="日期范围" min-width="220">
              <template #default="{ row }">
                <span>{{ row.start_date || '-' }} ~ {{ row.end_date || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="负荷贡献" width="140">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.daily_minutes) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="总工时" width="120">
              <template #default="{ row }">
                <span>{{ fmtLoad(row.total_minutes) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="采购入库" width="160">
              <template #default="{ row }">
                <span>{{ row.purchase_received_qty }} / {{ row.purchase_total_qty }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 移动端：折叠 + 卡片 -->
        <el-collapse v-model="loadDetailMobileCollapse" class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg">
          <el-collapse-item title="车间负荷" name="ws">
            <div v-if="loadDetail.workshops.length" class="space-y-2">
              <div v-for="(row, i) in loadDetail.workshops" :key="`ws-${i}-${row.workshop}`" class="admin-mobile-row">
                <div class="font-medium text-sm">{{ row.workshop }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>负荷</dt>
                  <dd>{{ fmtLoad(row.minutes) }}</dd>
                  <dt>产能</dt>
                  <dd>{{ fmtLoad(row.capacity) }}</dd>
                  <dt>状态</dt>
                  <dd>
                    <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
                  </dd>
                </dl>
              </div>
            </div>
            <el-empty v-else description="暂无" :image-size="64" />
          </el-collapse-item>
          <el-collapse-item title="人员负荷" name="user">
            <div v-if="loadDetail.users.length" class="space-y-2">
              <div v-for="(row, i) in loadDetail.users" :key="`u-${i}-${row.name}`" class="admin-mobile-row">
                <div class="font-medium text-sm">{{ row.name }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>负荷</dt>
                  <dd>{{ fmtLoad(row.minutes) }}</dd>
                  <dt>产能</dt>
                  <dd>{{ fmtLoad(row.capacity) }}</dd>
                  <dt>状态</dt>
                  <dd>
                    <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
                  </dd>
                </dl>
              </div>
            </div>
            <el-empty v-else description="暂无" :image-size="64" />
          </el-collapse-item>
          <el-collapse-item title="设备负荷" name="eq">
            <div v-if="loadDetail.equipments.length" class="space-y-2">
              <div v-for="(row, i) in loadDetail.equipments" :key="`e-${i}-${row.name}`" class="admin-mobile-row">
                <div class="font-medium text-sm">{{ row.name }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>负荷</dt>
                  <dd>{{ fmtLoad(row.minutes) }}</dd>
                  <dt>产能</dt>
                  <dd>{{ fmtLoad(row.capacity) }}</dd>
                  <dt>状态</dt>
                  <dd>
                    <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
                  </dd>
                </dl>
              </div>
            </div>
            <el-empty v-else description="暂无" :image-size="64" />
          </el-collapse-item>
          <el-collapse-item title="计划贡献" name="plans">
            <div v-if="loadDetail.items.length" class="space-y-2">
              <div v-for="row in loadDetail.items" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <span class="font-medium text-sm">{{ row.code }}</span>
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>日期</dt>
                  <dd class="text-left">{{ row.start_date || '—' }} ~ {{ row.end_date || '—' }}</dd>
                  <dt>负荷贡献</dt>
                  <dd>{{ fmtLoad(row.daily_minutes) }}</dd>
                  <dt>总工时</dt>
                  <dd>{{ fmtLoad(row.total_minutes) }}</dd>
                  <dt>采购入库</dt>
                  <dd>{{ row.purchase_received_qty }} / {{ row.purchase_total_qty }}</dd>
                </dl>
                <div class="admin-mobile-actions">
                  <el-button size="small" type="primary" @click="router.push(`/plans/${row.id}/edit`)">{{ t('production.plans.edit') }}</el-button>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无计划明细" :image-size="64" />
          </el-collapse-item>
        </el-collapse>

        <el-empty
          v-if="
            !loadDetail.loading &&
            !loadDetail.workshops.length &&
            !loadDetail.users.length &&
            !loadDetail.equipments.length &&
            !loadDetail.items.length
          "
          class="mt-2"
          description="暂无明细"
        />
      </div>
    </el-drawer>

    <el-drawer v-model="kit.open" size="980px" title="齐套检查" destroy-on-close>
      <div v-loading="kit.loading">
        <div v-if="kit.data" class="space-y-3">
          <div class="border rounded p-3 bg-white">
            <div class="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <div class="font-medium">{{ kit.data.plan_code }}</div>
                <div class="text-xs text-zinc-500 mt-1">
                  <span v-if="kit.data.order_code">{{ kit.data.order_code }}</span>
                  <span v-if="kit.data.customer_name"> · {{ kit.data.customer_name }}</span>
                </div>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <el-button
                  v-if="kitCanRelease"
                  type="success"
                  :loading="releasingId === kit.planId"
                  @click="onReleasePlanById(kit.planId!)"
                >
                  确认下发（生成工单）
                </el-button>
                <el-select v-model="kit.supplier_id" clearable filterable placeholder="选择供应商" style="width: 260px">
                  <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
                </el-select>
                <el-button type="primary" :loading="kit.creating" :disabled="!canCreatePurchase" @click="onCreatePurchase">
                  一键生成采购单
                </el-button>
              </div>
            </div>
          </div>

          <el-alert
            v-if="kit.data.missing_boms.length"
            title="存在未配置 BOM 的产品型号，需先补齐 BOM 后再生成采购单"
            type="warning"
            show-icon
            :closable="false"
          />

          <div class="hidden lg:block space-y-3">
            <div class="border rounded bg-white">
              <div class="px-3 py-2 border-b bg-zinc-50 flex items-center justify-between">
                <div class="font-medium">已生成采购单</div>
                <div class="text-xs text-zinc-500">
                  <span>数量：{{ kit.purchaseOrders.length }}</span>
                  <span class="ml-3">已入库：{{ poReceivedCount }}</span>
                </div>
              </div>
              <div v-loading="kit.loadingPOs">
                <el-table v-if="kit.purchaseOrders.length" class="w-full" :data="kit.purchaseOrders" border>
                <el-table-column prop="code" label="采购单号" min-width="220" />
                <el-table-column label="供应商" min-width="220">
                  <template #default="{ row }">
                    <span>{{ row.supplier_name || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="140">
                  <template #default="{ row }">
                    <el-tag :type="poStatusTag(row.status)">{{ poStatusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="入库进度" width="180">
                  <template #default="{ row }">
                    <span>{{ row.received_qty }} / {{ row.total_qty }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">详情</el-button>
                  </template>
                </el-table-column>
                </el-table>
                <el-empty v-if="!kit.purchaseOrders.length" description="暂无采购单（可用上方按钮一键生成）" />
              </div>
            </div>

            <div class="border rounded bg-white">
              <div class="px-3 py-2 border-b bg-zinc-50 flex items-center justify-between">
                <div class="font-medium">缺料明细</div>
                <div class="text-xs text-zinc-500">
                  <span>缺料行：{{ shortageCount }}</span>
                  <span class="ml-3">过滤后：{{ kitItems.length }}</span>
                </div>
              </div>
              <el-table class="w-full" :data="kitItems" border>
              <el-table-column prop="material_code" label="物料编码" width="180" />
              <el-table-column prop="material_name" label="物料名称" min-width="220" />
              <el-table-column prop="unit" label="单位" width="100" />
              <el-table-column prop="spec" label="规格" min-width="180" />
              <el-table-column prop="demand_qty" label="需求" width="110" />
              <el-table-column prop="stock_qty" label="库存" width="110" />
              <el-table-column label="缺口" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.shortage_qty > 0 ? 'danger' : 'success'">{{ row.shortage_qty }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="供应商" width="220">
                <template #default="{ row }">
                  <span>{{ supplierLabel(row.supplier_id) }}</span>
                </template>
              </el-table-column>
              </el-table>
            </div>
          </div>

          <el-collapse v-model="kitMobileCollapse" class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg overflow-hidden">
            <el-collapse-item name="po">
              <template #title>
                <span class="font-medium">已生成采购单</span>
                <span class="text-xs text-zinc-500 ml-2">({{ kit.purchaseOrders.length }})</span>
              </template>
              <div v-loading="kit.loadingPOs" class="space-y-2">
                <template v-if="kit.purchaseOrders.length">
                  <div v-for="row in kit.purchaseOrders" :key="row.id" class="admin-mobile-row">
                    <div class="admin-mobile-row__head">
                      <div class="min-w-0">
                        <div class="font-medium text-sm truncate">{{ row.code }}</div>
                        <div class="text-xs text-zinc-500">{{ row.supplier_name || '—' }}</div>
                      </div>
                      <el-tag :type="poStatusTag(row.status)" size="small">{{ poStatusLabel(row.status) }}</el-tag>
                    </div>
                    <dl class="admin-mobile-kv">
                      <dt>入库</dt>
                      <dd>{{ row.received_qty }} / {{ row.total_qty }}</dd>
                      <dt>创建</dt>
                      <dd>{{ row.created_at || '—' }}</dd>
                    </dl>
                    <div class="admin-mobile-actions">
                      <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">详情</el-button>
                    </div>
                  </div>
                </template>
                <el-empty v-else description="暂无采购单" :image-size="64" />
              </div>
            </el-collapse-item>
            <el-collapse-item name="kit">
              <template #title>
                <span class="font-medium">缺料明细</span>
                <span class="text-xs text-zinc-500 ml-2">缺料 {{ shortageCount }} · 显示 {{ kitItems.length }}</span>
              </template>
              <div class="space-y-2">
                <div v-for="(row, idx) in kitItems" :key="`${row.material_code}-${idx}`" class="admin-mobile-row">
                  <div class="font-medium text-sm">{{ row.material_name || row.material_code }}</div>
                  <div class="text-xs text-zinc-500">{{ row.material_code }} · {{ row.spec || '—' }}</div>
                  <dl class="admin-mobile-kv mt-2">
                    <dt>需求</dt>
                    <dd>{{ row.demand_qty }} {{ row.unit || '' }}</dd>
                    <dt>库存</dt>
                    <dd>{{ row.stock_qty }}</dd>
                    <dt>缺口</dt>
                    <dd>
                      <el-tag :type="row.shortage_qty > 0 ? 'danger' : 'success'" size="small">{{ row.shortage_qty }}</el-tag>
                    </dd>
                    <dt>供应商</dt>
                    <dd class="text-left">{{ supplierLabel(row.supplier_id) }}</dd>
                  </dl>
                </div>
                <el-empty v-if="!kitItems.length" description="无缺料行" :image-size="64" />
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <el-empty v-else description="暂无数据" />
      </div>
    </el-drawer>

    <el-dialog v-model="calendar.open" width="980px" title="生产日历" destroy-on-close>
      <div v-loading="calendar.loading">
        <div class="mb-3 flex items-center gap-2 flex-wrap">
          <div class="text-xs text-zinc-500">月份</div>
          <el-date-picker v-model="calendar.month" type="month" value-format="YYYY-MM" :clearable="false" style="width: 140px" @change="loadCalendar" />
          <div class="text-xs text-zinc-400">默认产能：{{ calendar.default_capacity }} {{ capacityUnitLabel }}</div>
        </div>
        <div class="flex flex-col gap-3 lg:grid lg:grid-cols-2">
          <div class="border rounded hidden lg:block">
            <el-table :data="calendar.rows" height="520" border @row-click="(row: any) => selectCalendarDay(row.day)">
              <el-table-column prop="day" label="日期" width="120" />
              <el-table-column prop="weekday_label" label="星期" width="80" />
              <el-table-column label="工作" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.is_workday ? 'success' : 'info'">{{ row.is_workday ? '是' : '否' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="产能" width="110">
                <template #default="{ row }">
                  <span>{{ row.is_workday ? row.capacity_minutes : '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="覆盖" width="90">
                <template #default="{ row }">
                  <el-tag v-if="row.has_override" type="warning">覆盖</el-tag>
                  <span v-else class="text-zinc-400">默认</span>
                </template>
              </el-table-column>
              <el-table-column prop="remark" label="备注" />
            </el-table>
          </div>

          <div class="lg:hidden border rounded p-2 max-h-[min(42vh,360px)] overflow-y-auto space-y-2 bg-zinc-50/50">
            <div
              v-for="row in calendar.rows"
              :key="row.day"
              class="admin-mobile-row cursor-pointer transition-shadow"
              :class="calendar.selected_day === row.day ? 'ring-2 ring-[var(--el-color-primary)]' : ''"
              @click="selectCalendarDay(row.day)"
            >
              <div class="admin-mobile-row__head">
                <div>
                  <div class="font-medium text-sm">{{ row.day }} · 周{{ row.weekday_label }}</div>
                  <div class="text-xs text-zinc-500 mt-0.5">
                    产能 {{ row.is_workday ? row.capacity_minutes : '—' }} 分
                    <span v-if="row.has_override" class="ml-2 text-amber-600">已覆盖</span>
                  </div>
                </div>
                <el-tag :type="row.is_workday ? 'success' : 'info'" size="small">{{ row.is_workday ? '工作日' : '休息' }}</el-tag>
              </div>
              <div v-if="row.remark" class="text-xs text-zinc-600 mt-1">{{ row.remark }}</div>
            </div>
          </div>

          <div class="border rounded p-3 lg:min-h-0">
            <div class="font-medium mb-2">日期：{{ calendar.selected_day || '-' }}</div>
            <div v-if="calendar.selected_day" class="space-y-3">
              <div class="flex items-center gap-3">
                <div class="text-sm text-zinc-600 w-20 shrink-0">工作日</div>
                <el-switch v-model="calendar.form.is_workday" />
              </div>
              <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                <div class="text-sm text-zinc-600 w-20 shrink-0">产能(分)</div>
                <div class="flex flex-wrap items-center gap-2">
                  <el-input-number
                    v-model="calendar.form.capacity_minutes"
                    :min="0"
                    :max="10000"
                    :controls="false"
                    class="!w-36"
                    :disabled="!calendar.form.is_workday"
                  />
                  <div class="text-xs text-zinc-400">留空/0=使用默认</div>
                </div>
              </div>
              <div class="flex flex-col gap-2">
                <div class="text-sm text-zinc-600 w-20">备注</div>
                <el-input v-model="calendar.form.remark" placeholder="可选" />
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <el-button type="primary" :loading="calendar.saving" @click="saveCalendarDay">保存</el-button>
                <el-button :loading="calendar.resetting" @click="resetCalendarDay">清除覆盖</el-button>
              </div>
            </div>
            <el-empty v-else description="点击日历中的日期进行设置" />
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="workshopCapacity.open" width="720px" title="车间日产能（分钟/天）" destroy-on-close>
      <div v-loading="workshopCapacity.loading">
        <div class="mb-3 text-xs text-zinc-500">默认产能：{{ workshopCapacity.default_capacity }} {{ capacityUnitLabel }}（未覆盖的车间按默认产能）</div>
        <el-table class="hidden lg:block" :data="workshopCapacity.rows" border height="520">
          <el-table-column prop="workshop" label="车间" min-width="220" />
          <el-table-column label="日产能(分)" width="220">
            <template #default="{ row }">
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
              <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
          <div v-for="(row, i) in workshopCapacity.rows" :key="`w-${i}-${row.workshop}`" class="admin-mobile-row">
            <div class="font-medium text-sm">{{ row.workshop }}</div>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <span class="text-xs text-zinc-500 shrink-0">日产能(分)</span>
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
              <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </div>
          </div>
        </div>
        <div class="mt-3 flex justify-end gap-2">
          <el-button :loading="workshopCapacity.saving" type="primary" @click="saveWorkshopCapacity">保存</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="userCapacity.open" width="720px" :title="`人员日产能（${capacityUnitLabel}）`" destroy-on-close>
      <div v-loading="userCapacity.loading">
        <div class="mb-3 text-xs text-zinc-500">
          默认产能：{{ userCapacity.default_capacity }} {{ capacityUnitLabel }}；仅显示「员工」角色（与自动派工一致）
        </div>
        <el-table class="hidden lg:block" :data="userCapacity.rows" border height="520">
          <el-table-column prop="name" label="人员" min-width="220" />
          <el-table-column :label="`日产能(${capacityUnitLabel})`" width="220">
            <template #default="{ row }">
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
              <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
          <div v-for="(row, i) in userCapacity.rows" :key="`u-${i}-${row.user_id}`" class="admin-mobile-row">
            <div class="font-medium text-sm">{{ row.name }}</div>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <span class="text-xs text-zinc-500 shrink-0">日产能({{ capacityUnitLabel }})</span>
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
              <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </div>
          </div>
        </div>
        <div class="mt-3 flex justify-end gap-2">
          <el-button :loading="userCapacity.saving" type="primary" @click="saveUserCapacity">保存</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="equipmentCapacity.open" width="720px" title="设备日产能（分钟/天）" destroy-on-close>
      <div v-loading="equipmentCapacity.loading">
        <div class="mb-3 text-xs text-zinc-500">默认产能：{{ equipmentCapacity.default_capacity }} {{ capacityUnitLabel }}（未覆盖的设备按默认产能）</div>
        <el-table class="hidden lg:block" :data="equipmentCapacity.rows" border height="520">
          <el-table-column prop="name" label="设备" min-width="260" />
          <el-table-column label="日产能(分)" width="220">
            <template #default="{ row }">
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" style="width: 160px" />
              <span class="ml-2 text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="lg:hidden space-y-2 max-h-[min(60vh,480px)] overflow-y-auto">
          <div v-for="(row, i) in equipmentCapacity.rows" :key="`e-${i}-${row.equipment_id}`" class="admin-mobile-row">
            <div class="font-medium text-sm">{{ row.name }}</div>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <span class="text-xs text-zinc-500 shrink-0">日产能(分)</span>
              <el-input-number v-model="row.capacity_minutes" :min="0" :max="10000" :controls="false" class="!w-36" />
              <span class="text-xs text-zinc-400">{{ row.capacity_minutes <= 0 ? '默认' : '覆盖' }}</span>
            </div>
          </div>
        </div>
        <div class="mt-3 flex justify-end gap-2">
          <el-button :loading="equipmentCapacity.saving" type="primary" @click="saveEquipmentCapacity">保存</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="autoDispatch.open" width="860px" title="自动派工结果" destroy-on-close>
      <div v-loading="autoDispatch.loading">
        <el-alert
          v-if="autoDispatch.result"
          class="mb-3"
          :title="`本次派工：${autoDispatch.result.assigned_count} 条（参与任务：${autoDispatch.result.task_count}，工期工作日：${autoDispatch.result.span_workdays}）`"
          type="success"
          show-icon
          :closable="false"
        />
        <el-alert v-if="autoDispatch.result && autoDispatch.result.overloads.length" class="mb-3" title="存在超负荷项，请优先处理" type="warning" show-icon :closable="false" />

        <div class="hidden lg:block space-y-3">
          <el-table v-if="autoDispatch.result && autoDispatch.result.overloads.length" :data="autoDispatch.result.overloads" border>
            <el-table-column prop="type" label="类型" width="120" />
            <el-table-column prop="name" label="对象" min-width="220" />
            <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
            <el-table-column prop="capacity" label="日产能(分)" width="140" />
          </el-table>
          <el-table v-if="autoDispatch.result" :data="autoDispatch.result.workshops" border>
            <el-table-column prop="workshop" label="车间" min-width="160" />
            <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
            <el-table-column prop="capacity" label="日产能(分)" width="140" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-table v-if="autoDispatch.result" :data="autoDispatch.result.users" border>
            <el-table-column prop="name" label="人员" min-width="160" />
            <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
            <el-table-column prop="capacity" label="日产能(分)" width="140" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-collapse
          v-if="autoDispatch.result"
          v-model="autoDispatchMobileCollapse"
          class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg overflow-hidden"
        >
          <el-collapse-item v-if="autoDispatch.result.overloads.length" name="overload">
            <template #title>
              <span class="font-medium">超负荷项</span>
              <span class="text-xs text-zinc-500 ml-2">({{ autoDispatch.result.overloads.length }})</span>
            </template>
            <div class="space-y-2">
              <div v-for="(row, i) in autoDispatch.result.overloads" :key="`ol-${i}-${row.name}`" class="admin-mobile-row">
                <div class="font-medium text-sm">{{ row.type }} · {{ row.name }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>日负荷</dt>
                  <dd>{{ row.daily_minutes }} 分</dd>
                  <dt>日产能</dt>
                  <dd>{{ row.capacity }} 分</dd>
                </dl>
              </div>
            </div>
          </el-collapse-item>
          <el-collapse-item name="ws">
            <template #title>
              <span class="font-medium">车间负荷</span>
              <span class="text-xs text-zinc-500 ml-2">({{ autoDispatch.result.workshops.length }})</span>
            </template>
            <div class="space-y-2">
              <div v-for="(row, i) in autoDispatch.result.workshops" :key="`adw-${i}-${row.workshop}`" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="font-medium text-sm">{{ row.workshop }}</div>
                  <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
                </div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>日负荷</dt>
                  <dd>{{ row.daily_minutes }} 分</dd>
                  <dt>日产能</dt>
                  <dd>{{ row.capacity }} 分</dd>
                </dl>
              </div>
            </div>
          </el-collapse-item>
          <el-collapse-item name="users">
            <template #title>
              <span class="font-medium">人员负荷</span>
              <span class="text-xs text-zinc-500 ml-2">({{ autoDispatch.result.users.length }})</span>
            </template>
            <div class="space-y-2">
              <div v-for="(row, i) in autoDispatch.result.users" :key="`adu-${i}-${row.name}`" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="font-medium text-sm">{{ row.name }}</div>
                  <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
                </div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>日负荷</dt>
                  <dd>{{ row.daily_minutes }} 分</dd>
                  <dt>日产能</dt>
                  <dd>{{ row.capacity }} 分</dd>
                </dl>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-dialog>
    <el-dialog v-model="aiDlg.open" :title="aiDlg.title" width="720px" destroy-on-close>
      <el-tabs v-model="aiDlg.tab">
        <el-tab-pane label="LLM 建议" name="llm">
          <div v-loading="aiLoading" class="text-sm whitespace-pre-wrap text-zinc-700">{{ aiDlg.text }}</div>
          <ul v-if="aiDlg.list.length" class="mt-3 list-disc pl-5 text-sm text-zinc-600">
            <li v-for="(t, i) in aiDlg.list" :key="i">{{ t }}</li>
          </ul>
        </el-tab-pane>
        <el-tab-pane label="OR-Tools 约束" name="optimizer">
          <div v-loading="aiOptimizeLoading" class="text-sm text-zinc-700">
            <p v-if="lastOptimize?.suggest_start_date">
              方案（{{ lastOptimize.solver || 'rule' }}）：
              {{ lastOptimize.suggest_start_date }} ~ {{ lastOptimize.suggest_end_date }}，
              工期 {{ lastOptimize.suggest_work_days }} 天，总工时 {{ lastOptimize.total_minutes }} 分
            </p>
            <ul v-if="lastOptimize?.notes?.length" class="mt-2 list-disc pl-5">
              <li v-for="(n, i) in lastOptimize.notes" :key="i">{{ n }}</li>
            </ul>
            <p v-else-if="!aiOptimizeLoading" class="text-zinc-400">暂无优化结果</p>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template v-if="aiDlg.mode === 'schedule'" #footer>
        <el-button @click="aiDlg.open = false">关闭</el-button>
        <el-button type="primary" :loading="aiApplying" @click="applyAiSchedule">采纳 LLM 并执行</el-button>
        <el-button type="success" plain :loading="aiApplying" :disabled="!lastOptimize?.ok" @click="applyOptimizerSchedule">
          采纳 OR-Tools 并执行
        </el-button>
        <el-button @click="router.push(`/plans/${aiPlanId}/edit`)">去编辑页</el-button>
      </template>
    </el-dialog>

    <PlanReadinessDrawer
      v-model="readiness.open"
      :plan-id="readiness.planId"
      show-release
      :can-release="readiness.canRelease"
      :releasing="releasingId === readiness.planId"
      title="投产就绪检查"
      @release="onReleaseFromReadiness"
      @closed="readiness.planId = null"
    />  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useStatus } from '@/utils/status-maps'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  plansApi,
  type PlanCalendarDayOut,
  type PlanLoadDetailItemOut,
  type PlanLoadEquipmentOut,
  type PlanLoadItemOut,
  type PlanLoadUserOut,
  type PlanLoadWorkshopOut,
  type PlanEquipmentCapacityOut,
  type PlanOut,
  type PlanWorkshopCapacityOut,
  type PlanUserCapacityOut,
} from '@/api/plans'
import { purchaseApi, type KittingOut, type PlanKittingPurchaseOrderOut } from '@/api/purchase'
import PlanReadinessDrawer from '@/components/PlanReadinessDrawer.vue'
import { materialsApi, type SupplierOut } from '@/api/materials'
import { masterApi, type ProcessOut } from '@/api/master'
import { systemApi, type UserOut } from '@/api/system'
import { http } from '@/utils/http'
import { equipmentOptionLabel, partyOptionLabel } from '@/utils/display'
import { aiApi, type PlanScheduleOut, type PlanOptimizeOut } from '@/api/ai'
import { automationApi, type AutomationSettings } from '@/api/automation'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const { label: statusLabel, type: statusTagType } = useStatus('plan')
const auth = useAuthStore()
const canAi = computed(() => auth.hasAnyPermission(['ai.use', 'plan.manage']))
const canAutomationSettings = computed(() => auth.hasAnyPermission(['setting.manage']))
const automationSettings = ref<AutomationSettings | null>(null)

const loading = ref(false)
const releasingId = ref<number | null>(null)
const aiPlanId = ref<number | null>(null)
const aiLoading = ref(false)
const aiOptimizeLoading = ref(false)
const aiApplying = ref(false)
const lastScheduleSuggest = ref<PlanScheduleOut | null>(null)
const lastOptimize = ref<PlanOptimizeOut | null>(null)
const aiDlg = reactive({
  open: false,
  title: '智能排产建议',
  text: '',
  list: [] as string[],
  mode: 'schedule' as 'schedule' | 'risk',
  tab: 'llm' as 'llm' | 'optimizer',
})
const items = ref<PlanOut[]>([])
const activeTab = ref<'list' | 'gantt'>('list')

const query = reactive({
  status: '',
  order_id: null as number | null,
  range: [] as string[],
  offset: 0,
  limit: 50,
})

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const labelWidth = 280
const dayWidth = 26
const loadCapacity = ref(300)
const capacityUnit = ref<'pieces' | 'minutes'>('pieces')
const capacityUnitLabel = computed(() => (capacityUnit.value === 'pieces' ? '件/天' : '分钟/天'))
const capacitySaving = ref(false)

const planLoad = reactive({
  loading: false,
  items: [] as PlanLoadItemOut[],
})

const loadMap = computed(() => new Map(planLoad.items.map((x) => [x.date, x])))

const loadDetail = reactive({
  open: false,
  loading: false,
  day: '',
  items: [] as PlanLoadDetailItemOut[],
  workshops: [] as PlanLoadWorkshopOut[],
  users: [] as PlanLoadUserOut[],
  equipments: [] as PlanLoadEquipmentOut[],
})

const loadDetailMobileCollapse = ref(['ws', 'user', 'eq', 'plans'])
const kitMobileCollapse = ref(['po', 'kit'])

const calendar = reactive({
  open: false,
  loading: false,
  month: '',
  default_workdays: [] as number[],
  default_capacity: 480,
  items: [] as PlanCalendarDayOut[],
  rows: [] as {
    day: string
    weekday_label: string
    is_workday: boolean
    capacity_minutes: number
    has_override: boolean
    remark: string
  }[],
  selected_day: '',
  form: {
    is_workday: true,
    capacity_minutes: 0,
    remark: '' as string,
  },
  saving: false,
  resetting: false,
})

const workshopCapacity = reactive({
  open: false,
  loading: false,
  saving: false,
  default_capacity: 480,
  rows: [] as { workshop: string; capacity_minutes: number }[],
})

const userCapacity = reactive({
  open: false,
  loading: false,
  saving: false,
  default_capacity: 480,
  rows: [] as { user_id: number; name: string; capacity_minutes: number }[],
})

const equipmentCapacity = reactive({
  open: false,
  loading: false,
  saving: false,
  default_capacity: 480,
  rows: [] as { equipment_id: number; name: string; capacity_minutes: number }[],
})

const autoDispatchMobileCollapse = ref(['ws', 'users'])

const autoDispatch = reactive({
  open: false,
  loading: false,
  result: null as null | {
    assigned_count: number
    task_count: number
    span_workdays: number
    users: any[]
    workshops: any[]
    overloads: any[]
  },
})

const ganttDays = computed(() => {
  const ms: number[] = []
  for (const p of items.value) {
    const s = p.start_date || p.end_date
    const e = p.end_date || p.start_date
    if (!s || !e) continue
    ms.push(toMs(s), toMs(e))
  }
  if (!ms.length) return []
  const min = Math.min(...ms)
  const max = Math.max(...ms)
  const days = Math.max(1, Math.floor((max - min) / 86400000) + 1)
  const out: string[] = []
  for (let i = 0; i < days; i++) out.push(fromMs(min + i * 86400000))
  return out
})

function toMs(s: string) {
  return new Date(`${s}T00:00:00`).getTime()
}

function fromMs(ms: number) {
  const d = new Date(ms)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function monthStartEnd(month: string) {
  const [y0, m0] = month.split('-')
  const y = Number(y0)
  const m = Number(m0)
  const start = `${y0}-${m0}-01`
  const last = new Date(y, m, 0).getDate()
  const end = `${y0}-${m0}-${String(last).padStart(2, '0')}`
  return { start, end, days: last }
}

function isoWeekday(day: string) {
  const d = new Date(`${day}T00:00:00`)
  const w = d.getDay()
  return w === 0 ? 7 : w
}

function weekdayLabel(day: string) {
  const labels = ['日', '一', '二', '三', '四', '五', '六']
  const d = new Date(`${day}T00:00:00`)
  return labels[d.getDay()]
}

async function openCalendar() {
  if (!calendar.month) calendar.month = fromMs(Date.now()).slice(0, 7)
  calendar.open = true
  await loadCalendar()
}

async function loadCalendar() {
  if (!calendar.month) return
  calendar.loading = true
  try {
    const { start, end, days } = monthStartEnd(calendar.month)
    const res = await plansApi.listCalendar({ date_from: start, date_to: end })
    calendar.items = res.items || []
    calendar.default_workdays = res.default_workdays || []
    calendar.default_capacity = res.default_capacity || 480
    const map = new Map(calendar.items.map((x) => [x.day, x]))
    const rows = []
    for (let i = 1; i <= days; i++) {
      const d = `${calendar.month}-${String(i).padStart(2, '0')}`
      const ov = map.get(d)
      const isWork = ov ? ov.is_workday : calendar.default_workdays.includes(isoWeekday(d))
      const cap = isWork ? (ov?.capacity_minutes ?? calendar.default_capacity) : 0
      rows.push({
        day: d,
        weekday_label: weekdayLabel(d),
        is_workday: Boolean(isWork),
        capacity_minutes: Number(cap || 0),
        has_override: Boolean(ov),
        remark: (ov?.remark || '') as string,
      })
    }
    calendar.rows = rows
    if (calendar.selected_day) selectCalendarDay(calendar.selected_day)
  } finally {
    calendar.loading = false
  }
}

function selectCalendarDay(day: string) {
  calendar.selected_day = day
  const map = new Map(calendar.items.map((x) => [x.day, x]))
  const ov = map.get(day)
  const isWork = ov ? ov.is_workday : calendar.default_workdays.includes(isoWeekday(day))
  calendar.form.is_workday = Boolean(isWork)
  calendar.form.capacity_minutes = ov?.capacity_minutes ?? 0
  calendar.form.remark = (ov?.remark || '') as string
}

async function saveCalendarDay() {
  if (!calendar.selected_day) return
  if (calendar.saving) return
  calendar.saving = true
  try {
    const cap = calendar.form.is_workday ? (calendar.form.capacity_minutes > 0 ? calendar.form.capacity_minutes : null) : null
    await plansApi.upsertCalendarDay({
      day: calendar.selected_day,
      is_workday: calendar.form.is_workday,
      capacity_minutes: cap,
      remark: calendar.form.remark || null,
    })
    ElMessage.success(t('production.plans.calendarSaved'))
    await loadCalendar()
    await loadLoad()
  } finally {
    calendar.saving = false
  }
}

async function resetCalendarDay() {
  if (!calendar.selected_day) return
  if (calendar.resetting) return
  calendar.resetting = true
  try {
    const res = await plansApi.deleteCalendarDay(calendar.selected_day)
    if (res.deleted) ElMessage.success(t('production.plans.overrideCleared'))
    await loadCalendar()
    await loadLoad()
  } finally {
    calendar.resetting = false
  }
}

async function openWorkshopCapacity() {
  workshopCapacity.open = true
  workshopCapacity.loading = true
  try {
    const [capRes, procRes] = await Promise.all([
      plansApi.getWorkshopCapacities(),
      masterApi.listProcesses({ keyword: '', offset: 0, limit: 200, include_inactive: true }),
    ])

    const workshops = new Set<string>()
    for (const p of procRes.items as ProcessOut[]) {
      const w = (p.workshop || '').trim()
      if (w) workshops.add(w)
    }
    workshops.add('未分车间')

    const capMap = new Map((capRes.items || []).map((x: PlanWorkshopCapacityOut) => [x.workshop, x.capacity_minutes]))
    workshopCapacity.default_capacity = capRes.default_capacity || 480
    workshopCapacity.rows = Array.from(workshops)
      .sort((a, b) => a.localeCompare(b))
      .map((w) => ({
        workshop: w,
        capacity_minutes: capMap.get(w) ?? 0,
      }))
  } finally {
    workshopCapacity.loading = false
  }
}

async function saveWorkshopCapacity() {
  if (workshopCapacity.saving) return
  workshopCapacity.saving = true
  try {
    const def = workshopCapacity.default_capacity || 480
    const items = workshopCapacity.rows
      .filter((x) => x.capacity_minutes > 0 && x.capacity_minutes !== def)
      .map((x) => ({ workshop: x.workshop, capacity_minutes: x.capacity_minutes }))
    await plansApi.setWorkshopCapacities(items)
    ElMessage.success(t('production.plans.workshopCapacitySaved'))
    await loadLoad()
    if (loadDetail.open && loadDetail.day) await openLoadDetail(loadDetail.day)
  } finally {
    workshopCapacity.saving = false
  }
}

async function openUserCapacity() {
  userCapacity.open = true
  userCapacity.loading = true
  try {
    const capRes = await plansApi.getUserCapacityRows()
    userCapacity.default_capacity = capRes.default_capacity || 480
    userCapacity.rows = (capRes.items || []).map((x) => ({
      user_id: x.user_id,
      name: x.name,
      capacity_minutes: x.capacity_minutes ?? 0,
    }))
  } finally {
    userCapacity.loading = false
  }
}

async function saveUserCapacity() {
  if (userCapacity.saving) return
  userCapacity.saving = true
  try {
    const def = userCapacity.default_capacity || 480
    const items = userCapacity.rows
      .filter((x) => x.capacity_minutes > 0 && x.capacity_minutes !== def)
      .map((x) => ({ user_id: x.user_id, capacity_minutes: x.capacity_minutes }))
    await plansApi.setUserCapacities(items)
    ElMessage.success(t('production.plans.userCapacitySaved'))
    await loadLoad()
    if (loadDetail.open && loadDetail.day) await openLoadDetail(loadDetail.day)
  } finally {
    userCapacity.saving = false
  }
}

async function openEquipmentCapacity() {
  equipmentCapacity.open = true
  equipmentCapacity.loading = true
  try {
    const [capRes, eqRes] = await Promise.all([
      plansApi.getEquipmentCapacities(),
      http.request<any>({ url: '/admin/equipment', method: 'GET' }),
    ])

    const capMap = new Map((capRes.items || []).map((x: PlanEquipmentCapacityOut) => [x.equipment_id, x.capacity_minutes]))
    equipmentCapacity.default_capacity = capRes.default_capacity || 480
    equipmentCapacity.rows = (eqRes?.items || [])
      .map((e: any) => ({
        equipment_id: e.id,
        name: equipmentOptionLabel(e),
        capacity_minutes: capMap.get(e.id) ?? 0,
      }))
      .sort((a: any, b: any) => a.name.localeCompare(b.name))
  } finally {
    equipmentCapacity.loading = false
  }
}

async function saveEquipmentCapacity() {
  if (equipmentCapacity.saving) return
  equipmentCapacity.saving = true
  try {
    const def = equipmentCapacity.default_capacity || 480
    const items = equipmentCapacity.rows
      .filter((x) => x.capacity_minutes > 0 && x.capacity_minutes !== def)
      .map((x) => ({ equipment_id: x.equipment_id, capacity_minutes: x.capacity_minutes }))
    await plansApi.setEquipmentCapacities(items)
    ElMessage.success(t('production.plans.equipmentCapacitySaved'))
    await loadLoad()
    if (loadDetail.open && loadDetail.day) await openLoadDetail(loadDetail.day)
  } finally {
    equipmentCapacity.saving = false
  }
}

async function runAutoDispatch() {
  const list = items.value.filter((x) => x.status === 'planned' || x.status === 'in_progress')
  if (!list.length) {
    ElMessage.info(t('production.plans.noPlanToDispatch'))
    return
  }
  if (list.length > 1) {
    ElMessage.warning('请先通过筛选条件把列表收敛到单个计划后再自动派工（例如按订单ID筛选）')
    return
  }
  const planId = list[0].id
  autoDispatch.open = true
  autoDispatch.loading = true
  autoDispatch.result = null
  try {
    autoDispatch.result = await plansApi.autoDispatch(planId, { unassigned_only: true })
    ElMessage.success(t('production.plans.autoDispatchComplete'))
    await reload(false)
  } finally {
    autoDispatch.loading = false
  }
}



function barStyle(p: PlanOut) {
  const days = ganttDays.value
  if (!days.length) return null
  const s = p.start_date || p.end_date
  const e = p.end_date || p.start_date
  if (!s || !e) return null
  const startIdx = days.indexOf(s)
  const endIdx = days.indexOf(e)
  if (startIdx < 0 || endIdx < 0) return null
  return { left: `${startIdx * dayWidth}px`, width: `${(endIdx - startIdx + 1) * dayWidth}px` }
}

const ganttDrag = reactive({
  planId: null as number | null,
  startX: 0,
  offsetPx: 0,
  saving: false,
})

function barStyleWithDrag(p: PlanOut) {
  const base = barStyle(p)
  if (!base) return null
  if (ganttDrag.planId === p.id && ganttDrag.offsetPx) {
    const leftNum = parseFloat(String(base.left)) + ganttDrag.offsetPx
    return { ...base, left: `${leftNum}px`, opacity: 0.9, zIndex: 20 }
  }
  return base
}

function addDays(dateStr: string, n: number): string {
  const d = new Date(`${dateStr}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

function diffDaysInclusive(a: string, b: string): number {
  const da = new Date(`${a}T12:00:00`).getTime()
  const db = new Date(`${b}T12:00:00`).getTime()
  return Math.round((db - da) / 86400000) + 1
}

function onGanttPointerMove(e: PointerEvent) {
  if (ganttDrag.planId == null) return
  ganttDrag.offsetPx = e.clientX - ganttDrag.startX
}

async function onGanttPointerUp() {
  window.removeEventListener('pointermove', onGanttPointerMove)
  window.removeEventListener('pointerup', onGanttPointerUp)
  const planId = ganttDrag.planId
  const offsetPx = ganttDrag.offsetPx
  ganttDrag.planId = null
  ganttDrag.offsetPx = 0
  if (!planId || !offsetPx) return
  const p = items.value.find((x) => x.id === planId)
  if (!p?.start_date || !p?.end_date) return
  const shift = Math.round(offsetPx / dayWidth)
  if (shift === 0) return
  const newStart = addDays(p.start_date, shift)
  const newEnd = addDays(p.end_date, shift)
  ganttDrag.saving = true
  try {
    await plansApi.updatePlan(planId, {
      start_date: newStart,
      end_date: newEnd,
      work_days: diffDaysInclusive(newStart, newEnd),
    })
    ElMessage.success(t('gantt.dragSaved'))
    await reload()
  } catch {
    ElMessage.error(t('gantt.dragFailed'))
  } finally {
    ganttDrag.saving = false
  }
}

function onGanttBarDown(e: PointerEvent, p: PlanOut) {
  if (ganttDrag.saving || !p.start_date || !p.end_date) return
  ganttDrag.planId = p.id
  ganttDrag.startX = e.clientX
  ganttDrag.offsetPx = 0
  window.addEventListener('pointermove', onGanttPointerMove)
  window.addEventListener('pointerup', onGanttPointerUp)
}

onUnmounted(() => {
  window.removeEventListener('pointermove', onGanttPointerMove)
  window.removeEventListener('pointerup', onGanttPointerUp)
})

/** 移动端甘特条：在当前日期轴内的宽度占比 */
function barWidthPercent(p: PlanOut) {
  const days = ganttDays.value
  if (!days.length) return '0%'
  const s = p.start_date || p.end_date
  const e = p.end_date || p.start_date
  if (!s || !e) return '0%'
  const startIdx = days.indexOf(s)
  const endIdx = days.indexOf(e)
  if (startIdx < 0 || endIdx < 0) return '0%'
  const span = endIdx - startIdx + 1
  const pct = (span / days.length) * 100
  return `${Math.min(100, Math.max(2, pct)).toFixed(1)}%`
}

function fmtMinutes(v?: number | null) {
  if (v === null || v === undefined) return '-'
  if (!Number.isFinite(v)) return '-'
  const n = Number(v)
  if (n >= 60) return `${(n / 60).toFixed(n >= 600 ? 0 : 1)}h`
  return `${Math.round(n)}m`
}

function fmtLoad(v?: number | null) {
  if (v === null || v === undefined || !Number.isFinite(v)) return '-'
  const n = Number(v)
  if (capacityUnit.value === 'pieces') return `${Math.round(n)}件`
  return fmtMinutes(n)
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const [date_from, date_to] = Array.isArray(query.range) ? query.range : []
    const res = await plansApi.listPlans({
      status: query.status || undefined,
      order_id: query.order_id || undefined,
      date_from: date_from || undefined,
      date_to: date_to || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
    await loadLoad()
  } finally {
    loading.value = false
  }
}

async function loadLoad() {
  if (activeTab.value !== 'gantt') return
  const days = ganttDays.value
  if (!days.length) {
    planLoad.items = []
    return
  }
  planLoad.loading = true
  try {
    const res = await plansApi.load({ date_from: days[0], date_to: days[days.length - 1], capacity: loadCapacity.value })
    planLoad.items = res.items || []
  } finally {
    planLoad.loading = false
  }
}

async function openLoadDetail(day: string) {
  const it = loadMap.value.get(day)
  if (it && it.is_workday === false) {
    ElMessage.info(t('production.plans.notWorkday'))
    return
  }
  loadDetail.open = true
  loadDetail.day = day
  loadDetail.items = []
  loadDetail.workshops = []
  loadDetail.users = []
  loadDetail.equipments = []
  loadDetail.loading = true
  try {
    const res = await plansApi.loadDetail({ day })
    loadDetail.items = res.items || []
    loadDetail.workshops = res.workshops || []
    loadDetail.users = res.users || []
    loadDetail.equipments = res.equipments || []
  } finally {
    loadDetail.loading = false
  }
}

async function saveCapacity() {
  if (capacitySaving.value) return
  capacitySaving.value = true
  try {
    const res = await plansApi.setCapacity(loadCapacity.value)
    loadCapacity.value = res.capacity
    capacityUnit.value = res.unit || capacityUnit.value
    ElMessage.success(t('production.plans.capacitySaved'))
    await loadLoad()
  } finally {
    capacitySaving.value = false
  }
}

async function onCapacityUnitChange(unit: 'pieces' | 'minutes') {
  try {
    const res = await plansApi.setCapacityUnit(unit)
    loadCapacity.value = res.capacity
    capacityUnit.value = res.unit
    ElMessage.success(`已切换为${res.unit_label}`)
    await loadLoad()
  } catch {
    /* http 已提示 */
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

const readiness = reactive({
  open: false,
  planId: null as number | null,
  canRelease: false,
})

const kit = reactive({
  open: false,
  loading: false,
  creating: false,
  loadingPOs: false,
  planId: 0,
  supplier_id: null as number | null,
  data: null as KittingOut | null,
  purchaseOrders: [] as PlanKittingPurchaseOrderOut[],
})

const suppliers = ref<SupplierOut[]>([])
const supMap = computed(() => new Map(suppliers.value.map((s) => [s.id, s])))

function supplierLabel(id: number | null) {
  if (!id) return '-'
  const s = supMap.value.get(id)
  if (!s) return String(id)
  return partyOptionLabel(s)
}

const shortageCount = computed(() => (kit.data?.items || []).filter((x) => x.shortage_qty > 0).length)
const kitItems = computed(() => {
  const all = kit.data?.items || []
  if (!kit.supplier_id) return all
  return all.filter((x) => x.supplier_id === kit.supplier_id)
})

const canCreatePurchase = computed(() => {
  if (!kit.data) return false
  if (kit.creating) return false
  if (kit.data.missing_boms.length) return false
  const anyShort = (kit.data.items || []).some((x) => x.shortage_qty > 0)
  if (!anyShort) return false
  return true
})

const poReceivedCount = computed(() => kit.purchaseOrders.filter((x) => x.status === 'received').length)

function poStatusLabel(s: string) {
  if (s === 'draft') return t('production.plans.poStatusDraft')
  if (s === 'confirmed') return t('production.plans.poStatusConfirmed')
  if (s === 'partial_received') return t('production.plans.poStatusPartial')
  if (s === 'received') return t('production.plans.poStatusReceived')
  if (s === 'canceled') return t('production.plans.poStatusCanceled')
  return s || '-'
}

function poStatusTag(s: string) {
  if (s === 'draft') return 'info'
  if (s === 'confirmed') return 'warning'
  if (s === 'partial_received') return 'warning'
  if (s === 'received') return 'success'
  if (s === 'canceled') return 'danger'
  return 'info'
}

async function loadPlanPurchaseOrders(planId: number) {
  kit.loadingPOs = true
  try {
    const res = await purchaseApi.listKittingPurchaseOrders(planId)
    kit.purchaseOrders = res.items || []
  } finally {
    kit.loadingPOs = false
  }
}

const kitCanRelease = computed(() => {
  if (!kit.planId) return false
  const row = items.value.find((x) => x.id === kit.planId)
  return row?.can_release ?? false
})

async function onReleasePlan(row: PlanOut) {
  await onReleasePlanById(row.id, row.code)
}

async function onReleasePlanById(planId: number, planCode?: string) {
  if (releasingId.value) return
  const shortage =
    kit.planId === planId && kit.data?.items
      ? kit.data.items.filter((x) => x.shortage_qty > 0).length
      : 0
  let allowShortage = false
  if (shortage > 0) {
    const ok = await ElMessageBox.confirm(
      `当前齐套检查仍有 ${shortage} 项缺料，是否仍要下发投产？`,
      '缺料下发确认',
      { type: 'warning', confirmButtonText: '仍要下发', cancelButtonText: '取消' },
    )
      .then(() => true)
      .catch(() => false)
    if (!ok) return
    allowShortage = true
  } else {
    const ok = await ElMessageBox.confirm(
      `确认下发计划「${planCode || planId}」？将生成工单与工序任务，订单进入生产中。`,
      '确认下发',
      { type: 'warning' },
    )
      .then(() => true)
      .catch(() => false)
    if (!ok) return
  }
  releasingId.value = planId
  try {
    const res = await plansApi.releasePlan(planId, { allow_shortage: allowShortage })
    ElMessage.success(`已下发：生成工单 ${res.work_order_count} 个、任务 ${res.task_count} 条`)
    kit.open = false
    await reload(false)
  } finally {
    releasingId.value = null
  }
}

async function checkKit(planId: number) {
  readiness.planId = planId
  const row = items.value.find((x) => x.id === planId)
  readiness.canRelease = row?.can_release ?? false
  readiness.open = true
}

async function openAiSchedule(planId: number) {
  aiPlanId.value = planId
  aiLoading.value = true
  aiDlg.mode = 'schedule'
  aiDlg.title = '智能排产建议'
  aiDlg.open = true
  aiDlg.text = ''
  aiDlg.list = []
  aiDlg.tab = 'llm'
  lastOptimize.value = null
  try {
    const [res, opt] = await Promise.all([
      aiApi.planScheduleSuggest(planId),
      (async () => {
        aiOptimizeLoading.value = true
        try {
          return await aiApi.planScheduleOptimize(planId)
        } finally {
          aiOptimizeLoading.value = false
        }
      })(),
    ])
    lastScheduleSuggest.value = res
    lastOptimize.value = opt
    aiDlg.text = res.reply || ''
    const hints = [...(res.dispatch_hints || []), ...(res.overload_warnings || [])]
    if (res.suggest_start_date || res.suggest_end_date) {
      hints.unshift(
        `建议：${res.suggest_mode === 'forward' ? '正排' : '倒排'} ${res.suggest_start_date || '—'} ~ ${res.suggest_end_date || '—'}`,
      )
    }
    aiDlg.list = hints
  } catch (e: unknown) {
    aiDlg.text = e instanceof Error ? e.message : 'AI 暂不可用'
  } finally {
    aiLoading.value = false
  }
}

async function applyOptimizerSchedule() {
  if (!aiPlanId.value || !lastOptimize.value?.suggest_start_date || !lastOptimize.value?.suggest_end_date) return
  await ElMessageBox.confirm('将采纳 OR-Tools 日期方案并自动下发、派工。', '采纳 OR-Tools')
  aiApplying.value = true
  try {
    await aiApi.planScheduleApply(aiPlanId.value, {
      unassigned_only: true,
      auto_release: true,
      start_date: lastOptimize.value.suggest_start_date,
      end_date: lastOptimize.value.suggest_end_date,
      work_days: lastOptimize.value.suggest_work_days || undefined,
    })
    ElMessage.success('已执行 OR-Tools 排产与派工')
    aiDlg.open = false
    await reload(false)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '执行失败')
  } finally {
    aiApplying.value = false
  }
}

async function applyAiSchedule() {
  if (!aiPlanId.value) return
  const mode = lastScheduleSuggest.value?.suggest_mode === 'forward' ? 'forward' : 'backward'
  await ElMessageBox.confirm(
    '将依次：① 按交期调整计划日期 ② 若计划未下发则自动确认下发（生成工单/任务）③ 自动派工。缺料下发请先在计划页用「允许缺料」手动下达。',
    '采纳排产',
  )
  aiApplying.value = true
  try {
    await aiApi.planScheduleApply(aiPlanId.value, { mode, unassigned_only: true, auto_release: true })
    ElMessage.success('已执行排产与派工')
    aiDlg.open = false
    await reload(false)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '执行失败')
  } finally {
    aiApplying.value = false
  }
}

async function onReleaseFromReadiness(planId: number, opts: { allow_shortage: boolean }) {
  if (releasingId.value) return
  releasingId.value = planId
  try {
    const res = await plansApi.releasePlan(planId, { allow_shortage: opts.allow_shortage })
    ElMessage.success(`已下发：生成工单 ${res.work_order_count} 个、任务 ${res.task_count} 条`)
    readiness.open = false
    await reload(false)
  } finally {
    releasingId.value = null
  }
}

async function onCreatePurchase() {
  if (!kit.data) return
  kit.creating = true
  try {
    const res = await purchaseApi.createPurchaseFromKitting(kit.data.plan_id, kit.supplier_id)
    if (!res.items.length) {
      ElMessage.success(t('production.plans.noPurchaseNeeded'))
      return
    }
    ElMessage.success(`已生成 ${res.items.length} 张采购单`)
    await loadPlanPurchaseOrders(kit.data.plan_id)
    if (res.items.length === 1) router.push(`/purchase/orders/${res.items[0].id}`)
  } finally {
    kit.creating = false
  }
}

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({ keyword: '', offset: 0, limit: 200, include_inactive: true })
  suppliers.value = res.items
}

async function loadAutomationHint() {
  if (!canAutomationSettings.value) return
  try {
    automationSettings.value = await automationApi.getAutomationSettings()
  } catch {
    automationSettings.value = null
  }
}

onMounted(async () => {
  const cap = await plansApi.getCapacity()
  loadCapacity.value = cap.capacity
  capacityUnit.value = cap.unit || 'pieces'
  await loadSuppliers()
  await loadAutomationHint()
  await reload(true)
})

watch(activeTab, () => {
  loadLoad()
})
</script>
