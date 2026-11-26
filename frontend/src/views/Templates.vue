<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { api, get, post } from "../api";
import { ElMessage, ElMessageBox } from "element-plus";
import { Document, Plus, Right } from "@element-plus/icons-vue";
const router = useRouter(),
  rows = ref<any[]>([]),
  busy = ref(false),
  dialog = ref(false),
  editing = ref<number>(),
  form = ref<any>({}),
  configText = ref("{}"),
  schema = ref("{}"),
  total = ref(0),
  page = ref(1);
async function load() {
  busy.value = true;
  try {
    const d = await get("templates/", { page: page.value });
    rows.value = d.results;
    total.value = d.count;
  } finally {
    busy.value = false;
  }
}
function edit(t?: any) {
  editing.value = t?.id;
  form.value = t
    ? { ...t }
    : {
        name: "",
        description: "",
        prompt_template: "",
        requires_approval: false,
      };
  configText.value = JSON.stringify(
    t?.default_config || {
      target_url: "",
      allowed_domains: [],
      parameters: {},
    },
    null,
    2,
  );
  schema.value = JSON.stringify(t?.output_schema || {}, null, 2);
  dialog.value = true;
}
async function save() {
  if (!form.value.name || !form.value.prompt_template) {
    ElMessage.warning("请填写名称和任务提示词");
    return;
  }
  let payload;
  try {
    payload = {
      ...form.value,
      default_config: JSON.parse(configText.value),
      output_schema: JSON.parse(schema.value),
    };
  } catch {
    ElMessage.error("配置必须是合法 JSON");
    return;
  }
  if (editing.value) await api.put(`templates/${editing.value}/`, payload);
  else await post("templates/", payload);
  dialog.value = false;
  ElMessage.success("模板已保存");
  await load();
}
async function remove(t: any) {
  await ElMessageBox.confirm("删除个人模板？", "删除确认");
  await api.delete(`templates/${t.id}/`);
  await load();
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">REUSABLE WORKFLOWS</span>
      <h1>任务模板</h1>
      <p>把成熟的任务流程，变成下一次执行的起点。</p>
    </div>
    <el-button type="primary" :icon="Plus" @click="edit()">创建模板</el-button>
  </div>
  <el-skeleton :loading="busy" :rows="8" animated
    ><template #default
      ><div class="template-grid">
        <section class="panel template-card" v-for="t in rows" :key="t.id">
          <div class="panel-heading">
            <span class="template-icon"
              ><el-icon :size="26"><Document /></el-icon></span
            ><el-tag size="small" :type="t.owner ? 'info' : 'primary'">{{
              t.owner ? "个人模板" : "内置模板"
            }}</el-tag>
          </div>
          <h2>{{ t.name }}</h2>
          <p>{{ t.description }}</p>
          <span class="muted">{{
            t.requires_approval ? "人工审批 · 写入操作" : "独立验收 · 数据采集"
          }}</span>
          <div class="template-actions">
            <el-button
              type="primary"
              plain
              @click="
                router.push({ path: '/tasks/new', query: { template: t.id } })
              "
              >使用模板 <el-icon><Right /></el-icon></el-button
            ><template v-if="t.owner"
              ><el-button link @click="edit(t)">编辑</el-button
              ><el-button link type="danger" @click="remove(t)"
                >删除</el-button
              ></template
            >
          </div>
        </section>
      </div>
      <el-empty v-if="!rows.length" description="暂无模板" /><el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="20"
        layout="prev,pager,next"
        @current-change="load" /></template></el-skeleton
  ><el-dialog
    v-model="dialog"
    :title="editing ? '编辑模板' : '创建模板'"
    width="min(640px,94vw)"
    ><el-form label-position="top"
      ><el-form-item label="模板名称"
        ><el-input v-model="form.name" /></el-form-item
      ><el-form-item label="描述"
        ><el-input v-model="form.description" /></el-form-item
      ><el-form-item label="任务提示词"
        ><el-input
          v-model="form.prompt_template"
          type="textarea"
          :rows="4" /></el-form-item
      ><el-form-item label="默认任务配置 JSON"
        ><el-input
          v-model="configText"
          type="textarea"
          :rows="5" /></el-form-item
      ><el-form-item label="输出 JSON Schema"
        ><el-input v-model="schema" type="textarea" :rows="4" /></el-form-item
      ><el-checkbox v-model="form.requires_approval"
        >包含人工审批步骤</el-checkbox
      ></el-form
    ><template #footer
      ><el-button @click="dialog = false">取消</el-button
      ><el-button type="primary" @click="save">保存模板</el-button></template
    ></el-dialog
  >
</template>
