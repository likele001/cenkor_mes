<template>
  <div class="admin-page-skeleton space-y-4">
    <el-skeleton animated>
      <template #template>
        <el-skeleton-item variant="h3" style="width: 28%; margin-bottom: 12px" />
        <div class="flex gap-3 mb-4">
          <el-skeleton-item variant="rect" style="width: 180px; height: 32px" />
          <el-skeleton-item variant="rect" style="width: 88px; height: 32px" />
        </div>
        <el-skeleton-item variant="rect" style="width: 100%; height: 280px" />
      </template>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts"></script>
