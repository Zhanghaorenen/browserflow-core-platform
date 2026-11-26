<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { get } from "../api";
import Chart from "../components/Chart.vue";
import StatusTag from "../components/StatusTag.vue";
import {
  Plus,
  Refresh,
  Right,
  DocumentChecked,
  Timer,
  Warning,
  Files,
} from "@element-plus/icons-vue";
const router = useRouter(),
  data = ref<any>(),
  trends = ref<any[]>([]),
  busy = ref(false),
  error = ref(false);
async function load() {
  busy.value = true;
  error.value = false;
  try {
    [data.value, trends.value] = await Promise.all([
      get("dashboard/summary/"),
      get("dashboard/trends/"),
    ]);
  } catch {
    error.value = true;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
const trend = computed(() => {
  const dates = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - 6 + i);
    return d.toLocaleDateString("sv-SE");
  });
  return {
    color: ["#2563eb", "#06b6d4"],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 40, right: 20, top: 25, bottom: 50 },
    xAxis: {
      type: "category",
      data: dates.map((d) => d.slice(5)),
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } },
    },
    series: [
      {
        name: "全部任务",
        type: "line",
        smooth: true,
        areaStyle: { opacity: 0.08 },
        data: dates.map((d) =>
          trends.value
            .filter((r) => r.date === d)
            .reduce((n, r) => n + r.count, 0),
        ),
      },
      {
        name: "已完成",
        type: "line",
        smooth: true,
        data: dates.map((d) =>
          trends.value
            .filter((r) => r.date === d && r.status === "SUCCEEDED")
            .reduce((n, r) => n + r.count, 0),
        ),
      },
    ],
  };
});
const pie = computed(() => ({
  color: ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#94a3b8"],
  tooltip: { trigger: "item" },
  legend: { bottom: 5 },
  series: [
    {
      type: "pie",
      radius: ["52%", "73%"],
      center: ["50%", "43%"],
      label: { show: false },
      data: [
        { name: "执行中", value: data.value?.counts.RUNNING || 0 },
        { name: "已完成", value: data.value?.counts.SUCCEEDED || 0 },
        {
          name: "待处理",
          value:
            (data.value?.counts.PENDING || 0) +
            (data.value?.counts.WAITING_APPROVAL || 0),
        },
        { name: "失败", value: data.value?.counts.FAILED || 0 },
        { name: "取消", value: data.value?.counts.CANCELLED || 0 },
      ],
    },
  ],
}));
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">WORKSPACE OVERVIEW</span>
      <h1>工作台总览</h1>
      <p>掌握每一次执行，让自动化井然有序。</p>
    </div>
    <div class="actions">
      <span class="muted date">{{
        new Date().toLocaleDateString("zh-CN", {
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      }}</span
      ><el-button :icon="Refresh" @click="load" :loading="busy">刷新</el-button
      ><el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')"
        >创建任务</el-button
      >
    </div>
  </div>
  <el-alert
    v-if="error"
    title="数据加载失败，请点击刷新重试"
    type="error"
  /><el-skeleton :loading="busy && !data" animated :rows="10"
    ><template #default
      ><div class="welcome-banner">
        <div>
          <span class="pill">BROWSER AUTOMATION, REIMAGINED</span>
          <h2>从想法，到执行。</h2>
          <p>描述你的目标，Agent 负责浏览网页，你掌握每一步。</p>
          <el-button @click="router.push('/templates')"
            >从任务模板开始 <el-icon><Right /></el-icon
          ></el-button>
        </div>
        <div class="banner-art" aria-hidden="true">
          <div class="mini-browser">
            <i></i><i></i><i></i>
            <div>⌘ &nbsp; BrowserFlow Agent</div>
            <p>✓ &nbsp; 理解任务目标</p>
            <p>↗ &nbsp; 编排浏览器操作</p>
            <p>◉ &nbsp; 验证执行结果</p>
          </div>
          <span class="floating-check">✓</span>
        </div>
      </div>
      <div class="metrics">
        <div
          class="metric"
          v-for="[label, value, icon, tone] in [
            ['任务总数', data?.total, Files, 'blue'],
            ['已完成任务', data?.counts.SUCCEEDED, DocumentChecked, 'green'],
            ['正在执行', data?.counts.RUNNING, Timer, 'cyan'],
            ['执行失败', data?.counts.FAILED, Warning, 'red'],
          ]"
          :key="String(label)"
        >
          <div>
            <span class="muted">{{ label }}</span>
            <h2>{{ value ?? 0 }}</h2>
            <small class="muted">来自当前工作空间</small>
          </div>
          <span class="metric-icon" :class="tone"
            ><el-icon><component :is="icon" /></el-icon
          ></span>
        </div>
      </div>
      <div class="dashboard-charts">
        <section class="panel">
          <div class="panel-heading">
            <h3>任务执行趋势</h3>
            <span class="muted">最近 7 天</span>
          </div>
          <Chart :option="trend" />
        </section>
        <section class="panel">
          <div class="panel-heading">
            <h3>任务状态分布</h3>
            <span class="muted">成功率 {{ data?.success_rate ?? 0 }}%</span>
          </div>
          <Chart v-if="data?.total" :option="pie" />
          <el-empty v-else description="暂无任务统计" :image-size="90" />
        </section>
      </div>
      <div class="dashboard-charts">
        <section class="panel">
          <div class="panel-heading">
            <h3>最近任务</h3>
            <el-button link type="primary" @click="router.push('/tasks')"
              >查看全部 →</el-button
            >
          </div>
          <el-table
            :data="data?.recent || []"
            @row-click="(row: any) => router.push('/tasks/' + row.id)"
            ><el-table-column
              prop="name"
              label="任务名称"
              min-width="160" /><el-table-column label="状态" width="130"
              ><template #default="{ row }"
                ><StatusTag :status="row.status" /></template></el-table-column
            ><el-table-column prop="model_name" label="模型" /><el-table-column
              label="创建时间"
              min-width="135"
              ><template #default="{ row }">{{
                new Date(row.created_at).toLocaleString("zh-CN")
              }}</template></el-table-column
            ><template #empty
              ><el-empty
                description="还没有任务，从创建第一个任务开始" /></template
          ></el-table>
        </section>
        <section class="panel">
          <div class="panel-heading">
            <h3>执行异常</h3>
            <span class="subtle-badge">{{ data?.failures.length || 0 }}</span>
          </div>
          <el-empty
            v-if="!data?.failures.length"
            description="暂无执行异常"
            :image-size="75"
          />
          <div
            v-for="run in data?.failures"
            :key="run.id"
            class="failure-row"
            @click="router.push('/tasks/' + run.task)"
          >
            <el-icon color="#ef4444"><Warning /></el-icon>
            <div>
              <b>{{ run.error_type }}</b>
              <p>{{ run.error_message.slice(0, 100) }}</p>
            </div>
          </div>
          <div class="panel-foot">所有统计均来自实际任务运行记录</div>
        </section>
      </div></template
    ></el-skeleton
  >
</template>
