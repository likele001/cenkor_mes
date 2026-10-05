<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <el-alert v-if="info" type="success" :closable="false" class="mb-4" :title="t('system.feishu.testSendDeliveryHint')">
    <dl class="grid grid-cols-[7rem_1fr] gap-x-4 gap-y-1 text-sm">
      <dt class="text-el-placeholder">{{ t('system.feishu.feishuTenant') }}</dt>
      <dd>{{ info.feishu_tenant_name || '—' }}</dd>
      <dt class="text-el-placeholder">{{ t('system.feishu.botName') }}</dt>
      <dd>{{ info.bot_name || '—' }}（{{ info.bot_app_id }}）</dd>
      <dt class="text-el-placeholder">{{ t('system.feishu.boundFeishuUser') }}</dt>
      <dd>{{ info.bound_feishu_name || '—' }}（{{ info.bound_feishu_email || '—' }}）</dd>
      <dt class="text-el-placeholder">open_id</dt>
      <dd class="break-all">{{ info.bound_open_id || '—' }}</dd>
      <dt class="text-el-placeholder">{{ t('system.feishu.p2pChatId') }}</dt>
      <dd class="break-all">{{ info.p2p_chat_id || '—' }}</dd>
      <dt class="text-el-placeholder">{{ t('system.feishu.p2pMessageCount') }}</dt>
      <dd>{{ info.p2p_message_count }}</dd>
    </dl>
    <ul class="text-sm mt-3 list-disc pl-5">
      <li v-for="(hint, idx) in info.hints" :key="idx">{{ hint }}</li>
    </ul>
    <div class="mt-3 flex gap-2 flex-wrap">
      <el-button v-if="info.chat_open_link" type="primary" @click="openLink(info.chat_open_link)">
        {{ t('system.feishu.openBotChat') }}
      </el-button>
      <el-button v-if="info.bot_open_link" @click="openLink(info.bot_open_link)">
        {{ t('system.feishu.openBotApp') }}
      </el-button>
    </div>
  </el-alert>
  <el-empty v-else :description="t('system.feishu.diagEmpty')" />
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { FeishuDeliveryDiagnostics } from '@/api/feishu'

defineProps<{ info: FeishuDeliveryDiagnostics | null }>()

const { t } = useI18n()

function openLink(url: string) {
  window.open(url, '_blank')
}
</script>
