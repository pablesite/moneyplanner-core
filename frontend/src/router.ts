import { createRouter, createWebHistory } from 'vue-router';
import NetWorthView from './views/NetWorthView.vue';
import LoginView from './views/LoginView.vue';
import AuxDataView from './views/AuxDataView.vue';
import { registerAuthGuard } from '@/domains/auth/guard';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'networth', component: NetWorthView },
    { path: '/data', name: 'aux-data', component: AuxDataView },
  ],
});

registerAuthGuard(router);
