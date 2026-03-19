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
