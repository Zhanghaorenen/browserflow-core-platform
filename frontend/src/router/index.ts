import { createRouter, createWebHistory } from "vue-router";
import Layout from "../layouts/Layout.vue";
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      component: () => import("../views/Auth.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: Layout,
      children: [
        {
          path: "",
          component: () => import("../views/Dashboard.vue"),
          meta: { title: "工作台总览" },
        },
        {
          path: "tasks",
          component: () => import("../views/Tasks.vue"),
          meta: { title: "任务管理" },
        },
        {
          path: "tasks/new",
          component: () => import("../views/CreateTask.vue"),
          meta: { title: "创建任务" },
        },
        {
          path: "tasks/:id",
          component: () => import("../views/TaskDetail.vue"),
          meta: { title: "执行工作台" },
        },
        {
          path: "templates",
          component: () => import("../views/Templates.vue"),
          meta: { title: "任务模板" },
        },
        {
          path: "approvals",
          component: () => import("../views/Approvals.vue"),
          meta: { title: "人工审批" },
        },
        {
          path: "results",
          component: () => import("../views/Results.vue"),
          meta: { title: "结果中心" },
        },
        {
          path: "monitoring",
          component: () => import("../views/Monitoring.vue"),
          meta: { title: "系统监控" },
        },
        {
          path: "settings",
          component: () => import("../views/Settings.vue"),
          meta: { title: "系统设置" },
        },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
router.beforeEach((to) => {
  if (
    !to.meta.public &&
    !sessionStorage.getItem("access") &&
    !localStorage.getItem("refresh")
  )
    return "/login";
});
export default router;
