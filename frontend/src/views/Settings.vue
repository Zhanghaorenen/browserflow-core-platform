<script setup lang="ts">
import { ref, onMounted } from "vue";
import { get, post, api } from "../api";
import { ElMessage } from "element-plus";
const user = ref<any>({}),
  prefs = ref<any>({}),
  health = ref<any>({ models: ["mock"] }),
  domains = ref(""),
  password = ref({ old_password: "", new_password: "" }),
  busy = ref(false),
  probe = ref(""),
  tab = ref("profile");
onMounted(async () => {
  [user.value, prefs.value, health.value] = await Promise.all([
    get("auth/me/"),
    get("system/preferences/"),
    get("system/health/"),
  ]);
  domains.value = prefs.value.allowed_domains.join(", ");
});
async function save() {
  busy.value = true;
  try {
    await api.patch("auth/me/", user.value);
    prefs.value.allowed_domains = domains.value
      .split(/[,，\s]+/)
      .filter(Boolean);
    await api.patch("system/preferences/", prefs.value);
    document.documentElement.classList.toggle(
      "dark",
      prefs.value.theme === "dark",
    );
    localStorage.setItem("theme", prefs.value.theme);
    ElMessage.success("设置已保存");
  } finally {
    busy.value = false;
  }
}
async function changePassword() {
  await post("auth/password/", password.value);
  password.value = { old_password: "", new_password: "" };
  ElMessage.success("密码已修改");
}
async function test() {
  const d = await post("system/model-probe/");
  probe.value = d.connected
    ? "模型端点连接成功"
    : d.detail || "端点返回 HTTP " + d.http_status;
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">PREFERENCES</span>
      <h1>系统设置</h1>
      <p>管理个人资料及你的默认执行偏好。</p>
    </div>
    <el-button type="primary" :loading="busy" @click="save">保存设置</el-button>
  </div>
  <section class="panel settings-panel">
    <el-tabs v-model="tab"
      ><el-tab-pane label="基本资料" name="profile"
        ><el-form label-position="top"
          ><el-form-item label="用户名"
            ><el-input :model-value="user.username" disabled /></el-form-item
          ><el-form-item label="邮箱"
            ><el-input v-model="user.email" type="email" /></el-form-item
          ><el-form-item label="名字"
            ><el-input v-model="user.first_name" /></el-form-item
          ><el-form-item label="姓氏"
            ><el-input
              v-model="user.last_name" /></el-form-item></el-form></el-tab-pane
      ><el-tab-pane label="Agent 默认配置" name="agent"
        ><el-form label-position="top"
          ><el-form-item label="默认执行模型"
            ><el-select v-model="prefs.model_name"
              ><el-option
                v-for="m in health.models"
                :key="m"
                :value="m"
                :label="m" /></el-select></el-form-item
          ><el-form-item label="默认最大步骤"
            ><el-input-number
              v-model="prefs.max_steps"
              :min="1"
              :max="100" /></el-form-item
          ><el-form-item label="默认任务超时（秒）"
            ><el-input-number
              v-model="prefs.timeout_seconds"
              :min="5"
              :max="900" /></el-form-item
          ><el-form-item label="默认域名白名单"
            ><el-input
              v-model="domains"
              placeholder="使用逗号分隔" /></el-form-item
          ><el-button @click="test">测试模型连接</el-button>
          <p>{{ probe }}</p>
          <el-alert
            type="info"
            :closable="false"
            title="模型地址和密钥由服务端环境变量管理，不在浏览器中存储或显示。" /></el-form></el-tab-pane
      ><el-tab-pane label="界面主题" name="theme"
        ><el-radio-group v-model="prefs.theme"
          ><el-radio-button value="light">浅色主题</el-radio-button
          ><el-radio-button value="dark"
            >深色主题</el-radio-button
          ></el-radio-group
        ></el-tab-pane
      ><el-tab-pane label="账号安全" name="security"
        ><el-form label-position="top"
          ><el-form-item label="原密码"
            ><el-input
              v-model="password.old_password"
              type="password"
              show-password /></el-form-item
          ><el-form-item label="新密码（至少十个字符）"
            ><el-input
              v-model="password.new_password"
              type="password"
              show-password /></el-form-item
          ><el-button type="primary" @click="changePassword"
            >修改密码</el-button
          ></el-form
        ></el-tab-pane
      ><el-tab-pane label="系统信息" name="about"
        ><h2>BrowserFlow Agent</h2>
        <p>智能网页任务编排与自动化执行平台 · v{{ health.version }}</p>
        <p class="muted">Vue 3 / Django 5.2 / Celery / Browser Use</p>
        <p>
          Browser Use 采用 MIT
          许可证。本项目独立实现任务调度、审批、追踪与可靠性验证。
        </p></el-tab-pane
      ></el-tabs
    >
  </section>
</template>
