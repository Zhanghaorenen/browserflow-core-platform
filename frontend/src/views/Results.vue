<script setup lang="ts">
import { ref, onMounted } from "vue";
import { get, download } from "../api";
import StatusTag from "../components/StatusTag.vue";
import { Search, Refresh } from "@element-plus/icons-vue";
const rows = ref<any[]>([]),
  selected = ref<any>(),
  view = ref("table"),
  total = ref(0),
  page = ref(1),
  search = ref(""),
  busy = ref(false);
async function load() {
  busy.value = true;
  try {
    const d = await get("results/", { page: page.value, search: search.value });
    rows.value = d.results;
    total.value = d.count;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">VERIFIED OUTPUTS</span>
      <h1>任务结果中心</h1>
      <p>每一份结果都有来源、有记录、经过验证。</p>
    </div>
    <el-button :icon="Refresh" @click="load">刷新</el-button>
  </div>
  <section class="panel">
    <div class="toolbar">
      <el-input
        v-model="search"
        :prefix-icon="Search"
        placeholder="按任务名称查询"
        @keyup.enter="
          page = 1;
          load();
        "
        clearable
      /><el-button
        @click="
          page = 1;
          load();
        "
        >查询</el-button
      >
    </div>
    <el-table :data="rows" v-loading="busy"
      ><el-table-column
        prop="task_name"
        label="任务名称"
        min-width="200" /><el-table-column
        prop="engine"
        label="引擎" /><el-table-column label="验证状态"
        ><template #default="{ row }"
          ><StatusTag
            :status="row.validation_status" /></template></el-table-column
      ><el-table-column label="数据条数"
        ><template #default="{ row }">{{
          row.structured_result.items.length
        }}</template></el-table-column
      ><el-table-column label="采集时间" min-width="170"
        ><template #default="{ row }">{{
          new Date(row.created_at).toLocaleString()
        }}</template></el-table-column
      ><el-table-column label="操作" width="210"
        ><template #default="{ row }"
          ><el-button link type="primary" @click="selected = row"
            >查看</el-button
          ><el-button link @click="download(row.id, 'csv')">CSV</el-button
          ><el-button link @click="download(row.id, 'json')"
            >JSON</el-button
          ></template
        ></el-table-column
      ><template #empty
        ><el-empty
          description="完成任务后，经过验证的结果会出现在这里" /></template></el-table
    ><el-pagination
      class="pagination"
      v-model:current-page="page"
      :total="total"
      :page-size="20"
      layout="total,prev,pager,next"
      @current-change="load"
    />
  </section>
  <el-dialog
    :model-value="!!selected"
    @close="selected = null"
    title="结构化结果"
    width="min(900px,94vw)"
    ><template v-if="selected"
      ><div class="panel-heading">
        <router-link :to="'/tasks/' + selected.task_id"
          >{{ selected.task_name }} →</router-link
        ><el-radio-group v-model="view"
          ><el-radio-button value="table">表格</el-radio-button
          ><el-radio-button value="json">JSON</el-radio-button></el-radio-group
        >
      </div>
      <el-table v-if="view === 'table'" :data="selected.structured_result.items"
        ><el-table-column
          v-for="key in [
            ...new Set(
              selected.structured_result.items.flatMap((r: any) =>
                Object.keys(r),
              ),
            ),
          ]"
          :key="String(key)"
          :prop="String(key)"
          :label="String(key)"
          min-width="160"
      /></el-table>
      <pre v-else>{{
        JSON.stringify(selected.structured_result, null, 2)
      }}</pre>
      <h4>来源 URL</h4>
      <p v-for="url in selected.source_urls" :key="url">
        <a :href="url" target="_blank" rel="noopener noreferrer">{{ url }}</a>
      </p></template
    ></el-dialog
  >
</template>
