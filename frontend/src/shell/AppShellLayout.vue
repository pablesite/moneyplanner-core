<script setup lang="ts">
import type { ComponentPublicInstance } from 'vue';
import { useAppShell } from './useAppShell';

const {
  accountInitials,
  accountLabel,
  accountMenuOpen,
  accountMenuRef,
  accountPlan,
  accountRole,
  closeAccountMenu,
  closeSidebar,
  hasToken,
  isNavItemActive,
  logout,
  navItems,
  pageTitle,
  sidebarOpen,
  toggleAccountMenu,
  toggleSidebar,
} = useAppShell();
const assignAccountMenuRef = (element: Element | ComponentPublicInstance | null) => {
  accountMenuRef.value = element as HTMLElement | null;
};
</script>

<template>
  <div class="ui-shell">
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
        <div v-if="hasToken" :ref="assignAccountMenuRef" class="ui-shell-account-menu">
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
