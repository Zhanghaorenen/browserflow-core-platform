<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, get, post } from "../api";
import StatusTag from "../components/StatusTag.vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Refresh, Search } from "@element-plus/icons-vue";
const router = useRouter(),
  route = useRoute(),
  rows = ref<any[]>([]),
  total = ref(0),
  page = ref(1),
  search = ref(String(route.query.search || "")),
  status = ref(""),
  dates = ref<string[]>([]),
  busy = ref(false),
  failed = ref(false);
async function load() {
  busy.value = true;
  failed.value = false;
  try {
    const d = await get("tasks/", {
      page: page.value,
      search: search.value,
      status: status.value,
      after: dates.value?.[0],
      before: dates.value?.[1],
    });
    rows.value = d.results;
    total.value = d.count;
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
async function act(row: any, action: string) {
  if (action === "delete") {
    await ElMessageBox.confirm("删除该任务及全部执行记录？", "删除任务", {
      type: "warning",
    });
    await api.delete(`tasks/${row.id}/`);
  } else await post(`tasks/${row.id}/${action}/`);
  ElMessage.success("操作完成");
  await load();
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">TASK ORCHESTRATION</span>
      <h1>任务管理</h1>
      <p>创建、追踪和管理你的浏览器自动化任务。</p>
    </div>
    <el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')"
      >创建任务</el-button
    >
  </div>
  <section class="panel">
    <div class="toolbar">
      <el-input
        v-model="search"
        :prefix-icon="Search"
        placeholder="搜索任务名称"
        clearable
        @keyup.enter="
          page = 1;
          load();
        "
      /><el-select
        v-model="status"
        placeholder="全部状态"
        clearable
        @change="
          page = 1;
          load();
        "
        ><el-option
          v-for="s in [
            'PENDING',
            'RUNNING',
            'WAITING_APPROVAL',
            'SUCCEEDED',
            'FAILED',
            'CANCELLED',
          ]"
          :key="s"
          :value="s"
          :label="s" /></el-select
      ><el-date-picker
        v-model="dates"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        @change="
          page = 1;
          load();
        "
      /><el-button
        @click="
          search = '';
          status = '';
          dates = [];
          page = 1;
          load();
        "
        >重置</el-button
      ><el-button :icon="Refresh" :loading="busy" @click="load">刷新</el-button>
    </div>
    <el-alert
      v-if="failed"
      type="error"
      title="任务加载失败，请刷新重试"
    /><el-table :data="rows" v-loading="busy"
      ><el-table-column label="任务" min-width="220"
        ><template #default="{ row }"
          ><el-button
            link
            type="primary"
            @click="router.push('/tasks/' + row.id)"
            >{{ row.name }}</el-button
          >
          <p class="table-description">
            {{ row.description.slice(0, 70) }}
          </p></template
        ></el-table-column
      ><el-table-column label="状态" width="140"
        ><template #default="{ row }"
          ><StatusTag :status="row.status" /></template></el-table-column
      ><el-table-column
        prop="model_name"
        label="模型"
        width="140" /><el-table-column label="步骤 / 耗时" width="140"
        ><template #default="{ row }"
          >{{ row.latest_run?.step_count || 0 }} 步 ·
          {{ row.latest_run?.duration.toFixed(1) || 0 }}s</template
        ></el-table-column
      ><el-table-column label="创建时间" width="170"
        ><template #default="{ row }">{{
          new Date(row.created_at).toLocaleString("zh-CN")
        }}</template></el-table-column
      ><el-table-column label="操作" width="185" fixed="right"
        ><template #default="{ row }"
          ><el-button link @click="router.push('/tasks/' + row.id)"
            >详情</el-button
          ><el-button
            link
            type="warning"
            v-if="
              ['RUNNING', 'PENDING', 'WAITING_APPROVAL'].includes(row.status) &&
              row.latest_run
            "
            @click="act(row, 'cancel')"
            >取消</el-button
          ><el-button link type="primary" v-else @click="act(row, 'run')">{{
            row.latest_run ? "重试" : "运行"
          }}</el-button
          ><el-button link type="danger" @click="act(row, 'delete')"
            >删除</el-button
          ></template
        ></el-table-column
      ><template #empty
        ><el-empty description="没有匹配的任务" /></template></el-table
    ><el-pagination
      class="pagination"
      background
      layout="total, prev, pager, next"
      :total="total"
      :page-size="20"
      v-model:current-page="page"
      @current-change="load"
    />
  </section>
</template>
