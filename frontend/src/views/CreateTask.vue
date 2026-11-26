<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { get, post } from "../api";
import { ElMessage } from "element-plus";
import { Right, Lock } from "@element-plus/icons-vue";
const router = useRouter(),
  route = useRoute(),
  form = ref(),
  busy = ref(true),
  templates = ref<any[]>([]),
  health = ref<any>({ models: ["mock"] }),
  domains = ref(""),
  schemaText = ref("{}"),
  paramsText = ref("{}"),
  templateId = ref<number>();
const data = reactive({
  name: "",
  description: "",
  target_url: "",
  model_name: "mock",
  max_steps: 20,
  timeout_seconds: 120,
  output_type: "json",
});
const rules = {
  name: [{ required: true, message: "请输入任务名称", trigger: "blur" }],
  description: [
    { required: true, message: "请描述你的任务目标", trigger: "blur" },
  ],
  target_url: [
    { required: true, message: "请输入目标 URL", trigger: "blur" },
    { type: "url", message: "请输入有效 URL", trigger: "blur" },
  ],
};
function applyTemplate(id: number) {
  const t = templates.value.find((t) => t.id === id);
  if (!t) return;
  data.name = t.name;
  data.description = t.prompt_template;
  Object.assign(data, t.default_config);
  domains.value = t.default_config.allowed_domains?.join(", ") || "";
  schemaText.value = JSON.stringify(t.output_schema, null, 2);
  paramsText.value = JSON.stringify(t.default_config.parameters || {}, null, 2);
}
onMounted(async () => {
  const [t, h, p] = await Promise.all([
    get("templates/"),
    get("system/health/"),
    get("system/preferences/"),
  ]);
  templates.value = t.results;
  health.value = h;
  Object.assign(data, {
    model_name: p.model_name,
    max_steps: p.max_steps,
    timeout_seconds: p.timeout_seconds,
  });
  domains.value = p.allowed_domains.join(", ");
  if (route.query.template) {
    templateId.value = Number(route.query.template);
    applyTemplate(templateId.value);
  }
  busy.value = false;
});
async function submit() {
  if (!(await form.value.validate().catch(() => false))) return;
  if (!domains.value.trim()) {
    ElMessage.warning("请填写域名白名单");
    return;
  }
  let parameters, output_schema;
  try {
    parameters = JSON.parse(paramsText.value);
    output_schema = JSON.parse(schemaText.value);
  } catch {
    ElMessage.error("参数和结果 Schema 必须是合法 JSON");
    return;
  }
  busy.value = true;
  try {
    const task = await post("tasks/", {
      ...data,
      allowed_domains: domains.value.split(/[,，\s]+/).filter(Boolean),
      parameters,
      output_schema,
    });
    await post(`tasks/${task.id}/run/`);
    router.push("/tasks/" + task.id);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">NEW AUTOMATION</span>
      <h1>让 Agent 接手下一个任务</h1>
      <p>描述你想完成的工作，配置执行边界，然后开始。</p>
    </div>
    <el-button @click="router.push('/tasks')">返回任务列表</el-button>
  </div>
  <el-form
    ref="form"
    :model="data"
    :rules="rules"
    label-position="top"
    @submit.prevent="submit"
    ><div class="create-grid">
      <section class="panel form-panel">
        <div class="panel-heading">
          <h3>任务目标</h3>
          <span class="subtle-badge">01</span>
        </div>
        <el-form-item label="从模板开始"
          ><el-select
            v-model="templateId"
            placeholder="选择一个模板，快速开始"
            clearable
            @change="applyTemplate"
            ><el-option
              v-for="t in templates"
              :key="t.id"
              :label="t.name"
              :value="t.id" /></el-select></el-form-item
        ><el-form-item label="任务名称" prop="name"
          ><el-input
            v-model="data.name"
            placeholder="例如：采集产品目录并汇总价格"
            maxlength="160"
            show-word-limit /></el-form-item
        ><el-form-item label="用自然语言描述任务" prop="description"
          ><el-input
            v-model="data.description"
            type="textarea"
            :rows="8"
            placeholder="访问目标网页，收集前五条产品信息，提取名称、价格和来源链接，并保存结构化结果。" /></el-form-item
        ><el-form-item label="目标 URL" prop="target_url"
          ><el-input
            v-model="data.target_url"
            placeholder="https://example.com/products" /></el-form-item
        ><el-form-item label="允许访问的域名"
          ><el-input
            v-model="domains"
            placeholder="example.com, docs.example.com"
          /><small class="muted"
            >填写精确域名，使用逗号分隔；任务仅能访问此范围。</small
          ></el-form-item
        ><el-collapse
          ><el-collapse-item title="业务参数与结果验收 Schema" name="advanced"
            ><el-form-item label="业务参数 JSON"
              ><el-input
                v-model="paramsText"
                type="textarea"
                :rows="6" /></el-form-item
            ><el-form-item label="结果 JSON Schema"
              ><el-input
                v-model="schemaText"
                type="textarea"
                :rows="6" /></el-form-item></el-collapse-item
        ></el-collapse>
      </section>
      <div>
        <section class="panel form-panel">
          <div class="panel-heading">
            <h3>执行配置</h3>
            <span class="subtle-badge">02</span>
          </div>
          <el-form-item label="执行模型"
            ><el-select v-model="data.model_name"
              ><el-option
                v-for="m in health.models"
                :key="m"
                :value="m"
                :label="
                  m === 'mock' ? 'Mock · 本地浏览器驱动' : m
                " /></el-select></el-form-item
          ><el-alert
            v-if="data.model_name === 'mock'"
            title="确定性驱动操作真实 Demo 网页，不调用 LLM。执行记录标记为 Mock。"
            :closable="false"
            type="info"
          /><el-form-item label="最大执行步骤"
            ><el-input-number
              v-model="data.max_steps"
              :min="1"
              :max="100" /></el-form-item
          ><el-form-item label="超时时间（秒）"
            ><el-input-number
              v-model="data.timeout_seconds"
              :min="5"
              :max="900" /></el-form-item
          ><el-form-item label="输出格式"
            ><el-radio-group v-model="data.output_type"
              ><el-radio-button value="json">JSON</el-radio-button
              ><el-radio-button value="csv"
                >CSV</el-radio-button
              ></el-radio-group
            ></el-form-item
          ><el-button
            type="primary"
            size="large"
            class="full"
            native-type="submit"
            :loading="busy"
            >创建并运行 <el-icon><Right /></el-icon
          ></el-button>
        </section>
        <section class="safety-card">
          <el-icon><Lock /></el-icon>
          <h4>安全，由你掌控</h4>
          <p>
            访问限制在白名单内。表单提交需人工审批；不支持的写入工具默认禁用。浏览器会话按运行隔离。
          </p>
        </section>
      </div>
    </div></el-form
  >
</template>
