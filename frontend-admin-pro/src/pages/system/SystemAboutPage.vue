<template>
  <div class="system-about-page p-4 sm:p-6 space-y-6">
    <!-- 当前版本卡片 -->
    <el-card shadow="never" class="version-card">
      <div class="flex items-center gap-4">
        <div class="version-icon shrink-0 w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg">
          <el-icon :size="32"><InfoFilled /></el-icon>
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-xs text-gray-400 mb-1">{{ t('system.about.currentVersion') }}</div>
          <div class="flex items-center gap-3 flex-wrap">
            <span class="text-2xl font-bold text-gray-800">{{ versionInfo?.version || '--' }}</span>
            <el-tag :type="edition === 'pro' ? 'danger' : 'info'" size="small" effect="plain">
              {{ edition === 'pro' ? '专业版' : '社区版' }}
            </el-tag>
          </div>
          <div class="text-xs text-gray-400 mt-1">
            {{ t('system.about.releaseDate') }}：{{ versionInfo?.release_date || '--' }}
          </div>
        </div>
        <div class="text-right shrink-0 hidden sm:block">
          <div class="text-xs text-gray-400">{{ t('system.about.buildInfo') }}</div>
          <div class="text-sm text-gray-600 mt-0.5">CenkorMES {{ versionInfo?.version }}</div>
        </div>
      </div>
    </el-card>

    <!-- 开发日志标题 -->
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800">{{ t('system.about.changelog') }}</h3>
      <el-tag size="small" type="info" effect="plain">
        {{ t('system.about.totalVersions', { count: changelog.length }) }}
      </el-tag>
    </div>

    <!-- 开发日志时间线 -->
    <div class="changelog-timeline" v-loading="loading">
      <div v-if="changelog.length === 0 && !loading" class="text-center text-gray-400 py-12">
        {{ t('system.about.noChangelog') }}
      </div>
      <div
        v-for="(item, idx) in changelog"
        :key="item.id"
        class="timeline-item relative pl-8 pb-8"
        :class="{ 'last:pb-0': idx === changelog.length - 1 }"
      >
        <!-- 时间线竖线 -->
        <div
          class="timeline-line absolute left-[11px] top-6 bottom-0 w-0.5"
          :class="idx === changelog.length - 1 ? 'bg-transparent' : 'bg-gray-200'"
        />
        <!-- 时间线圆点 -->
        <div
          class="timeline-dot absolute left-0 top-1.5 w-6 h-6 rounded-full border-2 flex items-center justify-center"
          :class="idx === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'"
        >
          <div :class="idx === 0 ? 'w-2 h-2 rounded-full bg-blue-500' : 'w-1.5 h-1.5 rounded-full bg-gray-300'" />
        </div>
        <!-- 内容卡片 -->
        <div
          class="timeline-content rounded-xl border p-4 transition-shadow hover:shadow-sm"
          :class="idx === 0 ? 'border-blue-200 bg-blue-50/30' : 'border-gray-200 bg-white'"
        >
          <div class="flex items-center gap-2 mb-1.5 flex-wrap">
            <span class="font-semibold text-base" :class="idx === 0 ? 'text-blue-700' : 'text-gray-800'">
              {{ item.version }}
            </span>
            <span class="text-xs text-gray-400">{{ item.release_date }}</span>
            <el-tag v-if="idx === 0" size="small" type="success" effect="dark">最新</el-tag>
          </div>
          <p class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{{ item.description }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { InfoFilled } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const versionInfo = ref<{ version: string; release_date: string; description: string } | null>(null)
const changelog = ref<{ id: number; version: string; release_date: string; description: string }[]>([])
const edition = ref('community')

onMounted(async () => {
  loading.value = true
  try {
    const [verRes, logRes] = await Promise.all([
      systemApi.getVersionInfo(),
      systemApi.listChangelog({ limit: 200 }),
    ])
    const data = verRes as any
    versionInfo.value = data?.version || null
    edition.value = data?.edition || 'community'
    changelog.value = (logRes as any)?.items || []
  } catch (e) {
    console.error('获取版本信息失败', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.timeline-item:last-child .timeline-line {
  display: none;
}
</style>