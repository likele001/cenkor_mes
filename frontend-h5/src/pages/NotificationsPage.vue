<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import {
  listMyNotifications,
  markMyAllNotificationsRead,
  markMyNotificationRead,
  type H5Notification,
} from '@/api/tasks'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const tab = ref<'all' | 'unread'>('all')
const unreadOnly = computed(() => tab.value === 'unread')

const items = ref<H5Notification[]>([])
const refreshing = ref(false)
const loading = ref(false)
const finished = ref(false)

const offset = ref(0)
const limit = 20

function timeLabel(v: string | null | undefined) {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

function bizIcon(bizType: string | null) {
  if (bizType === 'report') return 'records'
  if (bizType === 'salary_slip') return 'gold-coin-o'
  return 'info-o'
}

async function load(reset = false) {
  if (loading.value) return
  if (reset) {
    offset.value = 0
    finished.value = false
    items.value = []
  }
  if (finished.value) return

  loading.value = true
  try {
    const resp = await listMyNotifications({
      unread: unreadOnly.value ? true : undefined,
      offset: offset.value,
      limit,
    })
    const arr = resp?.items ?? []
    items.value = items.value.concat(arr)
    offset.value += arr.length
    if (arr.length < limit) finished.value = true
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await load(true)
    await auth.refreshUnreadNotificationCount()
  } finally {
    refreshing.value = false
  }
}

async function onLoadMore() {
  await load(false)
}

async function handleNotification(n: H5Notification) {
  // 标记已读
  if (!n.read_at) {
    try {
      await markMyNotificationRead(n.id)
      await auth.refreshUnreadNotificationCount()
      if (unreadOnly.value) {
        items.value = items.value.filter((x) => x.id !== n.id)
      } else {
        n.read_at = new Date().toISOString()
      }
    } catch {}
  }

  // 按业务类型跳转
  if (n.biz_type === 'salary_slip') {
    try {
      await showConfirmDialog({
        title: n.title || '工资条消息',
        message: n.content || '',
        confirmButtonText: '查看工资条',
        cancelButtonText: '关闭',
      })
      router.push('/salary/slip')
    } catch {}
    return
  }

  if (n.biz_type === 'report') {
    try {
      await showConfirmDialog({
        title: n.title || '报工消息',
        message: n.content || '',
        confirmButtonText: '查看我的任务',
        cancelButtonText: '关闭',
      })
      router.push('/tasks')
    } catch {}
    return
  }

  // 默认：显示内容
  await showDialog({
    title: n.title || '消息',
    message: n.content || '',
    confirmButtonText: '关闭',
  })
}

async function onReadAll() {
  try {
    await showConfirmDialog({ title: '全部已读', message: '确认将所有消息标记为已读？' })
  } catch {
    return
  }
  try {
    await markMyAllNotificationsRead()
    showToast('已全部标记为已读')
    await auth.refreshUnreadNotificationCount()
    await load(true)
  } catch {}
}

watch(
  tab,
  () => { load(true) },
  { immediate: true },
)
</script>

<template>
  <div>
    <!-- 标题+全部已读 -->
    <div class="flex items-center justify-between px-3 pt-2">
      <div class="text-sm font-medium text-zinc-700">消息中心</div>
      <van-button size="small" type="primary" plain @click="onReadAll">全部已读</van-button>
    </div>

    <!-- Tab -->
    <van-tabs v-model:active="tab" shrink class="mt-1">
      <van-tab title="全部" name="all" />
      <van-tab title="未读" name="unread" />
    </van-tabs>

    <!-- 列表 -->
    <div class="mt-2">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-list v-model:loading="loading" :finished="finished" finished-text="没有更多了" @load="onLoadMore">
          <van-cell-group v-if="items.length" inset>
            <van-cell
              v-for="n in items"
              :key="n.id"
              is-link
              @click="handleNotification(n)"
            >
              <template #icon>
                <van-icon :name="bizIcon(n.biz_type)" class="mr-2 text-blue-500" />
              </template>
              <template #title>
                <div class="flex items-center gap-2">
                  <span :class="!n.read_at ? 'font-semibold' : ''">{{ n.title || '消息' }}</span>
                  <van-tag v-if="!n.read_at" type="primary" size="medium" plain>未读</van-tag>
                </div>
              </template>
              <template #label>
                <div class="text-xs text-zinc-400 mt-0.5">
                  <div>{{ timeLabel(n.created_at) }}</div>
                  <div class="mt-0.5 line-clamp-2">{{ n.content || '' }}</div>
                </div>
              </template>
            </van-cell>
          </van-cell-group>
          <van-empty v-else description="暂无消息" />
        </van-list>
      </van-pull-refresh>
    </div>
  </div>
</template>
