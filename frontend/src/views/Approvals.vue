<script setup lang="ts">
import { ref, onMounted } from "vue";
import { get, post } from "../api";
import StatusTag from "../components/StatusTag.vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
const rows = ref<any[]>([]),
  selected = ref<any>(),
  busy = ref(false),
  total = ref(0),
  counts = ref<Record<string, number>>({}),
  page = ref(1),
  reviewing = ref(false);
async function load() {
  busy.value = true;
  try {
    const [d, summary] = await Promise.all([
      get("approvals/", { page: page.value }),
      get("approvals/summary/"),
    ]);
    counts.value = summary;
    rows.value = d.results;
    total.value = d.count;
  } finally {
    busy.value = false;
  }
}
async function review(approve: boolean) {
  await ElMessageBox.confirm(
    approve
      ? "批准后将重新校验页面并执行该操作。确认批准？"
      : "拒绝后本次任务将取消。确认拒绝？",
    "审批确认",
    { type: "warning" },
  );
  reviewing.value = true;
  try {
    await post(
      `approvals/${selected.value.id}/${approve ? "approve" : "reject"}/`,
    );
    selected.value = null;
    ElMessage.success("审批已记录");
    await load();
  } finally {
    reviewing.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">HUMAN IN THE LOOP</span>
      <h1>人工审批中心</h1>
      <p>让关键操作在你的授权下发生。</p>
    </div>
    <el-button :icon="Refresh" @click="load">刷新</el-button>
  </div>
  <div class="metrics">
    <div
      class="metric"
      v-for="[status, label] in [
        ['PENDING', '待审批'],
        ['APPROVED', '已批准'],
        ['REJECTED', '已拒绝'],
      ]"
      :key="status"
    >
      <div>
        <span class="muted">{{ label }}</span>
        <h2>{{ counts[status] || 0 }}</h2>
      </div>
    </div>
  </div>
  <section class="panel">
    <div class="panel-heading">
      <h3>审批记录</h3>
      <span class="muted">共 {{ total }} 条</span>
    </div>
    <el-table :data="rows" v-loading="busy"
      ><el-table-column prop="task_name" label="所属任务" /><el-table-column
        prop="operation_type"
        label="操作类型" /><el-table-column label="目标网站" min-width="180"
        ><template #default="{ row }">{{
          row.operation_summary.url
        }}</template></el-table-column
      ><el-table-column label="状态"
        ><template #default="{ row }"
          ><StatusTag :status="row.status" /></template></el-table-column
      ><el-table-column label="申请时间"
        ><template #default="{ row }">{{
          new Date(row.created_at).toLocaleString()
        }}</template></el-table-column
      ><el-table-column label="操作"
        ><template #default="{ row }"
          ><el-button link type="primary" @click="selected = row"
            >查看详情</el-button
          ></template
        ></el-table-column
      ><template #empty
        ><el-empty description="没有需要处理的审批" /></template></el-table
    ><el-pagination
      class="pagination"
      v-model:current-page="page"
      :total="total"
      :page-size="20"
      layout="total,prev,pager,next"
      @current-change="load"
    />
  </section>
  <el-drawer
    :model-value="!!selected"
    @close="selected = null"
    title="审批操作详情"
    size="min(560px,95vw)"
    ><template v-if="selected"
      ><h2>{{ selected.task_name }}</h2>
      <StatusTag :status="selected.status" /><el-alert
        class="spaced"
        title="批准将允许 Agent 对外提交此处展示的数据。审批绑定具体页面、表单版本和参数，24 小时内有效。"
        type="warning"
        :closable="false"
        show-icon
      />
      <h3>操作参数摘要</h3>
      <pre>{{ JSON.stringify(selected.operation_summary, null, 2) }}</pre>
      <p class="muted">
        已消费：{{ selected.consumed_at ? "是" : "否" }} · 审批人 ID：{{
          selected.reviewer || "—"
        }}
      </p>
      <router-link :to="'/tasks/' + selected.task">查看任务执行 →</router-link>
      <div class="actions spaced" v-if="selected.status === 'PENDING'">
        <el-button
          type="danger"
          plain
          :loading="reviewing"
          @click="review(false)"
          >拒绝操作</el-button
        ><el-button type="primary" :loading="reviewing" @click="review(true)"
          >批准并继续</el-button
        >
      </div></template
    ></el-drawer
  >
</template>
