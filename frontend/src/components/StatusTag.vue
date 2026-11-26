<script setup lang="ts">
defineProps<{ status: string }>();
const labels: Record<string, string> = {
  PENDING: "等待执行",
  RUNNING: "执行中",
  WAITING_APPROVAL: "等待审批",
  SUCCEEDED: "已完成",
  FAILED: "执行失败",
  CANCELLED: "已取消",
  APPROVED: "已批准",
  REJECTED: "已拒绝",
  VALID: "验证通过",
};
const types: Record<string, any> = {
  PENDING: "info",
  RUNNING: "primary",
  WAITING_APPROVAL: "warning",
  SUCCEEDED: "success",
  FAILED: "danger",
  CANCELLED: "info",
  APPROVED: "success",
  REJECTED: "danger",
  VALID: "success",
};
</script>
<template>
  <el-tag :type="types[status] || 'info'" effect="light" round
    ><span class="status-dot">●</span> {{ labels[status] || status }}</el-tag
  >
</template>
