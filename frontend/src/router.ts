import { createRouter, createWebHistory } from "vue-router";
import NetWorthView from "./views/NetWorthView.vue";
import LoginView from "./views/LoginView.vue";
import PeopleView from "./views/PeopleView.vue";
import AuxDataView from "./views/AuxDataView.vue";
import { api } from "@/lib/api";


export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "networth", component: NetWorthView },
    { path: "/people", name: "people", component: PeopleView },
    { path: "/data", name: "aux-data", component: AuxDataView },
  ],
});

let authChecked = false;
let authCheckPromise: Promise<boolean> | null = null;

async function ensureAuthValid(): Promise<boolean> {
  const token = localStorage.getItem("access_token");
  if (!token) return false;
  if (authChecked) return true;

  if (!authCheckPromise) {
    authCheckPromise = api
      .get("/api/auth/settings/")
      .then(() => {
        authChecked = true;
        return true;
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        authChecked = false;
        return false;
      })
      .finally(() => {
        authCheckPromise = null;
      });
  }

  return authCheckPromise;
}

router.beforeEach(async (to) => {
  const token = localStorage.getItem("access_token");

  if (!token && to.path !== "/login") {
    return { path: "/login" };
  }

  if (token) {
    const ok = await ensureAuthValid();
    if (!ok && to.path !== "/login") {
      return { path: "/login" };
    }
    if (ok && to.path === "/login") {
      return { path: "/" };
    }
  }

  return true;
});



