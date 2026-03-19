// import { defineConfig } from 'vite'
// import vue from '@vitejs/plugin-vue'

// // https://vite.dev/config/
// export default defineConfig({
//   plugins: [vue()],
// })

import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['src/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/**/*.{ts,vue}'],
      exclude: [
        'src/**/*.spec.ts',
        'src/**/__tests__/**',
        'src/main.ts',
        // Legacy/bridge surfaces pending dedicated refactor phases
        'src/App.vue',
        'src/shell/AppShellLayout.vue',
        'src/domains/auth/api.ts',
        'src/domains/auth/guard.ts',
        'src/domains/auth/index.ts',
        'src/domains/auth/components/AppHeader.vue',
        'src/domains/ui/components/BaseModal.vue',
        'src/domains/people/components/OwnershipSplitEditor.vue',
        'src/domains/accounting/api.ts',
        'src/domains/accounting/composables.ts',
        'src/domains/accounting/store.ts',
        'src/domains/accounting/components/*.vue',
        'src/domains/budget/components/*.vue',
        'src/domains/capabilities/index.ts',
        'src/domains/data-input/portableBundle.ts',
        'src/domains/data-input/annualExpenseStore.ts',
        'src/domains/data-input/annualIncomeStore.ts',
        'src/domains/guide/composables.ts',
        'src/domains/aux-data/composables.ts',
        'src/domains/net-worth/composables.ts',
        'src/domains/net-worth/extensions.ts',
        'src/domains/net-worth/store.ts',
        'src/domains/net-worth/useNetWorthTimelineLayout.ts',
        'src/domains/net-worth/useNetWorthPositionActivity.ts',
        'src/domains/net-worth/components/ItemForm.vue',
        'src/domains/net-worth/components/ItemList.vue',
        'src/domains/net-worth/components/NetWorthHeroSection.vue',
        'src/domains/net-worth/components/NetWorthCategoryWorkspace.vue',
        'src/domains/people/composables.ts',
        'src/lib/api.ts',
        'src/shell/useAppShell.ts',
        'src/views/AuxDataView.vue',
        'src/views/GuidePhaseDetailView.vue',
        'src/views/NetWorthView.vue',
        'src/views/AccountingMovementsView.vue',
        'src/views/BudgetDashboardView.vue',
        'src/views/data-input/useDataInputPage.ts',
      ],
      thresholds: {
        statements: 80,
        branches: 80,
        functions: 80,
        lines: 80,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    // Prefer TS/Vue sources over colocated transpiled JS artifacts in src/
    extensions: ['.ts', '.tsx', '.vue', '.js', '.jsx', '.json'],
  },
  server: {
    host: true,
    watch: {
      usePolling: true,
      interval: 100,
    },
  },
});
