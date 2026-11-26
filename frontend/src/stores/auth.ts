import { defineStore } from "pinia";
import { ref } from "vue";
import { api, get, post } from "../api";
export const useAuth = defineStore("auth", () => {
  const user = ref<any>(null);
  async function load() {
    user.value = await get("auth/me/");
  }
  async function login(username: string, password: string, remember: boolean) {
    const d = await post("auth/login/", { username, password });
    sessionStorage.setItem("access", d.access);
    sessionStorage.setItem("refresh", d.refresh);
    if (remember) localStorage.setItem("refresh", d.refresh);
    await load();
  }
  async function logout() {
    try {
      await post("auth/logout/", {
        refresh:
          sessionStorage.getItem("refresh") || localStorage.getItem("refresh"),
      });
    } finally {
      sessionStorage.clear();
      localStorage.removeItem("refresh");
      user.value = null;
      location.assign("/login");
    }
  }
  return { user, load, login, logout, api };
});
