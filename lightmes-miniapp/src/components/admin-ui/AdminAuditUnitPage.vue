<template>
  <view class="adm-page">
    <view v-if="canAiSummary" class="ai-toolbar">
      <button class="ai-btn" :loading="summaryLoading" @tap="runAuditSummary">AI 批量摘要</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无待审件次报工" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.task?.task_code || `任务${item.task_id}` }} · 第{{ item.unit_seq }}件</text>
          <text v-if="item.prescreen_level" :class="['adm-list-badge', prescreenTagClass(item.prescreen_level)]">
            {{ prescreenLabel(item.prescreen_level) }}
          </text>
          <text v-else class="adm-list-badge tone-active">{{ reportStatusLabel(item.status) }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '员工', value: userLabel(item) },
          { label: '状态', value: reportStatusLabel(item.status) },
          { label: '结果', value: item.result_type || '—' },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>

    <!-- Detail Sheet -->
    <view v-if="detailVisible" class="mask" @tap="detailVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">件次报工 #{{ detail?.id }}</text>
          <text class="status-tag">{{ reportStatusLabel(String(detail?.status)) }}</text>
        </view>
        <scroll-view scroll-y class="body">

          <!-- 订单 / 产品信息 -->
          <view class="section-title">报工信息</view>
          <view class="kv"><text class="k">任务</text><text class="v">{{ detail?.task?.task_code || '—' }}</text></view>
          <view class="kv"><text class="k">工序</text><text class="v">{{ detail?.task?.process_name || '—' }}</text></view>
          <view class="kv"><text class="k">订单</text><text class="v">{{ detail?.order?.code || '—' }}</text></view>
          <view class="kv"><text class="k">产品</text><text class="v">{{ detail?.product ? `${detail.product.name} (${detail.product.code})` : '—' }}</text></view>
          <view class="kv"><text class="k">件次</text><text class="v">第 {{ detail?.unit_seq }} 件</text></view>
          <view class="kv"><text class="k">员工</text><text class="v">{{ detail ? userLabel(detail) : '—' }}</text></view>
          <view class="kv"><text class="k">结果</text><text class="v">{{ detail?.result_type === 'good' ? '合格' : detail?.result_type === 'bad' ? '不良' : '—' }}</text></view>
          <view v-if="detail?.submitted_at" class="kv"><text class="k">提交时间</text><text class="v">{{ formatTime(detail.submitted_at) }}</text></view>

          <!-- 预审信息 -->
          <view v-if="detail?.prescreen_level" class="kv">
            <text class="k">预审</text>
            <text :class="['prescreen-tag', prescreenTagClass(detail.prescreen_level)]">{{ prescreenLabel(detail.prescreen_level) }}</text>
          </view>
          <view v-if="prescreenReasons.length" class="prescreen-reasons">
            <text v-for="(r, i) in prescreenReasons" :key="'pr' + i" class="reason">· {{ r }}</text>
          </view>

          <!-- 报工人备注 -->
          <view v-if="detail?.remark" class="kv"><text class="k">报工备注</text><text class="v">{{ detail.remark }}</text></view>

          <!-- 报工人上传的图片/视频 -->
          <view v-if="employeePhotos.length" class="section-title">报工照片</view>
          <view v-if="employeePhotos.length" class="photo-grid">
            <view v-for="(p, i) in employeePhotos" :key="'ep' + i" class="photo-item" @tap="previewMedia(p)">
              <image :src="p.play_url" mode="aspectFill" class="photo-thumb" />
              <view v-if="isVideo(p)" class="video-badge">
                <text class="video-icon">▶</text>
              </view>
            </view>
          </view>

          <!-- Vision AI -->
          <view v-if="canVision" class="vision-row">
            <button class="btn vision" :loading="visionLoading" @tap="runVision">Vision 识图辅助</button>
          </view>
          <text v-if="visionText" class="vision-result">{{ visionText }}</text>

          <!-- 管理员上传区 -->
          <view v-if="canAudit" class="section-title">审核操作</view>
          <view v-if="canAudit" class="admin-upload-area">
            <!-- 图片上传 -->
            <button class="btn upload-btn upload-btn-image" :loading="imageUploading" @tap="pickQcImages">
              {{ qcPhotos.length ? `图片 ${qcPhotos.filter(p => !p.isVideo).length}/9` : '选择审核图片' }}
            </button>
            <!-- 视频上传 -->
            <button class="btn upload-btn upload-btn-video" :loading="videoUploading" @tap="pickQcVideos">
              {{ qcVideos.length ? `视频 ${qcVideos.length}/3` : '录制审核视频（≤30秒）' }}
            </button>
            <!-- 已选文件列表 -->
            <view v-if="qcPhotos.length || qcVideos.length" class="photo-grid">
              <view v-for="(p, i) in qcPhotos" :key="'qcimg' + i" class="photo-item">
                <image :src="p.url" mode="aspectFill" class="photo-thumb" />
                <view v-if="p.isVideo" class="video-badge"><text class="video-icon">▶</text></view>
                <view class="remove-badge" @tap="removeQcPhoto(i, true)">×</view>
              </view>
              <view v-for="(v, i) in qcVideos" :key="'qcv' + i" class="photo-item">
                <image :src="v.thumb || v.url" mode="aspectFill" class="photo-thumb" />
                <view class="video-badge"><text class="video-icon">▶</text></view>
                <view class="remove-badge" @tap="removeQcVideo(i)">×</view>
              </view>
            </view>
          </view>

          <!-- 管理员备注 -->
          <view v-if="canAudit" class="admin-remark-area">
            <text class="section-title" style="margin-bottom: 8rpx;">审核备注</text>
            <textarea v-model="adminRemark" class="remark-input" placeholder="可填写审核意见（选填）" :maxlength="500" />
          </view>

          <!-- 已有审核照片 -->
          <view v-if="qcExistingPhotos.length" class="section-title">已有审核照片</view>
          <view v-if="qcExistingPhotos.length" class="photo-grid">
            <view v-for="(p, i) in qcExistingPhotos" :key="'qce' + i" class="photo-item" @tap="previewMedia(p)">
              <image :src="p.play_url" mode="aspectFill" class="photo-thumb" />
              <view v-if="isVideo(p)" class="video-badge"><text class="video-icon">▶</text></view>
            </view>
          </view>

          <!-- 审核历史 -->
          <view v-if="auditHistory.length" class="section-title">审核记录</view>
          <view v-for="(a, i) in auditHistory" :key="'ah' + i" class="audit-item">
            <view class="audit-head">
              <text class="audit-level">{{ a.audit_level === 'leader' ? '班长' : '质检' }}</text>
              <text :class="['audit-action', a.action === 'approve' ? 'action-pass' : 'action-reject']">
                {{ a.action === 'approve' ? '通过' : '驳回' }}
              </text>
            </view>
            <text v-if="a.reason" class="audit-reason">{{ a.reason }}</text>
            <text class="audit-time">{{ formatTime(a.created_at) }}</text>
          </view>
        </scroll-view>

        <!-- Draft tip -->
        <view v-if="detail?.status === 'draft'" class="foot draft-tip">
          <text class="draft-tip-text">该件次尚未报工，请让员工在「逐件报工」中提交后再审核</text>
        </view>

        <!-- Action buttons -->
        <view v-else-if="canAudit" class="foot">
          <button v-if="detail?.status === 'submitted'" class="btn ghost" @tap="approve('leader')">班长通过</button>
          <button v-if="detail?.status === 'leader_approved'" class="btn primary" @tap="approve('qc')">质检通过</button>
          <button class="btn warn" @tap="reject">驳回</button>
        </view>
      </view>
    </view>

    <!-- Summary Sheet -->
    <view v-if="summaryVisible" class="mask" @tap="summaryVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">待审 AI 批量摘要</text></view>
        <scroll-view scroll-y class="body">
          <view v-if="summaryData">
            <text v-if="summaryData.pending_count != null" class="meta">待审 {{ summaryData.pending_count }} 条</text>
            <text v-if="summaryData.summary" class="summary-text">{{ summaryData.summary }}</text>
            <text v-if="summaryData.high_risk_ids?.length" class="section-title">高风险件次 ID</text>
            <text v-if="summaryData.high_risk_ids?.length" class="summary-text">{{ summaryData.high_risk_ids.join(', ') }}</text>
            <text v-if="summaryData.risk_points?.length" class="section-title">风险点</text>
            <text v-for="(p, i) in summaryData.risk_points" :key="'r' + i" class="bullet">· {{ p }}</text>
            <text v-if="summaryData.suggest_actions?.length" class="section-title">建议动作</text>
            <text v-for="(a, i) in summaryData.suggest_actions" :key="'a' + i" class="bullet">· {{ a }}</text>
          </view>
          <text v-else class="summary-text">{{ summaryLoading ? '生成中…' : '暂无摘要' }}</text>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost" @tap="summaryVisible = false">关闭</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { auditAdminApi, reportStatusLabel, prescreenLabel, prescreenTagClass, type ReportUnitRow, type AttachmentMeta } from '@/api/admin/audit'
import { aiAdminApi } from '@/api/admin/ai'
import { usePermission } from '@/composables/usePermission'
import { PermissionCode } from '@/constants/permissions'
import { uploadFile, fileUrl } from '@/api/files'
import { chooseMediaCompat } from '@/utils/chooseMedia'

const { requirePermission, hasPermission } = usePermission()
const items = ref<ReportUnitRow[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref<ReportUnitRow | null>(null)
const detailId = ref(0)
const summaryLoading = ref(false)
const summaryVisible = ref(false)
const summaryData = ref<Record<string, unknown> | null>(null)
const visionLoading = ref(false)
const visionText = ref('')
const qcPhotos = ref<{ id: number; url: string; isVideo: boolean }[]>([])
const qcVideos = ref<{ id: number; url: string; thumb: string }[]>([])
const imageUploading = ref(false)
const videoUploading = ref(false)
const adminRemark = ref('')

const canAudit = computed(() => hasPermission(PermissionCode.REPORT_AUDIT) && ['submitted', 'leader_approved'].includes(String(detail.value?.status)))
const canAiSummary = computed(() => hasPermission(PermissionCode.AI_USE) && hasPermission(PermissionCode.REPORT_AUDIT))
const canVision = computed(() => canAiSummary.value && detailId.value > 0)

const employeePhotos = computed(() => detail.value?.employee_attachments || [])
const qcExistingPhotos = computed(() => detail.value?.qc_attachments || [])
const auditHistory = computed(() => (detail.value?.audits || []).slice().reverse())

const prescreenReasons = computed(() => {
  const raw = detail.value?.prescreen_json
  if (!raw) return [] as string[]
  try {
    const j = JSON.parse(raw) as { reasons?: string[] }
    return j.reasons || []
  } catch {
    return [] as string[]
  }
})

onShow(async () => {
  if (!requirePermission(PermissionCode.REPORT_AUDIT)) return
  await reload()
})

function userLabel(item: ReportUnitRow) {
  return item.report_user?.full_name || item.report_user?.username || '员工'
}

function formatTime(t?: string | null) {
  if (!t) return '—'
  return String(t).replace('T', ' ').slice(0, 16)
}

function isVideo(att: { content_type?: string }) {
  return att.content_type?.startsWith('video/')
}

function previewMedia(att: AttachmentMeta) {
  if (isVideo(att)) {
    uni.navigateTo({
      url: `/pages/shared/video-player/index?url=${encodeURIComponent(att.play_url)}`,
      fail: () => {
        ;(uni as any).openVideo?.({ src: att.play_url })
      },
    })
  } else {
    const urls = employeePhotos.value.filter(p => !isVideo(p)).map(p => p.play_url)
    uni.previewImage({ urls, current: att.play_url })
  }
}

function removeQcPhoto(index: number, isFromPhotos: boolean) {
  qcPhotos.value.splice(index, 1)
}

function removeQcVideo(index: number) {
  qcVideos.value.splice(index, 1)
}

async function reload() {
  loading.value = true
  try {
    const r = await auditAdminApi.listReportUnits({ limit: 50, pending_audit: true })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function openDetail(row: ReportUnitRow) {
  detailId.value = row.id
  visionText.value = ''
  qcPhotos.value = []
  qcVideos.value = []
  adminRemark.value = ''
  try {
    detail.value = await auditAdminApi.getReportUnit(row.id)
    detailVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function runAuditSummary() {
  summaryLoading.value = true
  summaryVisible.value = true
  summaryData.value = null
  try {
    summaryData.value = (await aiAdminApi.auditSummary('submitted')) as Record<string, unknown>
  } catch (e: unknown) {
    summaryData.value = { summary: (e as Error).message || 'AI 暂不可用' }
  } finally {
    summaryLoading.value = false
  }
}

async function runVision() {
  if (!detailId.value) return
  visionLoading.value = true
  visionText.value = ''
  try {
    const res = await aiAdminApi.reportVision(detailId.value)
    visionText.value = String(res.summary || res.reply || '识图完成')
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '识图失败', icon: 'none' })
  } finally {
    visionLoading.value = false
  }
}

/** 选择审核图片（最多9张） */
async function pickQcImages() {
  const remaining = 9 - qcPhotos.value.length
  if (remaining <= 0) {
    uni.showToast({ title: '图片最多9张', icon: 'none' })
    return
  }
  imageUploading.value = true
  try {
    const res = await chooseMediaCompat({
      count: remaining,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
    })
    for (const f of res.tempFiles) {
      const result = await uploadFile(f.tempFilePath, 'report_media')
      qcPhotos.value.push({ id: result.id, url: f.tempFilePath, isVideo: false })
    }
    uni.showToast({ title: `已添加 ${res.tempFiles.length} 张图片`, icon: 'success' })
  } catch (e: unknown) {
    if ((e as any)?.errMsg?.includes('cancel')) return
    console.error('[AdminAudit] pick images error:', e)
    uni.showToast({ title: (e as any)?.errMsg || '选择图片失败', icon: 'none' })
  } finally {
    imageUploading.value = false
  }
}

/** 选择审核视频（最多3个，每个≤30秒） */
async function pickQcVideos() {
  const remaining = 3 - qcVideos.value.length
  if (remaining <= 0) {
    uni.showToast({ title: '视频最多3个', icon: 'none' })
    return
  }
  videoUploading.value = true
  try {
    const res = await chooseMediaCompat({
      count: remaining,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      maxDuration: 30,
    })
    for (const f of res.tempFiles) {
      const result = await uploadFile(f.tempFilePath, 'report_media')
      qcVideos.value.push({
        id: result.id,
        url: f.tempFilePath,
        thumb: f.thumbTempFilePath || f.tempFilePath,
      })
    }
    uni.showToast({ title: `已添加 ${res.tempFiles.length} 个视频`, icon: 'success' })
  } catch (e: unknown) {
    if ((e as any)?.errMsg?.includes('cancel')) return
    console.error('[AdminAudit] pick videos error:', e)
    uni.showToast({ title: (e as any)?.errMsg || '选择视频失败', icon: 'none' })
  } finally {
    videoUploading.value = false
  }
}

/** 合并所有附件 ID（图片 + 视频） */
function allAttachmentIds(): string {
  const ids = [
    ...qcPhotos.value.map(p => p.id),
    ...qcVideos.value.map(v => v.id),
  ]
  return ids.join(',')
}

async function approve(type: 'leader' | 'qc') {
  if (!detailId.value) return
  const remarkVal = adminRemark.value.trim() || undefined
  const attachmentIds = allAttachmentIds()

  if (type === 'leader') {
    await auditAdminApi.leaderApproveUnit(detailId.value, {
      qc_attachment_ids: attachmentIds || '',
      remark: remarkVal,
    })
  } else {
    if (!attachmentIds && !qcExistingPhotos.value.length) {
      uni.showToast({ title: '请先上传审核照片或视频', icon: 'none' })
      return
    }
    await auditAdminApi.qcApproveUnit(detailId.value, {
      qc_attachment_ids: attachmentIds || '',
      remark: remarkVal,
    })
  }
  uni.showToast({ title: '已通过', icon: 'success' })
  detailVisible.value = false
  await reload()
}

function reject() {
  uni.showModal({
    title: '驳回',
    editable: true,
    placeholderText: '请输入驳回原因',
    success: async (res) => {
      if (!res.confirm || !detailId.value) return
      try {
        await auditAdminApi.rejectReportUnit(detailId.value, res.content || '驳回')
        uni.showToast({ title: '已驳回', icon: 'none' })
        detailVisible.value = false
        await reload()
      } catch (e: any) {
        uni.showToast({ title: e?.message || '驳回失败', icon: 'none' })
      }
    },
  })
}
</script>

<style scoped lang="scss">
.ai-toolbar { padding: 16rpx 24rpx 0; }
.prescreen-tag { font-size: 20rpx; padding: 4rpx 12rpx; border-radius: 999rpx; flex-shrink: 0; }
.prescreen-green { color: #15803d; background: #dcfce7; }
.prescreen-yellow { color: #b45309; background: #fef3c7; }
.prescreen-red { color: #b91c1c; background: #fee2e2; }
.prescreen-none { color: #64748b; background: #f1f5f9; }
.prescreen-reasons { margin: 12rpx 0; padding: 12rpx; background: #fffbeb; border-radius: 12rpx; }
.reason { display: block; font-size: 24rpx; color: #b45309; line-height: 1.5; }
.ai-btn { font-size: 26rpx; background: #fffbeb; color: #b45309; border: 1rpx solid #fcd34d; border-radius: 12rpx; padding: 12rpx 24rpx; }

.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 32rpx; font-weight: 700; }
.status-tag { font-size: 22rpx; color: #6366f1; background: #eef2ff; padding: 6rpx 16rpx; border-radius: 999rpx; }
.body { max-height: 65vh; padding: 16rpx 32rpx; }

.section-title { display: block; font-size: 26rpx; font-weight: 600; color: #334155; margin: 24rpx 0 12rpx; padding-bottom: 8rpx; border-bottom: 1rpx solid #f1f5f9; }
.kv { display: flex; gap: 16rpx; margin-bottom: 12rpx; font-size: 26rpx; }
.k { color: #64748b; width: 140rpx; flex-shrink: 0; }
.v { flex: 1; word-break: break-all; }

/* Photo grid */
.photo-grid { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 16rpx; }
.photo-item { position: relative; width: 160rpx; height: 160rpx; border-radius: 12rpx; overflow: hidden; }
.photo-thumb { width: 100%; height: 100%; }
.video-badge { position: absolute; inset: 0; background: rgba(0,0,0,.3); display: flex; align-items: center; justify-content: center; }
.video-icon { color: #fff; font-size: 40rpx; }
.remove-badge { position: absolute; top: 4rpx; right: 4rpx; width: 40rpx; height: 40rpx; background: rgba(0,0,0,.6); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28rpx; }

/* Vision */
.vision-row { margin: 16rpx 0; }
.vision-result { display: block; font-size: 24rpx; color: #475569; white-space: pre-wrap; margin-top: 12rpx; padding: 16rpx; background: #f8fafc; border-radius: 12rpx; }

/* Admin upload */
.admin-upload-area { margin-bottom: 16rpx; display: flex; flex-direction: column; gap: 12rpx; }
.upload-btn { background: #f8fafc; color: #475569; border: 2rpx dashed #cbd5e1; border-radius: 12rpx; font-size: 26rpx; }
.upload-btn-image { border-color: #93c5fd; color: #1d4ed8; }
.upload-btn-video { border-color: #fca5a5; color: #dc2626; }

/* Admin remark */
.admin-remark-area { margin-bottom: 16rpx; }
.remark-input { width: 100%; height: 140rpx; background: #f8fafc; border: 1rpx solid #e2e8f0; border-radius: 12rpx; padding: 16rpx; font-size: 26rpx; }

/* Audit history */
.audit-item { padding: 16rpx 0; border-bottom: 1rpx solid #f8fafc; }
.audit-head { display: flex; gap: 16rpx; align-items: center; margin-bottom: 8rpx; }
.audit-level { font-size: 24rpx; font-weight: 600; color: #334155; }
.audit-action { font-size: 22rpx; padding: 4rpx 16rpx; border-radius: 999rpx; }
.action-pass { color: #15803d; background: #dcfce7; }
.action-reject { color: #b91c1c; background: #fee2e2; }
.audit-reason { display: block; font-size: 24rpx; color: #475569; margin-bottom: 4rpx; }
.audit-time { display: block; font-size: 22rpx; color: #94a3b8; }

/* Summary */
.summary-text { font-size: 26rpx; color: #334155; white-space: pre-wrap; line-height: 1.6; }
.meta { display: block; font-size: 22rpx; color: #94a3b8; margin-bottom: 12rpx; }
.bullet { display: block; font-size: 26rpx; color: #334155; line-height: 1.5; margin-bottom: 6rpx; }

/* Footer */
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.draft-tip { display: block; }
.draft-tip-text { font-size: 24rpx; color: #b45309; line-height: 1.5; }
.btn { flex: 1; border-radius: 12rpx; font-size: 24rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.warn { background: #fef3c7; color: #b45309; }
.vision { background: #fffbeb; color: #b45309; flex: none; width: 100%; }
</style>
