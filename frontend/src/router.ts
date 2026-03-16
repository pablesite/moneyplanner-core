import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import NetWorthView from './views/NetWorthView.vue';
import LoginView from './views/LoginView.vue';
import HomeView from './views/HomeView.vue';
import GuidePhaseDetailView from './views/GuidePhaseDetailView.vue';
import DataInputView from './views/DataInputView.vue';
import BudgetDashboardView from './views/BudgetDashboardView.vue';
import AuxDataView from './views/AuxDataView.vue';
import AccountView from './views/AccountView.vue';
import PeopleView from './views/PeopleView.vue';
import AccountingMovementsView from './views/AccountingMovementsView.vue';
import { registerAuthGuard } from '@/domains/auth';

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: LoginView },
  { path: '/', name: 'home', component: HomeView },
  { path: '/inicio', redirect: '/' },
  { path: '/guia/fases/:phaseId', name: 'guide-phase', component: GuidePhaseDetailView },
  { path: '/introduccion-datos', name: 'data-input', component: DataInputView },
  { path: '/patrimonio', name: 'networth', component: NetWorthView },
  { path: '/presupuesto', name: 'budget-dashboard', component: BudgetDashboardView },
  {
    path: '/cierre-mensual',
    name: 'monthly-close',
    component: BudgetDashboardView,
    props: { mode: 'monthly-close' as const },
  },
  { path: '/data', name: 'aux-data', component: AuxDataView },
  { path: '/data/fx', redirect: '/data' },
  { path: '/data/ipc', redirect: '/data' },
  { path: '/account', name: 'account', component: AccountView },
  { path: '/people', name: 'people', component: PeopleView },
  { path: '/movimientos', name: 'accounting-movements', component: AccountingMovementsView },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

registerAuthGuard(router);
