<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { get } from "../api";
import Chart from "../components/Chart.vue";
import { Refresh } from "@element-plus/icons-vue";
const health = ref<any>(),
  summary = ref<any>(),
  errors = ref<any[]>([]),
  busy = ref(false);
async function load() {
  busy.value = true;
  try {
    [health.value, summary.value, errors.value] = await Promise.all([
      get("system/health/"),
      get("dashboard/summary/"),
      get("dashboard/errors/"),
    ]);
  } finally {
    busy.value = false;
  }
}
onMounted(load);
const chart = computed(() => ({
  color: ["#2563eb"],
  tooltip: {},
  grid: { left: 150, right: 40, top: 20, bottom: 35 },
  xAxis: { type: "value", minInterval: 1 },
  yAxis: { type: "category", data: errors.value.map((x) => x.error_type) },
  series: [
    {
      type: "bar",
      data: errors.value.map((x) => x.count),
      barMaxWidth: 30,
      itemStyle: { borderRadius: [0, 5, 5, 0] },
    },
  ],
}));
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">OBSERVABILITY</span>
      <h1>系统运行监控</h1>
      <p>以真实运行数据，持续了解任务可靠性。</p>
    </div>
    <el-button :icon="Refresh" :loading="busy" @click="load"
      >刷新状态</el-button
    >
  </div>
  <el-alert
    v-if="health?.runner_mode === 'local-demo'"
    title="当前为本地演示 Worker；下方 Celery 在线数仅显示真实 Celery 状态。"
    type="info"
    :closable="false"
    class="spaced"
  />
  <div class="metrics">
    <div
      class="metric"
      v-for="[label, value] in [
        ['任务成功率', (summary?.success_rate || 0) + '%'],
        ['平均执行耗时', (summary?.average_duration || 0).toFixed(1) + 's'],
        ['平均执行步骤', (summary?.average_steps || 0).toFixed(1)],
        ['当前排队任务', health?.queued || 0],
      ]"
      :key="label"
    >
      <div>
        <span class="muted">{{ label }}</span>
        <h2>{{ value }}</h2>
      </div>
    </div>
  </div>
  <div class="dashboard-charts">
    <section class="panel">
      <h3>错误类型分布</h3>
      <Chart v-if="errors.length" :option="chart" /><el-empty
        v-else
        description="暂无错误记录"
      />
    </section>
    <section class="panel">
      <h3>基础设施状态</h3>
      <p class="muted">
        模型用量：{{
          summary?.model_usage
            ? summary.model_usage.total_tokens +
              " tokens（" +
              summary.model_usage.reported_runs +
              " 次运行已上报）"
            : "尚未收到模型用量报告"
        }}
      </p>
      <dl class="health-list">
        <dt>MySQL / 业务数据库</dt>
        <dd>
          <el-tag :type="health?.database ? 'success' : 'danger'">{{
            health?.database ? "已连接" : "未连接"
          }}</el-tag>
        </dd>
        <dt>Redis 消息队列</dt>
        <dd>
          <el-tag :type="health?.redis ? 'success' : 'danger'">{{
            health?.redis ? "已连接" : "未连接"
          }}</el-tag>
        </dd>
        <dt>Celery Worker</dt>
        <dd>
          <el-tag :type="health?.workers.length ? 'success' : 'warning'"
            >{{ health?.workers.length || 0 }} 在线</el-tag
          >
        </dd>
        <dt>模型配置</dt>
        <dd>
          {{ health?.provider }} ·
          {{ health?.model_configured ? "已配置密钥" : "未配置密钥" }}
        </dd>
      </dl>
      <p class="muted">{{ health?.workers.join(", ") }}</p>
    </section>
  </div>
  <section class="panel">
    <h3>最近失败记录</h3>
    <el-table :data="summary?.failures || []"
      ><el-table-column prop="error_type" label="错误类型" /><el-table-column
        prop="error_message"
        label="错误详情"
        min-width="300" /><el-table-column prop="engine" label="引擎"
    /></el-table>
  </section>
</template>
