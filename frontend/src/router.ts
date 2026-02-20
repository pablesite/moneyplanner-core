import { createRouter, createWebHistory } from 'vue-router';
import NetWorthView from './views/NetWorthView.vue';
import LoginView from './views/LoginView.vue';
import HomeView from './views/HomeView.vue';
import DataInputView from './views/DataInputView.vue';
import AuxDataView from './views/AuxDataView.vue';
import { registerAuthGuard } from '@/domains/auth';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/inicio', name: 'home', component: HomeView },
    { path: '/introduccion-datos', name: 'data-input', component: DataInputView },
    { path: '/', name: 'networth', component: NetWorthView },
    { path: '/data', name: 'aux-data', component: AuxDataView },
  ],
});

registerAuthGuard(router);
