import axios from "axios";
import { ElMessage } from "element-plus";
export const api = axios.create({ baseURL: "/api/v1/", timeout: 20000 });
let refreshFlight: Promise<string> | null = null;
api.interceptors.request.use((c) => {
  const t = sessionStorage.getItem("access");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
api.interceptors.response.use(
  (r) => {
    if (r.data?.data !== undefined) r.data = r.data.data;
    return r;
  },
  async (e) => {
    const c = e.config;
    if (
      e.response?.status === 401 &&
      !c?._retry &&
      !c?.url?.includes("auth/")
    ) {
      c._retry = true;
      try {
        if (!refreshFlight)
          refreshFlight = axios
            .post("/api/v1/auth/refresh/", {
              refresh:
                sessionStorage.getItem("refresh") ||
                localStorage.getItem("refresh"),
            })
            .then((r) => {
              const d = r.data.data;
              sessionStorage.setItem("access", d.access);
              sessionStorage.setItem("refresh", d.refresh);
              if (localStorage.getItem("refresh"))
                localStorage.setItem("refresh", d.refresh);
              return d.access;
            })
            .finally(() => (refreshFlight = null));
        await refreshFlight;
        return api(c);
      } catch {
        sessionStorage.clear();
        localStorage.removeItem("refresh");
        location.assign("/login");
      }
    }
    ElMessage.error(
      JSON.stringify(e.response?.data?.error || "网络请求失败，请重试"),
    );
    return Promise.reject(e);
  },
);
export async function get<T = any>(url: string, params?: any): Promise<T> {
  return (await api.get(url, { params })).data;
}
export async function post<T = any>(url: string, data?: any): Promise<T> {
  return (await api.post(url, data)).data;
}
export async function download(id: number, format: string) {
  const r = await api.get(`results/${id}/export/`, {
    params: { format_type: format },
    responseType: "blob",
  });
  const u = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = u;
  a.download = `browserflow-${id}.${format}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
