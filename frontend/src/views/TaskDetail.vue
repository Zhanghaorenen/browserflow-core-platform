<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { get, post, api, download } from "../api";
import StatusTag from "../components/StatusTag.vue";
import { ElMessage } from "element-plus";
import { Refresh, VideoPlay, Close, Picture } from "@element-plus/icons-vue";
const route = useRoute(),
  router = useRouter(),
  id = String(route.params.id),
  task = ref<any>(),
  steps = ref<any[]>([]),
  runs = ref<any[]>([]),
  result = ref<any>(),
  busy = ref(false),
  selected = ref(""),
  screenshot = ref(""),
  connection = ref("连接中"),
  tab = ref("execution");
let ws: WebSocket | undefined,
  timer: ReturnType<typeof setTimeout>,
  poll: ReturnType<typeof setInterval>,
  disposed = false;
async function load() {
  const [t, s, r, res] = await Promise.all([
    get(`tasks/${id}/`),
    get(`tasks/${id}/steps/`, selected.value ? { run: selected.value } : {}),
    get(`tasks/${id}/runs/`),
    get(`tasks/${id}/result/`),
  ]);
  task.value = t;
  steps.value = s;
  runs.value = r;
  result.value = res;
  const image = [...s].reverse().find((s: any) => s.screenshot_path);
  if (image) {
    const res = await api.get(`tasks/${id}/screenshots/${image.id}/`, {
      responseType: "blob",
    });
    if (screenshot.value) URL.revokeObjectURL(screenshot.value);
    screenshot.value = URL.createObjectURL(res.data);
  } else if (screenshot.value) {
    URL.revokeObjectURL(screenshot.value);
    screenshot.value = "";
  }
}
function connect() {
  if (disposed) return;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws/tasks/${id}/`);
  ws.onopen = () =>
    ws?.send(JSON.stringify({ token: sessionStorage.getItem("access") }));
  ws.onmessage = () => {
    connection.value = "实时已连接";
    void load();
  };
  ws.onclose = () => {
    connection.value = "重连中 · HTTP 同步";
    if (!disposed) timer = setTimeout(connect, 3000);
  };
}
async function act(action: string) {
  busy.value = true;
  try {
    await post(`tasks/${id}/${action}/`);
    ElMessage.success("操作已受理");
    selected.value = "";
    await load();
  } finally {
    busy.value = false;
  }
}
onMounted(async () => {
  await load();
  connect();
  poll = setInterval(() => void load(), 8000);
});
onBeforeUnmount(() => {
  disposed = true;
  clearTimeout(timer);
  clearInterval(poll);
  ws?.close();
  if (screenshot.value) URL.revokeObjectURL(screenshot.value);
});
</script>
<template>
  <el-skeleton v-if="!task" :rows="10" animated /><template v-else
    ><div class="page-heading">
      <div>
        <span class="eyebrow">EXECUTION WORKSPACE</span>
        <h1>{{ task.name }} <StatusTag :status="task.status" /></h1>
        <p>
          {{ task.latest_run?.engine || "尚未运行" }} ·
          {{ task.latest_run?.step_count || 0 }} 个步骤 ·
          {{ task.latest_run?.duration.toFixed(1) || 0 }} 秒
          <span class="connection">● {{ connection }}</span>
        </p>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" @click="load">刷新</el-button
        ><el-button
          v-if="
            ['PENDING', 'RUNNING', 'WAITING_APPROVAL'].includes(task.status) &&
            task.latest_run
          "
          type="danger"
          plain
          :icon="Close"
          :loading="busy"
          @click="act('cancel')"
          >取消执行</el-button
        ><el-button
          v-else
          type="primary"
          :icon="VideoPlay"
          :loading="busy"
          @click="act('run')"
          >{{ task.latest_run ? "重新运行" : "启动任务" }}</el-button
        >
      </div>
    </div>
    <el-alert
      v-if="task.status === 'WAITING_APPROVAL'"
      type="warning"
      show-icon
      :closable="false"
      title="执行已暂停，浏览器已释放。请在审批中心确认操作后继续。"
      ><el-button link type="primary" @click="router.push('/approvals')"
        >前往审批中心 →</el-button
      ></el-alert
    >
    <div class="detail-grid">
      <section class="panel">
        <div class="panel-heading">
          <h3>执行时间线</h3>
          <el-select
            v-model="selected"
            placeholder="当前运行"
            clearable
            @change="load"
            style="width: 180px"
            ><el-option
              v-for="run in runs"
              :key="run.id"
              :label="'第 ' + run.attempt_number + ' 次运行'"
              :value="run.id"
          /></el-select>
        </div>
        <el-empty
          v-if="!steps.length"
          description="等待 Worker 生成第一个执行步骤"
        /><el-timeline v-else class="execution-timeline"
          ><el-timeline-item
            v-for="s in steps"
            :key="s.id"
            :timestamp="new Date(s.created_at).toLocaleTimeString()"
            :type="s.status === 'FAILED' ? 'danger' : 'primary'"
            placement="top"
            ><div class="step-card">
              <div class="panel-heading">
                <b
                  >{{ String(s.step_number).padStart(2, "0") }} ·
                  {{ s.action_name }}</b
                ><span class="muted">{{ s.duration.toFixed(2) }} s</span>
              </div>
              <p class="step-url">{{ s.page_url }}</p>
              <el-collapse
                ><el-collapse-item title="操作参数 / 详情" :name="s.id">
                  <pre>{{ JSON.stringify(s.action_parameters, null, 2) }}</pre>
                  <el-alert
                    v-if="s.error_message"
                    type="error"
                    :title="s.error_message" /></el-collapse-item
              ></el-collapse></div></el-timeline-item
        ></el-timeline>
      </section>
      <div>
        <section class="panel screenshot-panel">
          <div class="panel-heading">
            <h3>浏览器快照</h3>
            <span class="muted">最新捕获</span>
          </div>
          <el-image
            v-if="screenshot"
            :src="screenshot"
            :preview-src-list="[screenshot]"
            fit="contain"
          /><el-empty v-else description="执行截图将在这里显示" :image-size="90"
            ><template #image
              ><el-icon :size="70"><Picture /></el-icon></template
          ></el-empty>
        </section>
        <section class="panel task-info">
          <h3>任务信息</h3>
          <p>{{ task.description }}</p>
          <dl>
            <dt>目标 URL</dt>
            <dd>{{ task.target_url }}</dd>
            <dt>模型</dt>
            <dd>{{ task.model_name }}</dd>
            <dt>访问范围</dt>
            <dd>{{ task.allowed_domains.join(", ") }}</dd>
            <dt>执行预算</dt>
            <dd>{{ task.max_steps }} 步 / {{ task.timeout_seconds }} 秒</dd>
          </dl>
        </section>
      </div>
    </div>
    <section class="panel">
      <el-tabs v-model="tab"
        ><el-tab-pane label="执行详情" name="execution">
          <pre>{{
            JSON.stringify(
              { id: task.id, status: task.status, run: task.latest_run },
              null,
              2,
            )
          }}</pre></el-tab-pane
        ><el-tab-pane label="结构化结果" name="result"
          ><template v-if="result"
            ><div class="actions">
              <StatusTag :status="result.validation_status" /><el-button
                @click="download(result.id, 'json')"
                >导出 JSON</el-button
              ><el-button @click="download(result.id, 'csv')"
                >导出 CSV</el-button
              >
            </div>
            <pre>{{
              JSON.stringify(result.structured_result, null, 2)
            }}</pre></template
          ><el-empty v-else description="尚无经过验证的结果" /></el-tab-pane
        ><el-tab-pane label="错误信息" name="error"
          ><el-alert
            v-if="task.latest_run?.error_message"
            type="error"
            :title="task.latest_run.error_message" /><el-empty
            v-else
            description="没有错误记录" /></el-tab-pane
        ><el-tab-pane label="历史运行记录" name="history"
          ><el-table :data="runs"
            ><el-table-column
              prop="attempt_number"
              label="运行次数" /><el-table-column
              prop="engine"
              label="执行引擎" /><el-table-column
              prop="step_count"
              label="步骤数" /><el-table-column label="状态"
              ><template #default="{ row }"
                ><StatusTag :status="row.status" /></template></el-table-column
            ><el-table-column
              prop="duration"
              label="耗时（秒）" /></el-table></el-tab-pane
      ></el-tabs></section
  ></template>
</template>
