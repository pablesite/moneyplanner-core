<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { clearAuthTokens, hasAccessToken } from '@/domains/auth/session';

type NavItem = {
  id: string;
  icon: string;
  label: string;
  hint: string;
  to: string;
};

const route = useRoute();
const router = useRouter();
const sidebarOpen = ref(false);
const accountMenuOpen = ref(false);
const accountMenuRef = ref<HTMLElement | null>(null);
const accountLabel = ref('Mi cuenta');
const accountRole = ref('');
const accountPlan = ref('');

const hasToken = computed(() => hasAccessToken.value);
const isLoginRoute = computed(() => route.name === 'login');
const navItems = computed<NavItem[]>(() => {
  const baseItems: NavItem[] = [
    { id: 'home', icon: 'GU', label: 'Guia', hint: 'Plan paso a paso', to: '/' },
    {
      id: 'data-input',
      icon: 'IN',
      label: 'Introduccion de datos',
      hint: 'Ingresos, gastos, activos y pasivos',
      to: '/introduccion-datos',
    },
    {
      id: 'net-worth',
      icon: 'PT',
      label: 'Patrimonio',
      hint: 'Estado financiero',
      to: '/patrimonio',
    },
    {
      id: 'budget',
      icon: 'PR',
      label: 'Presupuesto',
      hint: 'Plan anual de ingresos y gastos',
      to: '/presupuesto',
    },
    {
      id: 'monthly-close',
      icon: 'CM',
      label: 'Cierre mensual',
      hint: 'Liquidez, ingresos, gastos y residual',
      to: '/cierre-mensual',
    },
    {
      id: 'accounting-movements',
      icon: 'LD',
      label: 'Movimientos',
      hint: 'Libro diario y cuentas contables',
      to: '/movimientos',
    },
  ];

  return baseItems;
});

const pageTitle = 'moneyplanner';

function isNavItemActive(item: NavItem): boolean {
  if (item.id === 'home') {
    return route.path === '/' || route.path.startsWith('/guia/');
  }
  return route.path === item.to || route.path.startsWith(`${item.to}/`);
}

const accountInitials = computed(() => {
  const text = accountLabel.value.trim();
  if (!text || text === 'Mi cuenta') return 'MC';
  const words = text.split(/\s+/).filter(Boolean);
  const first = words[0] ?? '';
  const second = words[1] ?? '';
  if (!second) {
    return first.slice(0, 2).toUpperCase();
  }
  return `${first[0] ?? ''}${second[0] ?? ''}`.toUpperCase();
});

function toggleSidebar(): void {
  sidebarOpen.value = !sidebarOpen.value;
}

function closeSidebar(): void {
  sidebarOpen.value = false;
}

function toggleAccountMenu(): void {
  accountMenuOpen.value = !accountMenuOpen.value;
}

function closeAccountMenu(): void {
  accountMenuOpen.value = false;
}

function logout(): void {
  clearAuthTokens();
  closeAccountMenu();
  sidebarOpen.value = false;
  router.push('/login');
}

function handleGlobalKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    if (sidebarOpen.value) closeSidebar();
    if (accountMenuOpen.value) closeAccountMenu();
  }
}

function handleGlobalClick(event: MouseEvent): void {
  if (!accountMenuOpen.value) return;
  const target = event.target as Node | null;
  if (!target) return;
  if (accountMenuRef.value && !accountMenuRef.value.contains(target)) {
    closeAccountMenu();
  }
}

watch(sidebarOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : '';
});

watch(
  () => route.fullPath,
  () => {
    sidebarOpen.value = false;
    accountMenuOpen.value = false;
  },
);

watch(
  hasToken,
  (tokenPresent) => {
    if (!tokenPresent) {
      accountLabel.value = 'Mi cuenta';
      accountRole.value = '';
      accountPlan.value = '';
      return;
    }
    accountLabel.value = 'Mi cuenta';
    accountRole.value = '';
    accountPlan.value = '';
  },
  { immediate: true },
);

window.addEventListener('keydown', handleGlobalKeydown);
document.addEventListener('click', handleGlobalClick);
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
  document.removeEventListener('click', handleGlobalClick);
  document.body.style.overflow = '';
});
</script>

<template>
  <router-view v-if="isLoginRoute" />

  <div v-else class="ui-shell">
    <div v-if="sidebarOpen" class="ui-shell-backdrop" @click="closeSidebar" />

    <aside class="ui-shell-sidebar" :class="{ 'ui-shell-sidebar-open': sidebarOpen }">
      <div class="ui-shell-sidebar-top">
        <div class="ui-shell-brand">
          <div class="ui-shell-brand-mark">MP</div>
          <div class="ui-shell-brand-text">
            <strong>Moneyplanner</strong>
            <span>Coach financiero</span>
          </div>
        </div>
        <button
          class="icon-btn ui-shell-icon-btn"
          type="button"
          aria-label="Cerrar menu"
          @click="closeSidebar"
        >
          <span aria-hidden="true">X</span>
        </button>
      </div>

      <nav class="ui-shell-nav" aria-label="Navegacion principal">
        <div class="ui-shell-nav-section">Navegacion</div>
        <RouterLink
          v-for="item in navItems"
          :key="item.id"
          :to="item.to"
          class="ui-shell-link"
          :class="{ 'ui-shell-link-active': isNavItemActive(item) }"
          :title="`${item.label}: ${item.hint}`"
          @click="closeSidebar"
        >
          <span class="ui-shell-link-icon" aria-hidden="true">{{ item.icon }}</span>
          <span class="ui-shell-link-copy">
            <span class="ui-shell-link-label">{{ item.label }}</span>
            <span class="ui-shell-link-hint">{{ item.hint }}</span>
          </span>
        </RouterLink>
      </nav>
    </aside>

    <div class="ui-shell-main">
      <header class="ui-shell-header">
        <button
          class="icon-btn ui-shell-icon-btn"
          type="button"
          aria-label="Abrir menu"
          @click="toggleSidebar"
        >
          <span aria-hidden="true">&#9776;</span>
        </button>
        <RouterLink class="ui-shell-header-title-link" to="/">
          <div class="ui-shell-header-title">{{ pageTitle }}</div>
        </RouterLink>
        <div v-if="hasToken" ref="accountMenuRef" class="ui-shell-account-menu">
          <button
            class="ui-shell-account-link"
            type="button"
            :aria-expanded="accountMenuOpen"
            aria-haspopup="menu"
            @click="toggleAccountMenu"
          >
            <span class="ui-shell-account-avatar">{{ accountInitials }}</span>
            <span class="ui-shell-account-info">
              <span class="ui-shell-account-name">{{ accountLabel }}</span>
              <span class="ui-shell-account-meta">
                <span v-if="accountRole">{{ accountRole }}</span>
                <span v-if="accountRole && accountPlan"> | </span>
                <span v-if="accountPlan">{{ accountPlan }}</span>
              </span>
            </span>
          </button>

          <div v-if="accountMenuOpen" class="ui-shell-account-dropdown" role="menu">
            <RouterLink
              class="ui-shell-account-item"
              to="/account"
              role="menuitem"
              @click="closeAccountMenu"
            >
              Perfil
            </RouterLink>
            <RouterLink
              class="ui-shell-account-item"
              to="/data"
              role="menuitem"
              @click="closeAccountMenu"
            >
              Settings
            </RouterLink>
            <button
              class="ui-shell-account-item ui-shell-account-item-btn"
              type="button"
              role="menuitem"
              @click="logout"
            >
              Cerrar sesion
            </button>
          </div>
        </div>
      </header>

      <main class="ui-shell-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.ui-shell {
  position: relative;
  min-height: 100vh;
}

.ui-shell-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(3, 7, 16, 0.72);
  backdrop-filter: blur(2px);
  z-index: 30;
}

.ui-shell-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 40;
  height: 100vh;
  width: min(320px, calc(100vw - 24px));
  border-right: 1px solid rgba(255, 255, 255, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015)),
    rgba(8, 12, 22, 0.96);
  backdrop-filter: blur(12px);
  padding: 20px 14px;
  transform: translateX(-102%);
  transition: transform 0.22s ease-out;
  box-shadow: 10px 0 28px rgba(0, 0, 0, 0.4);
}

.ui-shell-sidebar-open {
  transform: translateX(0);
}

.ui-shell-sidebar-top {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ui-shell-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ui-shell-brand-mark {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid rgba(45, 212, 191, 0.55);
  background: rgba(45, 212, 191, 0.16);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.ui-shell-brand-text {
  display: grid;
  line-height: 1.1;
}

.ui-shell-brand-text strong {
  font-size: 13px;
}

.ui-shell-brand-text span {
  font-size: 11px;
  color: var(--muted);
}

.ui-shell-nav {
  display: grid;
  gap: 9px;
}

.ui-shell-nav-section {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 2px 2px 4px;
}

.ui-shell-link {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 10px 10px;
  color: var(--text);
  text-decoration: none;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
}

.ui-shell-link:hover {
  border-color: rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.04);
  transform: translateX(2px);
}

.ui-shell-link-active {
  border-color: rgba(45, 212, 191, 0.7);
  background: rgba(45, 212, 191, 0.08);
  box-shadow: inset 0 0 0 1px rgba(45, 212, 191, 0.16);
}

.ui-shell-link-icon {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.88);
}

.ui-shell-link-copy {
  display: grid;
  line-height: 1.1;
}

.ui-shell-link-label {
  font-size: 14px;
  font-weight: 600;
}

.ui-shell-link-hint {
  font-size: 12px;
  color: var(--muted);
}

.ui-shell-main {
  min-width: 0;
}

.ui-shell-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 16px 24px;
  background: rgba(11, 13, 18, 0.72);
  backdrop-filter: blur(7px);
}

.ui-shell-icon-btn {
  width: 36px;
  height: 36px;
}

.ui-shell-header-title {
  font-size: 18px;
  font-weight: 600;
}

.ui-shell-header-title-link {
  color: inherit;
  text-decoration: none;
}

.ui-shell-account-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  cursor: pointer;
  color: var(--text);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  padding: 4px 10px 4px 4px;
}

.ui-shell-account-avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  background: rgba(45, 212, 191, 0.2);
  border: 1px solid rgba(45, 212, 191, 0.55);
}

.ui-shell-account-info {
  display: grid;
  justify-items: start;
  line-height: 1.1;
}

.ui-shell-account-name {
  font-size: 13px;
  font-weight: 600;
}

.ui-shell-account-meta {
  font-size: 11px;
  color: var(--muted);
}

.ui-shell-account-menu {
  position: relative;
}

.ui-shell-account-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 170px;
  border: 1px solid rgba(45, 212, 191, 0.45);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(45, 212, 191, 0.08), rgba(45, 212, 191, 0.02)),
    rgba(8, 12, 22, 0.96);
  box-shadow:
    0 16px 32px rgba(0, 0, 0, 0.35),
    inset 0 0 0 1px rgba(45, 212, 191, 0.14);
  padding: 6px;
  z-index: 30;
}

.ui-shell-account-item {
  display: block;
  width: 100%;
  text-align: left;
  border-radius: 9px;
  padding: 9px 10px;
  color: var(--text);
  text-decoration: none;
  font-size: 13px;
}

.ui-shell-account-item-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.ui-shell-account-item:hover {
  background: rgba(45, 212, 191, 0.12);
}

.ui-shell-content {
  min-width: 0;
}

@media (max-width: 900px) {
  .ui-shell-header {
    grid-template-columns: auto minmax(0, 1fr) auto;
    padding: 12px;
  }

  .ui-shell-account-link {
    padding-right: 8px;
  }

  .ui-shell-account-meta {
    display: none;
  }
}
</style>
