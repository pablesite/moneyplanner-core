<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useAccountingPage } from '@/domains/accounting';
import BaseModal from '@/domains/ui/components/BaseModal.vue';

const {
  loading,
  accountCreationLoading,
  accountActivationLoading,
  transactionCreationLoading,
  error,
  successMessage,
  accounts,
  transactions,
  selectedYear,
  selectedMonth,
  yearOptions,
  monthOptions,
  accountTypeOptions,
  manualPositionTypeOptions,
  quickMovementTypeOptions,
  editMovementTypeOptions,
  editAccountOptions,
  editCounterpartyOptions,
  editCounterpartyMissingHint,
  editKindNeedsCounterparty,
  editKindNeedsClassification,
  editCounterpartyLabel,
  editSelectedAccountCurrentBalance,
  editCategoryOptions,
  editSubcategoryOptions,
  activationForm,
  quickEntryForm,
  editTransactionForm,
  activityFilters,
  liquidityAccounts,
  availableManualPositionOptions,
  accountPositionMetaByAccountId,
  accountDisplayName,
  hasAvailableManualPositions,
  annualIncomeOptionsCompatible,
  annualExpenseOptionsCompatible,
  quickEntryNeedsClassification,
  quickCategoryOptions,
  quickSubcategoryOptions,
  transferCounterpartyOptions,
  investmentCounterpartyOptions,
  liabilityCounterpartyOptions,
  debtInterestOptions,
  quickEntryReady,
  editEntryReady,
  summaryRows,
  filteredTransactions,
  activityKindLabel,
  reloadPeriod,
  activateNetWorthPositions,
  removeNetWorthTracking,
  deleteAccount,
  deleteTransaction,
  openTransactionForEditing,
  submitQuickEntry,
  submitEditedTransaction,
} = useAccountingPage();

function toNumber(raw: string): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(isoDate: string): string {
  const d = new Date(isoDate + 'T00:00:00');
  return new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(d);
}

function formatMoney(value: number, currency = 'EUR'): string {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency,
    minimumFractionDigits: currency === 'EUR' ? 2 : undefined,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCompact(raw: string, currency = 'EUR'): string {
  return formatMoney(toNumber(raw), currency);
}

function monthLabel(month: number): string {
  return (
    monthOptions.find((option) => option.value === month)?.label.slice(0, 3) ??
    String(month).padStart(2, '0')
  );
}

function humanizeKey(value: string): string {
  const normalized = String(value ?? '').trim();
  if (!normalized) return 'Sin clasificar';
  return normalized.replace(/_/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());
}

const accountsByType = computed(() => {
  const groups = new Map<string, typeof accounts.value>();
  accounts.value.forEach((account) => {
    const existing = groups.get(account.account_type) ?? [];
    existing.push(account);
    groups.set(account.account_type, existing);
  });
  return groups;
});
const accountingAssetsTotal = computed(() =>
  (accountsByType.value.get('asset') ?? []).reduce(
    (total, account) => total + toNumber(account.current_balance),
    0,
  ),
);
const accountingLiabilitiesTotal = computed(() =>
  (accountsByType.value.get('liability') ?? []).reduce(
    (total, account) => total + toNumber(account.current_balance),
    0,
  ),
);
const accountingNetBalance = computed(
  () => accountingAssetsTotal.value - accountingLiabilitiesTotal.value,
);
const operationalAccountTypeOptions = computed(() =>
  accountTypeOptions.filter((type) => type.value === 'asset' || type.value === 'liability'),
);
const operationalAccountsCount = computed(() =>
  operationalAccountTypeOptions.value.reduce(
    (total, type) => total + (accountsByType.value.get(type.value)?.length ?? 0),
    0,
  ),
);
const operationalAccounts = computed(() =>
  operationalAccountTypeOptions.value.flatMap((type) => accountsByType.value.get(type.value) ?? []),
);
const technicalAccountTypeOptions = computed(() =>
  accountTypeOptions.filter((type) => type.value !== 'asset' && type.value !== 'liability'),
);
const hasTechnicalAccounts = computed(() =>
  technicalAccountTypeOptions.value.some(
    (type) => (accountsByType.value.get(type.value)?.length ?? 0) > 0,
  ),
);
const hasCompatibleAnnualPlanOptions = computed(() => {
  if (quickEntryForm.movement_type === 'income') {
    return annualIncomeOptionsCompatible.value.length > 0;
  }
  if (
    quickEntryForm.movement_type === 'expense' ||
    quickEntryForm.movement_type === 'debt_payment'
  ) {
    return annualExpenseOptionsCompatible.value.length > 0;
  }
  return false;
});
const selectedOperationalAccountId = computed<number | null>(() => {
  if (activityFilters.accountId === 'all') return null;
  const parsed = Number(activityFilters.accountId);
  return Number.isFinite(parsed) ? parsed : null;
});

function signedEntryImpact(accountType: string, side: 'debit' | 'credit', amount: string): number {
  const value = toNumber(amount);
  if (value === 0) return 0;
  const increasesOnDebit = accountType === 'asset' || accountType === 'expense';
  const increases = increasesOnDebit ? side === 'debit' : side === 'credit';
  return increases ? value : -value;
}

function impactTone(value: number): 'positive' | 'negative' | 'neutral' {
  if (value > 0) return 'positive';
  if (value < 0) return 'negative';
  return 'neutral';
}

function formatSignedMoney(value: number, currency = 'EUR'): string {
  if (value > 0) return `+${formatMoney(value, currency)}`;
  if (value < 0) return `-${formatMoney(Math.abs(value), currency)}`;
  return formatMoney(0, currency);
}

const accountTimelineRows = computed(() => {
  const scopedAccounts = operationalAccounts.value.filter(
    (account) =>
      selectedOperationalAccountId.value == null ||
      account.id === selectedOperationalAccountId.value,
  );
  const rows = scopedAccounts
    .map((account) => {
      const movements = filteredTransactions.value
        .map((transaction) => {
          const impactValue = transaction.entries
            .filter((entry) => entry.account_id === account.id)
            .reduce(
              (total, entry) =>
                total + signedEntryImpact(account.account_type, entry.side, entry.amount),
              0,
            );
          if (impactValue === 0) return null;
          return {
            id: transaction.id,
            booking_date: transaction.booking_date,
            description: transaction.description,
            kind_label: activityKindLabel(transaction),
            origin: transaction.origin,
            status: transaction.status,
            impact_value: impactValue,
            tone: impactTone(impactValue),
          };
        })
        .filter((movement): movement is NonNullable<typeof movement> => movement != null)
        .sort((a, b) => b.booking_date.localeCompare(a.booking_date) || b.id - a.id);
      return {
        account,
        movements,
        movement_count: movements.length,
      };
    })
    .filter((row) => row.movement_count > 0);
  return rows.sort(
    (left, right) =>
      right.movement_count - left.movement_count ||
      accountDisplayName(left.account).localeCompare(accountDisplayName(right.account), 'es'),
  );
});
const groupedAccountTimelineRows = computed(() => {
  const grouped = new Map<
    string,
    {
      positionType: 'asset' | 'liability';
      category: string;
      subgroups: Map<string, typeof accountTimelineRows.value>;
    }
  >();
  accountTimelineRows.value.forEach((row) => {
    const meta = accountPositionMetaByAccountId.value.get(row.account.id);
    const positionType =
      meta?.position_type ?? (row.account.account_type === 'liability' ? 'liability' : 'asset');
    const category = meta?.category ?? 'other';
    const subcategory = meta?.subcategory ?? 'other';
    const categoryKey = `${positionType}:${category}`;
    const categoryBucket = grouped.get(categoryKey) ?? {
      positionType,
      category,
      subgroups: new Map<string, typeof accountTimelineRows.value>(),
    };
    const subRows = categoryBucket.subgroups.get(subcategory) ?? [];
    subRows.push(row);
    categoryBucket.subgroups.set(subcategory, subRows);
    grouped.set(categoryKey, categoryBucket);
  });
  return Array.from(grouped.entries())
    .map(([key, group]) => {
      const subgroups = Array.from(group.subgroups.entries())
        .map(([subcategory, rows]) => ({
          key: `${key}:${subcategory}`,
          subcategory,
          rows: rows
            .slice()
            .sort((a, b) => accountDisplayName(a.account).localeCompare(accountDisplayName(b.account), 'es')),
          accountCount: rows.length,
        }))
        .sort((a, b) => a.subcategory.localeCompare(b.subcategory, 'es'));
      return {
        key,
        positionType: group.positionType,
        category: group.category,
        subgroups,
        accountCount: subgroups.reduce((total, subgroup) => total + subgroup.accountCount, 0),
      };
    })
    .sort((a, b) => {
      const typeOrder = a.positionType === b.positionType ? 0 : a.positionType === 'asset' ? -1 : 1;
      if (typeOrder !== 0) return typeOrder;
      return a.category.localeCompare(b.category, 'es');
    });
});

const showActivationModal = ref(false);
const showEditTransactionModal = ref(false);
const showQuickEntryModal = ref(false);
const activationQuery = ref('');
const activationOperationalOnly = ref(true);
const selectedActivationIds = ref<number[]>([]);
const assetActivationCategoryOrder = ['cash', 'investments', 'real_estate', 'furnishings', 'other'];
const assetActivationCategoryLabels: Record<string, string> = {
  cash: 'Liquidez',
  investments: 'Inversiones',
  real_estate: 'Inmuebles',
  furnishings: 'Mobiliario',
  other: 'Otros',
};
const liabilityActivationCategoryOrder = ['mortgage', 'personal_loan', 'credit_card', 'other'];
const liabilityActivationCategoryLabels: Record<string, string> = {
  mortgage: 'Hipoteca',
  personal_loan: 'Prestamo personal',
  credit_card: 'Tarjeta',
  other: 'Otros',
};
const activationOperationalCategories = new Set(['cash', 'investments']);
const filteredManualPositionOptions = computed(() => {
  const base =
    activationForm.position_type === 'liability'
      ? availableManualPositionOptions.value
      : activationOperationalOnly.value
        ? availableManualPositionOptions.value.filter((position) =>
            activationOperationalCategories.has(String(position.category ?? '').trim()),
          )
        : availableManualPositionOptions.value;
  const query = activationQuery.value.trim().toLowerCase();
  if (!query) return base;
  return base.filter((position) =>
    `${position.name} ${position.currency}`.toLowerCase().includes(query),
  );
});
const activationExcludedByOperationalFilter = computed(() => {
  if (activationForm.position_type === 'liability') return 0;
  if (!activationOperationalOnly.value) return 0;
  return Math.max(
    availableManualPositionOptions.value.length - filteredManualPositionOptions.value.length,
    0,
  );
});
const groupedManualPositionOptions = computed(() => {
  const groups = new Map<string, typeof filteredManualPositionOptions.value>();
  filteredManualPositionOptions.value.forEach((position) => {
    const key = String(position.category ?? 'other').trim() || 'other';
    const existing = groups.get(key) ?? [];
    existing.push(position);
    groups.set(key, existing);
  });
  const order =
    activationForm.position_type === 'asset'
      ? assetActivationCategoryOrder
      : liabilityActivationCategoryOrder;
  const labels =
    activationForm.position_type === 'asset'
      ? assetActivationCategoryLabels
      : liabilityActivationCategoryLabels;
  const orderedKeys = [
    ...order.filter((key) => groups.has(key)),
    ...Array.from(groups.keys()).filter((key) => !order.includes(key)),
  ];
  return orderedKeys.map((key) => ({
    key,
    label: labels[key] ?? key,
    positions: (groups.get(key) ?? []).slice().sort((a, b) => a.name.localeCompare(b.name, 'es')),
  }));
});
const allFilteredSelected = computed(
  () =>
    filteredManualPositionOptions.value.length > 0 &&
    filteredManualPositionOptions.value.every((position) =>
      selectedActivationIds.value.includes(position.id),
    ),
);

function openActivationModal() {
  selectedActivationIds.value = [];
  activationQuery.value = '';
  activationOperationalOnly.value = true;
  showActivationModal.value = true;
}

function toggleSelectAllFiltered() {
  if (allFilteredSelected.value) {
    const filteredIds = new Set(filteredManualPositionOptions.value.map((position) => position.id));
    selectedActivationIds.value = selectedActivationIds.value.filter((id) => !filteredIds.has(id));
    return;
  }
  const merged = new Set(selectedActivationIds.value);
  filteredManualPositionOptions.value.forEach((position) => merged.add(position.id));
  selectedActivationIds.value = Array.from(merged);
}

async function activatePositionFromModal() {
  if (!selectedActivationIds.value.length) return;
  await activateNetWorthPositions(
    activationForm.position_type,
    selectedActivationIds.value.map((id) => Number(id)),
  );
  selectedActivationIds.value = [];
  activationQuery.value = '';
  showActivationModal.value = false;
}

async function submitQuickEntryFromModal() {
  await submitQuickEntry();
  showQuickEntryModal.value = false;
}

function openEditTransactionModal(transactionId: number) {
  if (openTransactionForEditing(transactionId)) {
    showEditTransactionModal.value = true;
  }
}

async function submitEditedTransactionFromModal() {
  const saved = await submitEditedTransaction();
  if (saved) {
    showEditTransactionModal.value = false;
  }
}

async function deleteTransactionFromTimeline(transactionId: number, description: string) {
  await deleteTransaction(transactionId, description);
}

watch(availableManualPositionOptions, (options) => {
  const optionIds = new Set(options.map((option) => option.id));
  selectedActivationIds.value = selectedActivationIds.value.filter((id) => optionIds.has(id));
});
</script>

<template>
  <div class="container ui-page-shell">
    <!-- ── Hero: period selector + KPIs + monthly cashflow ── -->
    <section class="ui-section-card ui-accounting-hero-panel">
      <div class="ui-page-head">
        <div>
          <p class="ui-page-eyebrow">Accounting Movements</p>
          <h1 class="ui-accounting-hero-title">Libro diario operativo</h1>
        </div>
        <div class="ui-accounting-hero-right">
          <div class="ui-period-bar ui-accounting-period-bar">
            <label class="ui-period-field">
              <span>Ejercicio</span>
              <select v-model="selectedYear" class="select ui-period-select" @change="reloadPeriod">
                <option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option>
              </select>
            </label>
            <label class="ui-period-field">
              <span>Mes</span>
              <select
                v-model="selectedMonth"
                class="select ui-period-select"
                @change="reloadPeriod"
              >
                <option v-for="month in monthOptions" :key="month.value" :value="month.value">
                  {{ month.label }}
                </option>
              </select>
            </label>
          </div>
          <div class="ui-page-actions">
            <button
              class="btn"
              type="button"
              aria-label="Activar tracking contable"
              title="Activar tracking contable"
              :disabled="!hasAvailableManualPositions"
              @click="openActivationModal"
            >
              Activar tracking
            </button>
            <button
              class="btn btn-primary ui-accounting-cta"
              type="button"
              aria-label="Registrar movimiento diario"
              title="Registrar movimiento diario"
              :disabled="!liquidityAccounts.length"
              @click="showQuickEntryModal = true"
            >
              + Registrar movimiento
            </button>
          </div>
        </div>
      </div>

      <!-- KPI strip -->
      <div class="ui-kpi-strip">
        <div class="ui-kpi-card ui-kpi-card-primary">
          <span class="ui-kpi-label">Saldo neto contable</span>
          <strong class="ui-kpi-value">{{ formatMoney(accountingNetBalance) }}</strong>
          <p class="ui-kpi-meta">Activo contable - Pasivo contable</p>
        </div>
        <div class="ui-kpi-card">
          <span class="ui-kpi-label">Activos</span>
          <strong class="ui-kpi-value">{{ formatMoney(accountingAssetsTotal) }}</strong>
          <p class="ui-kpi-meta">
            {{ (accountsByType.get('asset') ?? []).length }} cuentas
          </p>
        </div>
        <div class="ui-kpi-card">
          <span class="ui-kpi-label">Pasivos</span>
          <strong class="ui-kpi-value">{{ formatMoney(accountingLiabilitiesTotal) }}</strong>
          <p class="ui-kpi-meta">
            {{ (accountsByType.get('liability') ?? []).length }} cuentas
          </p>
        </div>
      </div>

      <!-- Monthly cashflow strip -->
      <div v-if="summaryRows.length" class="ui-cashflow-strip">
        <div
          v-for="row in summaryRows"
          :key="row.month"
          class="ui-cashflow-month"
          :class="{ 'ui-cashflow-month-active': row.month === selectedMonth }"
        >
          <span class="ui-cashflow-month-label">{{ monthLabel(row.month) }}</span>
          <strong
            class="ui-cashflow-month-value"
            :class="
              row.incomeValue - row.expenseValue >= 0 ? 'ui-cashflow-positive' : 'ui-cashflow-negative'
            "
          >
            {{ formatMoney(row.incomeValue - row.expenseValue) }}
          </strong>
          <small class="ui-cashflow-month-meta">
            I {{ formatMoney(row.incomeValue) }} / G {{ formatMoney(row.expenseValue) }}
          </small>
        </div>
      </div>

      <p class="ui-page-lead">
        Este saldo solo incluye cuentas contables activas en esta vista. No incluye vivienda,
        mobiliario u otros activos fuera del ledger.
      </p>

      <div v-if="error" class="ui-state-block ui-state-error">{{ error }}</div>
      <div v-if="successMessage" class="ui-state-block ui-state-success">{{ successMessage }}</div>
    </section>


    <!-- ── Ledger: filters + account / movement timeline ── -->
    <section class="ui-section-card ui-accounting-ledger-panel">
      <div class="ui-section-head">
        <div class="ui-section-copy">
          <h2 class="ui-section-title">Cuentas + historico por cuenta</h2>
          <p class="ui-section-subtitle">
            {{ monthOptions.find((m) => m.value === selectedMonth)?.label ?? '' }}
            {{ selectedYear }}
            &middot; {{ filteredTransactions.length }} movimientos
            &middot; {{ operationalAccountsCount }} cuentas activas
          </p>
        </div>
      </div>

      <!-- Filters -->
      <div class="ui-action-bar">
        <input
          v-model="activityFilters.query"
          class="input ui-accounting-filter-input"
          placeholder="Filtrar por texto o cuenta"
        />
        <select v-model="activityFilters.accountId" class="select ui-accounting-filter-select">
          <option value="all">Todas las cuentas</option>
          <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
            {{ accountDisplayName(account) }}
          </option>
        </select>
        <select v-model="activityFilters.kind" class="select ui-accounting-filter-select">
          <option value="all">Todos los movimientos</option>
          <option value="income">Solo ingresos</option>
          <option value="expense">Solo gastos</option>
          <option value="transfer">Solo transferencias</option>
          <option value="investment_purchase">Solo compras de inversion</option>
          <option value="debt_payment">Solo pagos de deuda</option>
        </select>
      </div>

      <!-- States -->
      <div v-if="loading && !transactions.length" class="ui-state-block ui-state-loading">
        Cargando movimientos del periodo...
      </div>
      <div v-else-if="!accountTimelineRows.length" class="ui-state-block ui-state-empty">
        Sin cuentas operativas para el periodo seleccionado.
      </div>

      <!-- Account groups — 2-level: category → account (subcategory as label) -->
      <div v-else class="ui-ledger-groups">
        <details
          v-for="categoryGroup in groupedAccountTimelineRows"
          :key="categoryGroup.key"
          class="ui-ledger-category"
          open
        >
          <summary class="ui-ledger-category-summary">
            <strong>
              {{
                `${categoryGroup.positionType === 'asset' ? 'Activo' : 'Pasivo'} / ${humanizeKey(categoryGroup.category)}`
              }}
            </strong>
            <span class="ui-pro-chip">{{ categoryGroup.accountCount }} cuentas</span>
          </summary>

          <template v-for="subcategoryGroup in categoryGroup.subgroups" :key="subcategoryGroup.key">
            <div
              v-if="categoryGroup.subgroups.length > 1"
              class="ui-ledger-subcategory-label"
            >
              {{ humanizeKey(subcategoryGroup.subcategory) }}
            </div>

            <details
              v-for="row in subcategoryGroup.rows"
              :key="row.account.id"
              class="ui-ledger-account ui-accounting-account-timeline"
            >
              <summary class="ui-ledger-account-summary">
                <div class="ui-ledger-account-meta">
                  <strong class="ui-ledger-account-name">{{ accountDisplayName(row.account) }}</strong>
                  <div class="ui-action-bar ui-ledger-account-chips">
                    <span class="ui-pro-chip">{{ row.account.currency }}</span>
                  </div>
                </div>
                <div class="ui-ledger-account-info">
                  <span class="ui-ledger-movs-count">{{ row.movement_count }} mov.</span>
                  <strong class="ui-ledger-account-balance">
                    {{ formatCompact(row.account.current_balance, row.account.currency) }}
                  </strong>
                  <button
                    v-if="row.account.asset_id != null || row.account.liability_id != null"
                    class="icon-btn"
                    type="button"
                    title="Quitar tracking de patrimonio"
                    aria-label="Quitar tracking de patrimonio"
                    :disabled="accountActivationLoading || accountCreationLoading"
                    @click.stop.prevent="removeNetWorthTracking(row.account)"
                  >
                    &#128279;
                  </button>
                  <button
                    v-if="row.account.origin === 'user'"
                    class="icon-btn"
                    type="button"
                    title="Eliminar cuenta"
                    aria-label="Eliminar cuenta"
                    :disabled="accountCreationLoading"
                    @click.stop.prevent="
                      deleteAccount(row.account.id, accountDisplayName(row.account))
                    "
                  >
                    &#128465;&#65039;
                  </button>
                </div>
              </summary>

              <div class="ui-ledger-account-body">
                <div
                  v-if="!row.movements.length"
                  class="ui-state-block ui-state-empty ui-ledger-empty"
                >
                  Sin movimientos para esta cuenta en los filtros actuales.
                </div>
                <ul v-else class="ui-entry-list">
                  <li
                    v-for="movement in row.movements"
                    :key="`${row.account.id}-${movement.id}`"
                    class="ui-entry-row"
                  >
                    <span class="ui-entry-date">{{ formatDate(movement.booking_date) }}</span>
                    <div class="ui-entry-body">
                      <strong class="ui-entry-desc">{{ movement.description }}</strong>
                      <div class="ui-action-bar ui-entry-tags">
                        <span :class="`ui-type-badge ui-type-badge-${movement.tone}`">
                          {{ movement.kind_label }}
                        </span>
                        <span class="ui-entry-status">
                          {{ movement.status === 'posted' ? '●' : '○' }}
                          {{ movement.origin !== 'system' ? movement.origin : '' }}
                        </span>
                      </div>
                    </div>
                    <span
                      class="ui-accounting-balance-delta"
                      :class="`ui-accounting-balance-delta-${movement.tone}`"
                    >
                      {{ formatSignedMoney(movement.impact_value, row.account.currency) }}
                    </span>
                    <div class="ui-entry-actions">
                      <button
                        v-if="movement.origin !== 'system'"
                        class="icon-btn ui-accounting-entry-action-btn"
                        type="button"
                        title="Editar movimiento"
                        aria-label="Editar movimiento"
                        :disabled="transactionCreationLoading"
                        @click="openEditTransactionModal(movement.id)"
                      >
                        &#9998;&#65039;
                      </button>
                      <button
                        v-if="movement.origin !== 'system'"
                        class="icon-btn ui-accounting-entry-action-btn"
                        type="button"
                        title="Eliminar movimiento"
                        aria-label="Eliminar movimiento"
                        :disabled="transactionCreationLoading"
                        @click="deleteTransactionFromTimeline(movement.id, movement.description)"
                      >
                        &#128465;&#65039;
                      </button>
                    </div>
                  </li>
                </ul>
              </div>
            </details>
          </template>
        </details>
      </div>

      <!-- Technical / system accounts -->
      <details v-if="hasTechnicalAccounts" class="ui-ledger-technical">
        <summary>Contrapartidas tecnicas del sistema</summary>
        <p class="ui-page-lead">
          Estas cuentas siguen existiendo por compatibilidad interna, pero no forman parte del
          catalogo operativo que se gestiona manualmente.
        </p>
        <section
          v-for="type in technicalAccountTypeOptions"
          :key="type.value"
          class="ui-ledger-technical-group"
        >
          <div class="ui-section-head ui-ledger-technical-head">
            <strong>{{ type.label }}</strong>
            <span class="ui-pro-chip">{{ accountsByType.get(type.value)?.length ?? 0 }}</span>
          </div>
          <ul
            v-if="(accountsByType.get(type.value)?.length ?? 0) > 0"
            class="ui-entry-list"
          >
            <li
              v-for="account in accountsByType.get(type.value)"
              :key="account.id"
              class="ui-entry-row"
            >
              <div class="ui-ledger-account-meta ui-ledger-account-meta-stretch">
                <strong>{{ account.name }}</strong>
                <div class="ui-action-bar ui-ledger-account-chips">
                  <span class="ui-pro-chip">{{ account.currency }}</span>
                  <span class="ui-pro-chip">{{ account.origin }}</span>
                </div>
              </div>
              <div class="ui-ledger-account-info">
                <span>{{ formatCompact(account.current_balance, account.currency) }}</span>
                <button
                  v-if="account.asset_id != null || account.liability_id != null"
                  class="icon-btn"
                  type="button"
                  title="Quitar tracking"
                  :disabled="accountActivationLoading || accountCreationLoading"
                  @click="removeNetWorthTracking(account)"
                >
                  &#128279;
                </button>
                <button
                  v-if="account.origin === 'user'"
                  class="icon-btn"
                  type="button"
                  title="Eliminar cuenta"
                  :disabled="accountCreationLoading"
                  @click="deleteAccount(account.id, account.name)"
                >
                  &#128465;&#65039;
                </button>
              </div>
            </li>
          </ul>
        </section>
      </details>
    </section>

    <BaseModal
      :open="showActivationModal"
      title="Activar tracking contable"
      @close="showActivationModal = false"
    >
      <form
        class="ui-accounting-form ui-accounting-modal-form"
        @submit.prevent="activatePositionFromModal"
      >
        <p class="subtle">
          Selecciona una o varias posiciones manuales del patrimonio para activar su seguimiento
          contable en el ledger. Core generara automaticamente el saldo de apertura.
        </p>

        <div class="ui-accounting-form-grid">
          <select v-model="activationForm.position_type" class="select">
            <option v-for="type in manualPositionTypeOptions" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
          <input
            v-model="activationQuery"
            class="input"
            type="search"
            placeholder="Buscar posicion por nombre o divisa"
            :disabled="!availableManualPositionOptions.length"
          />
        </div>
        <label v-if="activationForm.position_type === 'asset'" class="ui-accounting-inline-note">
          <input v-model="activationOperationalOnly" type="checkbox" />
          Mostrar solo activos operativos recomendados (liquidez e inversiones)
        </label>
        <p
          v-if="
            activationExcludedByOperationalFilter > 0 && activationForm.position_type === 'asset'
          "
          class="ui-accounting-inline-note"
        >
          Se han ocultado {{ activationExcludedByOperationalFilter }} activos no operativos (ej:
          vivienda/mobiliario). Desactiva el filtro para verlos.
        </p>

        <div v-if="availableManualPositionOptions.length" class="ui-accounting-inline-actions">
          <p class="ui-accounting-inline-note">{{ selectedActivationIds.length }} seleccionadas</p>
          <button class="btn" type="button" @click="toggleSelectAllFiltered">
            {{ allFilteredSelected ? 'Quitar seleccion visible' : 'Seleccionar visibles' }}
          </button>
        </div>

        <div v-if="groupedManualPositionOptions.length" class="ui-accounting-activation-list">
          <div v-for="group in groupedManualPositionOptions" :key="group.key">
            <p class="ui-accounting-inline-note">
              <strong>{{ group.label }}</strong>
            </p>
            <label
              v-for="position in group.positions"
              :key="position.id"
              class="ui-accounting-activation-option"
            >
              <input
                v-model="selectedActivationIds"
                class="ui-accounting-activation-checkbox"
                type="checkbox"
                :value="position.id"
              />
              <span class="ui-accounting-activation-meta">
                <strong>{{ position.name }}</strong>
                <small>{{ position.currency }}</small>
              </span>
            </label>
          </div>
        </div>
        <div
          v-else-if="availableManualPositionOptions.length && activationQuery.trim()"
          class="ui-accounting-empty"
        >
          No hay coincidencias para la busqueda actual.
        </div>

        <div v-if="!hasAvailableManualPositions" class="ui-accounting-empty">
          No hay activos ni pasivos manuales disponibles para activar desde esta vista.
        </div>
        <p v-else class="ui-accounting-inline-note">
          Al activar una posicion, Core la vincula al ledger y genera automaticamente el saldo de
          apertura contra patrimonio neto contable.
        </p>

        <div class="ui-accounting-submit-row">
          <p class="ui-accounting-inline-note">
            Solo se muestran posiciones del patrimonio con `tracking_mode=manual`.
          </p>
          <button
            class="btn btn-primary"
            type="submit"
            :disabled="accountActivationLoading || !selectedActivationIds.length"
          >
            {{
              accountActivationLoading
                ? 'Activando...'
                : `Activar tracking (${selectedActivationIds.length})`
            }}
          </button>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :open="showEditTransactionModal"
      title="Editar movimiento"
      panel-class="max-w-[760px]"
      @close="showEditTransactionModal = false"
    >
      <div class="ui-accounting-modal-copy">
        <p class="ui-page-eyebrow">Edicion</p>
        <p class="subtle">
          Ajusta tipo, cuenta, fechas e importe manteniendo el asiento balanceado y coherente.
        </p>
      </div>
      <form
        class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form ui-accounting-edit-form"
        @submit.prevent="submitEditedTransactionFromModal"
      >
        <div class="ui-accounting-segmented">
          <button
            v-for="option in editMovementTypeOptions"
            :key="option.value"
            type="button"
            class="btn ui-accounting-segmented-btn"
            :class="{
              'ui-accounting-segmented-btn-active': editTransactionForm.kind === option.value,
            }"
            @click="editTransactionForm.kind = option.value"
          >
            {{ option.label }}
          </button>
        </div>

        <input
          v-model="editTransactionForm.description"
          class="input"
          placeholder="Nomina marzo, compra semanal, mover a ahorro..."
          required
        />
        <div class="ui-accounting-form-grid ui-accounting-form-grid-dates">
          <label class="ui-accounting-field">
            <span>Fecha contabilizacion</span>
            <input v-model="editTransactionForm.booking_date" type="date" class="input" required />
          </label>
          <label class="ui-accounting-field">
            <span>Fecha valor</span>
            <input v-model="editTransactionForm.value_date" type="date" class="input" required />
          </label>
          <label class="ui-accounting-field">
            <span>Hora</span>
            <input v-model="editTransactionForm.booking_time" type="time" class="input" />
          </label>
        </div>

        <div
          class="ui-accounting-form-grid"
          :class="editKindNeedsCounterparty ? 'ui-accounting-form-grid-wide' : 'ui-accounting-form-grid-edit-simple'"
        >
          <select v-model="editTransactionForm.account_id" class="select" required>
            <option :value="null" disabled>Cuenta principal</option>
            <option v-for="account in editAccountOptions" :key="account.id" :value="account.id">
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>

          <input
            v-model="editTransactionForm.amount"
            class="input"
            inputmode="decimal"
            :placeholder="
              editTransactionForm.kind === 'balance_adjustment' ? 'Saldo objetivo' : '0.00'
            "
            required
          />

          <select
            v-if="editKindNeedsCounterparty"
            v-model="editTransactionForm.counterparty_account_id"
            class="select"
            required
          >
            <option :value="null">{{ editCounterpartyLabel }}</option>
            <option
              v-for="account in editCounterpartyOptions"
              :key="account.id"
              :value="account.id"
            >
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>
        </div>
        <p
          v-if="editKindNeedsCounterparty && !editCounterpartyOptions.length"
          class="ui-accounting-inline-note"
        >
          {{ editCounterpartyMissingHint }}
        </p>
        <p v-else-if="editKindNeedsClassification" class="ui-accounting-inline-note">
          Selecciona categoria y subcategoria debajo.
        </p>
        <p v-else-if="editTransactionForm.kind !== 'balance_adjustment'" class="ui-accounting-inline-note">
          No requiere contracuenta manual para este tipo.
        </p>

        <div
          v-if="editKindNeedsClassification"
          class="ui-accounting-form-grid ui-accounting-form-grid-wide"
        >
          <select v-model="editTransactionForm.category_key" class="select" required>
            <option value="">Categoria</option>
            <option v-for="option in editCategoryOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <select v-model="editTransactionForm.subcategory_key" class="select" required>
            <option value="">Subcategoria</option>
            <option
              v-for="option in editSubcategoryOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </div>

        <p
          v-if="editTransactionForm.kind === 'balance_adjustment'"
          class="ui-accounting-inline-note"
        >
          Saldo actual de la cuenta:
          <strong>
            {{
              editSelectedAccountCurrentBalance != null
                ? formatCompact(editSelectedAccountCurrentBalance, editTransactionForm.currency)
                : '-'
            }}
          </strong>
          . Se registrara un asiento de ajuste por la diferencia.
        </p>

        <label class="ui-accounting-field">
          <span>Notas</span>
          <textarea
            v-model="editTransactionForm.notes"
            class="textarea"
            rows="2"
            placeholder="Nota opcional para el movimiento"
          />
        </label>

        <div class="ui-accounting-submit-row">
          <p class="subtle">
            {{
              editTransactionForm.kind === 'balance_adjustment'
                ? 'Ajuste: fija el saldo actual de la cuenta al valor objetivo sin tocar otros movimientos.'
                : 'Se mantiene el asiento balanceado y se actualizan tipo, cuenta, clasificacion e importe.'
            }}
          </p>
          <button
            class="btn btn-primary"
            type="submit"
            :disabled="transactionCreationLoading || !editEntryReady"
          >
            {{ transactionCreationLoading ? 'Guardando...' : 'Guardar cambios' }}
          </button>
        </div>
        <p v-if="!editEntryReady && !transactionCreationLoading" class="ui-accounting-inline-note">
          Completa descripcion, fechas, importe y cuenta principal. Segun el tipo tambien puede
          requerir contracuenta y clasificacion.
        </p>
      </form>
    </BaseModal>

    <BaseModal
      :open="showQuickEntryModal"
      title="Registrar movimiento diario"
      panel-class="max-w-[920px]"
      @close="showQuickEntryModal = false"
    >
      <div class="ui-accounting-modal-copy">
        <p class="ui-page-eyebrow">Alta rapida</p>
        <p class="subtle">
          La fecha de contabilizacion manda en el libro y la fecha valor indica cuando impacta
          realmente en saldo.
        </p>
      </div>

      <div v-if="!liquidityAccounts.length" class="ui-accounting-inline-note">
        Necesitas al menos una cuenta de liquidez para registrar movimientos de alta rapida.
      </div>

      <form
        class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form"
        @submit.prevent="submitQuickEntryFromModal"
      >
        <div class="ui-accounting-segmented">
          <button
            v-for="option in quickMovementTypeOptions"
            :key="option.value"
            type="button"
            class="btn ui-accounting-segmented-btn"
            :class="{
              'ui-accounting-segmented-btn-active': quickEntryForm.movement_type === option.value,
            }"
            @click="quickEntryForm.movement_type = option.value"
          >
            {{ option.label }}
          </button>
        </div>

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <input
            v-model="quickEntryForm.description"
            class="input"
            placeholder="Nomina marzo, compra semanal, mover a ahorro..."
            required
          />

          <label class="ui-accounting-field">
            <span>Fecha contabilizacion</span>
            <input v-model="quickEntryForm.booking_date" type="date" class="input" required />
          </label>

          <label class="ui-accounting-field">
            <span>Fecha valor</span>
            <input v-model="quickEntryForm.value_date" type="date" class="input" required />
          </label>
        </div>

        <p class="ui-accounting-inline-note">
          Normalmente coinciden. Si el banco liquida despues, usa una fecha valor posterior.
        </p>

        <div
          class="ui-accounting-form-grid"
          :class="
            quickEntryForm.movement_type === 'transfer' ||
            quickEntryForm.movement_type === 'investment_purchase' ||
            quickEntryForm.movement_type === 'debt_payment'
              ? 'ui-accounting-form-grid-wide'
              : 'ui-accounting-form-grid-edit-simple'
          "
        >
          <select v-model="quickEntryForm.account_id" class="select" required>
            <option :value="null">Cuenta de liquidez</option>
            <option v-for="account in liquidityAccounts" :key="account.id" :value="account.id">
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>

          <input
            v-model="quickEntryForm.amount"
            class="input"
            inputmode="decimal"
            placeholder="0.00"
            required
          />

          <select
            v-if="quickEntryForm.movement_type === 'transfer'"
            v-model="quickEntryForm.counterparty_account_id"
            class="select"
            required
          >
            <option :value="null">Cuenta destino</option>
            <option
              v-for="account in transferCounterpartyOptions"
              :key="account.id"
              :value="account.id"
            >
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>

          <select
            v-else-if="quickEntryForm.movement_type === 'investment_purchase'"
            v-model="quickEntryForm.counterparty_account_id"
            class="select"
            required
          >
            <option :value="null">Cuenta de inversion</option>
            <option
              v-for="account in investmentCounterpartyOptions"
              :key="account.id"
              :value="account.id"
            >
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>

          <select
            v-else-if="quickEntryForm.movement_type === 'debt_payment'"
            v-model="quickEntryForm.liability_account_id"
            class="select"
            required
          >
            <option :value="null">Cuenta de pasivo</option>
            <option
              v-for="account in liabilityCounterpartyOptions"
              :key="account.id"
              :value="account.id"
            >
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>
        </div>

        <div
          v-if="quickEntryNeedsClassification"
          class="ui-accounting-form-grid ui-accounting-form-grid-wide"
        >
          <select v-model="quickEntryForm.category_key" class="select" required>
            <option value="">Categoria</option>
            <option
              v-for="category in quickCategoryOptions"
              :key="category.value"
              :value="category.value"
            >
              {{ category.label }}
            </option>
          </select>

          <select v-model="quickEntryForm.subcategory_key" class="select" required>
            <option value="">Subcategoria</option>
            <option
              v-for="subcategory in quickSubcategoryOptions"
              :key="subcategory.value"
              :value="subcategory.value"
            >
              {{ subcategory.label }}
            </option>
          </select>
        </div>

        <details
          v-if="quickEntryNeedsClassification"
          class="ui-accounting-annual-link"
          :open="
            quickEntryForm.annual_income_entry_id != null ||
            quickEntryForm.annual_expense_entry_id != null
          "
        >
          <summary>
            {{
              hasCompatibleAnnualPlanOptions
                ? 'Alinear con una linea del plan (opcional)'
                : 'Sin lineas anuales compatibles para esta clasificacion'
            }}
          </summary>
          <p class="ui-accounting-inline-note">
            Usa este enlace solo si quieres relacionar el movimiento con una fila concreta del
            presupuesto anual. La clasificacion principal ya queda guardada en el ledger.
          </p>

          <select
            v-if="quickEntryForm.movement_type === 'income'"
            v-model="quickEntryForm.annual_income_entry_id"
            class="select"
            :disabled="!annualIncomeOptionsCompatible.length"
          >
            <option :value="null">Sin vincular al plan anual</option>
            <option
              v-for="entry in annualIncomeOptionsCompatible"
              :key="entry.id"
              :value="entry.id"
            >
              {{ entry.name }}
            </option>
          </select>

          <select
            v-else
            v-model="quickEntryForm.annual_expense_entry_id"
            class="select"
            :disabled="!annualExpenseOptionsCompatible.length"
          >
            <option :value="null">Sin vincular al plan anual</option>
            <option
              v-for="entry in annualExpenseOptionsCompatible"
              :key="entry.id"
              :value="entry.id"
            >
              {{ entry.name }}
            </option>
          </select>
        </details>

        <div
          v-if="quickEntryForm.movement_type === 'debt_payment'"
          class="ui-accounting-form-grid ui-accounting-form-grid-wide"
        >
          <input
            v-model="quickEntryForm.principal_amount"
            class="input"
            inputmode="decimal"
            placeholder="Principal (ej: 300.00)"
            required
          />
          <input
            v-model="quickEntryForm.interest_amount"
            class="input"
            inputmode="decimal"
            placeholder="Interes (ej: 30.00, 0 si no aplica)"
            required
          />
          <select v-model="quickEntryForm.interest_account_id" class="select">
            <option :value="null">Cuenta de gasto por intereses (si aplica)</option>
            <option v-for="account in debtInterestOptions" :key="account.id" :value="account.id">
              {{ account.name }} / {{ account.currency }}
            </option>
          </select>
        </div>

        <textarea
          v-model="quickEntryForm.notes"
          class="textarea"
          rows="2"
          placeholder="Nota opcional para el movimiento"
        />

        <div class="ui-accounting-submit-row">
          <p class="subtle">
            {{
              quickEntryForm.movement_type === 'transfer'
                ? 'La transferencia crea un asiento balanceado entre dos cuentas de liquidez.'
                : quickEntryForm.movement_type === 'investment_purchase'
                  ? 'La compra registra salida de liquidez y alta en la cuenta de inversion.'
                  : quickEntryForm.movement_type === 'debt_payment'
                    ? 'El pago separa principal e intereses; total = principal + interes.'
                    : 'El backend genera la contrapartida contable y registra categoria/subcategoria como clasificacion primaria.'
            }}
          </p>
          <button
            class="btn btn-primary"
            type="submit"
            :disabled="transactionCreationLoading || !quickEntryReady"
          >
            {{ transactionCreationLoading ? 'Guardando...' : 'Registrar movimiento rapido' }}
          </button>
        </div>

        <p v-if="!quickEntryReady && !transactionCreationLoading" class="ui-accounting-inline-note">
          Completa descripcion, fechas, importe y cuenta de liquidez. Cada tipo puede requerir
          cuentas, clasificacion funcional y desglose adicionales.
        </p>
      </form>
    </BaseModal>
  </div>
</template>

<style scoped>
/* ── Hero panel ──────────────────────────────────────────────── */
.ui-accounting-hero-panel {
  display: grid;
  gap: 20px;
  padding: 20px;
}

.ui-accounting-hero-title {
  margin: 4px 0 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

/* Right cluster: period bar stacked above action buttons, right-aligned */
.ui-accounting-hero-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .ui-accounting-hero-right {
    align-items: flex-start;
    width: 100%;
  }
}

/* Period selector — compact context indicator, not an action */
.ui-period-bar {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-md);
  padding: 8px 12px;
}

.ui-accounting-period-bar {
  padding: 6px 10px;
  background: transparent;
  border-color: rgba(255, 255, 255, 0.06);
}

.ui-period-field {
  display: grid;
  gap: 4px;
  font-size: 0.72rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ui-period-select {
  min-width: 120px;
  height: 38px;
  padding-top: 0;
  padding-bottom: 0;
  background: transparent;
  border-color: rgba(255, 255, 255, 0.1);
}

/* Primary CTA — more visual weight than secondary actions */
.ui-accounting-cta {
  padding: 10px 22px;
  font-size: 0.94rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

/* Net balance hero number — larger than the shared kpi-value */
.ui-accounting-hero-panel .ui-kpi-card-primary .ui-kpi-value {
  font-size: 2rem;
}

/* Force 12-month cashflow in one row — override shared minmax(88px) */
.ui-accounting-hero-panel .ui-cashflow-strip {
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

/* Active month highlight in cashflow strip */
.ui-cashflow-month-active {
  border-color: rgba(45, 212, 191, 0.32);
  background: rgba(45, 212, 191, 0.07);
}

/* ── Ledger panel ────────────────────────────────────────────── */
.ui-accounting-ledger-panel {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.ui-accounting-filter-input {
  min-width: 200px;
  flex: 1;
  width: auto;
}

.ui-accounting-filter-select {
  min-width: 160px;
  width: auto;
  flex: 1;
}

/* ── Ledger accordion — category level ──────────────────────── */
.ui-ledger-groups {
  display: grid;
  gap: 10px;
}

.ui-ledger-category {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.ui-ledger-category-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  list-style: none;
}

.ui-ledger-category-summary::-webkit-details-marker {
  display: none;
}

/* ── Subcategory label (non-interactive divider) ─────────────── */
.ui-ledger-subcategory-label {
  padding: 6px 16px;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.01);
}

/* ── Account level ───────────────────────────────────────────── */
.ui-ledger-account {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* Alias kept for test compatibility */
.ui-accounting-account-timeline {
  background: rgba(255, 255, 255, 0.015);
}

.ui-ledger-account-summary {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  list-style: none;
}

.ui-ledger-account-summary::-webkit-details-marker {
  display: none;
}

.ui-ledger-account-meta {
  display: grid;
  gap: 4px;
}

.ui-ledger-account-meta-stretch {
  flex: 1;
}

.ui-ledger-account-chips {
  gap: 6px;
}

.ui-ledger-account-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ui-ledger-account-name {
  color: rgba(245, 250, 255, 0.92);
}

.ui-ledger-movs-count {
  font-size: 0.72rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.ui-ledger-account-balance {
  font-size: 0.95rem;
  font-variant-numeric: tabular-nums;
}

.ui-ledger-account-body {
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.ui-ledger-empty {
  margin: 10px;
  font-size: 0.82rem;
  padding: 10px 14px;
}

/* ── Entry list ──────────────────────────────────────────────── */
.ui-entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.ui-entry-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}

.ui-entry-row + .ui-entry-row {
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.ui-entry-row:hover {
  background: rgba(255, 255, 255, 0.025);
}

.ui-entry-date {
  font-size: 0.75rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  line-height: 1.3;
}

.ui-entry-body {
  display: grid;
  gap: 4px;
}

.ui-entry-desc {
  font-size: 0.88rem;
}

.ui-entry-tags {
  gap: 6px;
}

.ui-entry-status {
  font-size: 0.72rem;
  color: var(--muted);
}

.ui-entry-actions {
  display: flex;
  gap: 6px;
}

/* ── Balance delta — kept for test compatibility ─────────────── */
.ui-accounting-balance-delta {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  border: 1px solid transparent;
  white-space: nowrap;
}

.ui-accounting-balance-delta-positive {
  color: #8cf0d0;
  background: rgba(45, 212, 191, 0.1);
  border-color: rgba(45, 212, 191, 0.2);
}

.ui-accounting-balance-delta-negative {
  color: #ffb3b3;
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.2);
}

.ui-accounting-balance-delta-neutral {
  color: rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.1);
}

.ui-accounting-entry-action-btn {
  width: 32px;
  height: 32px;
  min-height: 32px;
  padding: 0;
  font-size: 0.84rem;
}

/* ── Technical accounts ──────────────────────────────────────── */
.ui-ledger-technical {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-lg);
  padding: 12px 16px;
}

.ui-ledger-technical > summary {
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--muted);
}

.ui-ledger-technical-group {
  margin-top: 12px;
}

.ui-ledger-technical-head {
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 4px;
}

/* ── Modal forms ─────────────────────────────────────────────── */
.ui-accounting-form {
  display: grid;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.ui-accounting-form-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}

.ui-accounting-form-head h3 {
  margin: 0;
  font-size: 1rem;
}

.ui-accounting-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.ui-accounting-form-grid-wide {
  grid-template-columns: minmax(0, 2fr) repeat(2, minmax(0, 1fr));
}

.ui-accounting-form-grid-edit-simple {
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
}

/* 3-column row for booking_date + value_date + time in edit modal */
.ui-accounting-form-grid-dates {
  display: grid;
  grid-template-columns: 1fr 1fr 0.75fr;
  gap: 10px;
}

.ui-accounting-field {
  display: grid;
  gap: 6px;
}

.ui-accounting-field span {
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.66);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ui-accounting-inline-note {
  margin: 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.82rem;
}

.ui-accounting-form-grid > .ui-accounting-inline-note,
.ui-accounting-form-grid-wide > .ui-accounting-inline-note {
  align-self: center;
  color: rgba(255, 255, 255, 0.48);
  font-size: 0.76rem;
}

.ui-accounting-edit-readonly {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ui-accounting-edit-readonly div {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 10px;
  display: grid;
  gap: 4px;
}

.ui-accounting-edit-readonly span {
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.62);
}

.ui-accounting-modal-copy {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.ui-accounting-modal-copy .subtle,
.ui-accounting-modal-copy .ui-page-eyebrow {
  margin: 0;
}

.ui-accounting-modal-form {
  padding-top: 0;
  border-top: 0;
}

.ui-accounting-edit-form {
  gap: 14px;
}

.ui-accounting-edit-amount-wrap {
  position: relative;
}

.ui-accounting-edit-amount-wrap small {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(255, 255, 255, 0.64);
  font-size: 0.72rem;
  letter-spacing: 0.04em;
}

.ui-accounting-edit-amount-wrap .input {
  padding-right: 56px;
}

/* Segmented movement type selector — full-width tabs, no wrapping */
.ui-accounting-segmented {
  display: flex;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
}

.ui-accounting-segmented .ui-accounting-segmented-btn {
  flex: 1;
  min-width: 0;
  border: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0;
  background: transparent;
  padding: 10px 8px;
  font-size: 0.82rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transform: none;
}

.ui-accounting-segmented .ui-accounting-segmented-btn:last-child {
  border-right: none;
}

.ui-accounting-segmented .ui-accounting-segmented-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: transparent;
  border-right-color: rgba(255, 255, 255, 0.08);
  transform: none;
}

.ui-accounting-segmented .ui-accounting-segmented-btn.ui-accounting-segmented-btn-active {
  background: rgba(45, 212, 191, 0.1);
  color: rgba(45, 212, 191, 0.95);
  font-weight: 600;
}

.ui-accounting-annual-link {
  display: grid;
  gap: 10px;
  border-radius: 14px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
}

.ui-accounting-annual-link summary {
  cursor: pointer;
  color: rgba(255, 255, 255, 0.82);
  font-size: 0.84rem;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ui-accounting-annual-link summary::-webkit-details-marker {
  display: none;
}

.ui-accounting-annual-link summary::before {
  content: '›';
  display: inline-block;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--muted);
  transition: transform 0.18s;
  flex-shrink: 0;
}

.ui-accounting-annual-link[open] summary::before {
  transform: rotate(90deg);
}

.ui-accounting-activation-list {
  max-height: 280px;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
}

.ui-accounting-activation-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
}

.ui-accounting-activation-option + .ui-accounting-activation-option {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.ui-accounting-activation-checkbox {
  width: 16px;
  height: 16px;
}

.ui-accounting-activation-meta {
  display: grid;
  gap: 2px;
}

.ui-accounting-activation-meta small {
  color: rgba(255, 255, 255, 0.64);
  font-size: 0.76rem;
}

.ui-accounting-inline-actions,
.ui-accounting-submit-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.ui-accounting-entry-editor-row {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) repeat(4, minmax(0, 1fr)) auto;
  gap: 10px;
}

.ui-accounting-advanced {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 12px;
}

.ui-accounting-advanced-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.86);
  font-size: 0.84rem;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 900px) {
  .ui-period-bar {
    flex-wrap: wrap;
  }

  .ui-accounting-hero-right {
    align-items: flex-start;
  }

  .ui-accounting-hero-panel .ui-cashflow-strip {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .ui-entry-row {
    grid-template-columns: 44px minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
  }

  .ui-entry-actions {
    grid-column: 3;
    grid-row: 1 / span 2;
    align-self: center;
  }
}

@media (max-width: 720px) {
  .ui-accounting-form-grid,
  .ui-accounting-form-grid-wide,
  .ui-accounting-form-grid-edit-simple,
  .ui-accounting-form-grid-dates,
  .ui-accounting-entry-editor-row {
    grid-template-columns: 1fr;
  }

  .ui-accounting-edit-readonly {
    grid-template-columns: 1fr;
  }

  .ui-accounting-advanced-summary {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
