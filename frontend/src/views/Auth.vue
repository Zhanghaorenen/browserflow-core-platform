<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../stores/auth";
import { post } from "../api";
import { ElMessage } from "element-plus";
const router = useRouter(),
  auth = useAuth(),
  register = ref(false),
  busy = ref(false),
  form = ref(),
  data = reactive({ username: "", email: "", password: "", remember: true });
const rules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 3, message: "至少三个字符", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 10, message: "至少十个字符", trigger: "blur" },
  ],
  email: [{ type: "email", message: "请输入有效邮箱", trigger: "blur" }],
};
async function submit() {
  if (!(await form.value.validate().catch(() => false))) return;
  busy.value = true;
  try {
    if (register.value) {
      await post("auth/register/", data);
      ElMessage.success("注册成功，请登录");
      register.value = false;
    } else {
      await auth.login(data.username, data.password, data.remember);
      router.push("/");
    }
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="auth">
    <section class="auth-story">
      <div class="brand">
        <span class="brand-mark">B↗</span><strong>BrowserFlow Agent</strong>
      </div>
      <div>
        <span class="eyebrow">YOUR BROWSER. YOUR WORKFLOW.</span>
        <h1>把重复的网页工作，<br />交给智能 Agent。</h1>
        <p>
          从一句自然语言开始，到每一个可追踪的执行步骤。<br />编排、审批、验证，在一个工作台完成。
        </p>
        <div class="workflow">
          <span>01 描述任务</span><i>→</i><span>02 智能执行</span><i>→</i
          ><span>03 结果验证</span>
        </div>
      </div>
      <small>基于开源 Browser Use · 独立业务编排平台</small>
    </section>
    <section class="auth-form">
      <div class="auth-card">
        <span class="eyebrow">开始你的自动化工作流</span>
        <h2>{{ register ? "创建账号" : "欢迎回来" }}</h2>
        <p class="muted">
          {{
            register
              ? "建立你的个人 Agent 工作空间"
              : "登录 BrowserFlow，继续推进你的任务。"
          }}
        </p>
        <el-form
          ref="form"
          :model="data"
          :rules="rules"
          label-position="top"
          @submit.prevent="submit"
          ><el-form-item label="用户名 / 邮箱" prop="username"
            ><el-input
              v-model="data.username"
              size="large"
              autocomplete="username"
              placeholder="输入用户名" /></el-form-item
          ><el-form-item v-if="register" label="邮箱" prop="email"
            ><el-input v-model="data.email" size="large" /></el-form-item
          ><el-form-item label="密码" prop="password"
            ><el-input
              v-model="data.password"
              type="password"
              show-password
              size="large"
              autocomplete="current-password"
              placeholder="至少 10 个字符" /></el-form-item
          ><el-checkbox v-model="data.remember" v-if="!register"
            >记住登录状态</el-checkbox
          ><el-button
            class="full auth-submit"
            type="primary"
            size="large"
            :loading="busy"
            native-type="submit"
            >{{ register ? "注册账号" : "登录工作空间 →" }}</el-button
          ></el-form
        >
        <p class="center muted">
          {{ register ? "已有账号？" : "还没有账号？" }}
          <el-button link type="primary" @click="register = !register">{{
            register ? "立即登录" : "创建账号"
          }}</el-button>
        </p>
      </div>
    </section>
  </div>
</template>
