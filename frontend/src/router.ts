import { createRouter, createWebHistory } from "vue-router";
import NetWorthView from "./views/NetWorthView.vue";
import LoginView from "./views/LoginView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "networth", component: NetWorthView },
  ],
});

router.beforeEach((to) => {
  const token = localStorage.getItem("access_token");

  if (!token && to.path !== "/login") {
    return { path: "/login" };
  }

  if (token && to.path === "/login") {
    return { path: "/" };
  }

  return true;
});
