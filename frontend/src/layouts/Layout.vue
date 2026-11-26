<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuth } from "../stores/auth";
import {
  Grid,
  List,
  Document,
  Stamp,
  FolderOpened,
  DataLine,
  Setting,
  Expand,
  Fold,
  Sunny,
  Moon,
  Search,
  Right,
} from "@element-plus/icons-vue";
import { get, api } from "../api";
const route = useRoute(),
  router = useRouter(),
  auth = useAuth(),
  collapsed = ref(false),
  mobile = ref(false),
  search = ref(""),
  dark = ref(localStorage.getItem("theme") === "dark");
const items = [
  ["/", "工作台总览", Grid],
  ["/tasks", "任务管理", List],
  ["/templates", "任务模板", Document],
  ["/approvals", "人工审批", Stamp],
  ["/results", "结果中心", FolderOpened],
  ["/monitoring", "系统监控", DataLine],
  ["/settings", "系统设置", Setting],
] as const;
function theme() {
  document.documentElement.classList.toggle("dark", dark.value);
  localStorage.setItem("theme", dark.value ? "dark" : "light");
}
async function toggleTheme() {
  dark.value = !dark.value;
  theme();
  await api.patch("system/preferences/", {
    theme: dark.value ? "dark" : "light",
  });
}
onMounted(async () => {
  theme();
  await auth.load();
  const p = await get("system/preferences/");
  dark.value = p.theme === "dark";
  theme();
});
</script>
<template>
  <div class="shell" :class="{ collapsed }">
    <div v-if="mobile" class="scrim" @click="mobile = false"></div>
    <aside :class="{ mobile }">
      <router-link to="/" class="brand"
        ><span class="brand-mark">B<span>↗</span></span>
        <div v-if="!collapsed">
          <strong>BrowserFlow</strong><small>AGENT WORKSPACE</small>
        </div></router-link
      ><span class="nav-caption" v-if="!collapsed">工作空间</span>
      <nav>
        <router-link
          v-for="[path, label, icon] in items"
          :key="path"
          :to="path"
          :class="{
            active:
              path === '/' ? route.path === '/' : route.path.startsWith(path),
          }"
          @click="mobile = false"
          ><el-icon><component :is="icon" /></el-icon
          ><span v-if="!collapsed">{{ label }}</span></router-link
        >
      </nav>
      <div class="sidebar-note" v-if="!collapsed">
        <span class="online-dot"></span> 自然语言，驱动每一步
        <p>让网页工作流更清晰、更可控。</p>
        <span
          >Browser Use powered <el-icon><Right /></el-icon
        ></span>
      </div>
      <div class="sidebar-bottom">
        <span class="avatar">{{
          auth.user?.username?.[0]?.toUpperCase() || "B"
        }}</span>
        <div v-if="!collapsed">
          <b>{{ auth.user?.username }}</b
          ><small>个人工作空间</small>
        </div>
      </div>
    </aside>
    <section class="workspace">
      <header>
        <div class="header-start">
          <el-button
            text
            class="desktop-toggle"
            @click="collapsed = !collapsed"
            :icon="collapsed ? Expand : Fold"
            aria-label="折叠导航"
          /><el-button
            text
            class="mobile-toggle"
            @click="mobile = true"
            :icon="Expand"
            aria-label="展开导航"
          /><span class="muted">工作空间</span><span class="muted">/</span
          ><b>{{ route.meta.title }}</b>
        </div>
        <div class="header-end">
          <el-input
            v-model="search"
            :prefix-icon="Search"
            placeholder="搜索任务…"
            @keyup.enter="router.push({ path: '/tasks', query: { search } })"
            class="global-search"
          /><el-button
            text
            :icon="dark ? Sunny : Moon"
            @click="toggleTheme"
            aria-label="切换主题"
          /><el-dropdown @command="auth.logout"
            ><span class="avatar small">{{
              auth.user?.username?.[0]?.toUpperCase() || "B"
            }}</span
            ><template #dropdown
              ><el-dropdown-menu
                ><el-dropdown-item command="logout"
                  >退出登录</el-dropdown-item
                ></el-dropdown-menu
              ></template
            ></el-dropdown
          >
        </div>
      </header>
      <main><router-view :key="route.fullPath" /></main>
      <footer>
        BrowserFlow Agent <span>v1.0.0 · 可观测的浏览器自动化</span>
      </footer>
    </section>
  </div>
</template>
