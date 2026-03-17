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
  accountBalancesSummary,
  selectedYear,
  selectedMonth,
  yearOptions,
  monthOptions,
  accountTypeOptions,
  manualPositionTypeOptions,
  quickMovementTypeOptions,
  activationForm,
  quickEntryForm,
  transactionForm,
  activityFilters,
  liquidityAccounts,
  availableManualPositionOptions,
  hasAvailableManualPositions,
  liquidityBalanceRows,
  liquidityBalanceTotal,
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
  debitTotal,
  creditTotal,
  transactionBalanced,
  summaryRows,
  filteredTransactions,
  addEntry,
  activityKindLabel,
  liquidityBalanceDeltaTone,
  removeEntry,
  reloadPeriod,
  activateNetWorthPositions,
  removeNetWorthTracking,
  deleteAccount,
  submitQuickEntry,
  submitTransaction,
} = useAccountingPage();

function toNumber(raw: string): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(',', '.');
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value: number, currency = 'EUR'): string {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency,
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

const showActivationModal = ref(false);
const showQuickEntryModal = ref(false);
const activationQuery = ref('');
const selectedActivationIds = ref<number[]>([]);
const filteredManualPositionOptions = computed(() => {
  const query = activationQuery.value.trim().toLowerCase();
  if (!query) return availableManualPositionOptions.value;
  return availableManualPositionOptions.value.filter((position) =>
    `${position.name} ${position.currency}`.toLowerCase().includes(query),
  );
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

watch(availableManualPositionOptions, (options) => {
  const optionIds = new Set(options.map((option) => option.id));
  selectedActivationIds.value = selectedActivationIds.value.filter((id) => optionIds.has(id));
});
</script>

<template>
  <div class="container ui-pro-page ui-accounting-page">
    <section class="card ui-pro-panel ui-accounting-hero">
      <div class="ui-accounting-hero-copy">
        <p class="ui-pro-kicker">Accounting movements</p>
        <h1 class="h1 ui-accounting-title">Libro diario operativo</h1>
        <p class="subtle ui-accounting-subtitle">
          Primera entrega del dominio contable: cuentas, entrada rapida de movimientos y lectura
          mensual para preparar la integracion futura con presupuesto y patrimonio.
        </p>
      </div>

      <div class="ui-accounting-filters">
        <label class="ui-accounting-filter">
          <span>Ejercicio</span>
          <select v-model="selectedYear" class="select" @change="reloadPeriod">
            <option v-for="year in yearOptions" :key="year" :value="year">
              {{ year }}
            </option>
          </select>
        </label>

        <label class="ui-accounting-filter">
          <span>Mes</span>
          <select v-model="selectedMonth" class="select" @change="reloadPeriod">
            <option v-for="month in monthOptions" :key="month.value" :value="month.value">
              {{ month.label }}
            </option>
          </select>
        </label>
      </div>
    </section>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="successMessage" class="ui-alert-success">{{ successMessage }}</div>

    <section class="ui-accounting-grid">
      <article class="card ui-pro-panel ui-accounting-panel">
        <div class="ui-accounting-panel-head">
          <div>
            <p class="ui-accounting-panel-kicker">Cuentas</p>
            <h2 class="h2">Catalogo operativo</h2>
          </div>
          <div class="ui-accounting-panel-actions">
            <span class="ui-accounting-pill">{{ operationalAccountsCount }} activas</span>
            <button
              class="icon-btn ui-accounting-panel-add"
              type="button"
              aria-label="Activar tracking contable"
              title="Activar tracking contable"
              :disabled="!hasAvailableManualPositions"
              @click="openActivationModal"
            >
              <span class="icon" aria-hidden="true">+</span>
            </button>
          </div>
        </div>

        <div class="ui-accounting-net-summary">
          <div class="ui-accounting-net-summary-copy">
            <p class="ui-accounting-panel-kicker">Resumen contable</p>
            <h3 class="ui-accounting-net-summary-title">Saldo neto contable</h3>
            <p class="ui-accounting-net-summary-subtitle">Activo contable - Pasivo contable</p>
          </div>
          <div class="ui-accounting-net-summary-values">
            <strong>{{ formatMoney(accountingNetBalance) }}</strong>
            <small>
              Activos {{ formatMoney(accountingAssetsTotal) }} / Pasivos
              {{ formatMoney(accountingLiabilitiesTotal) }}
            </small>
          </div>
        </div>

        <p class="ui-accounting-inline-note">
          Este saldo solo incluye cuentas contables activas en esta vista. No incluye vivienda,
          mobiliario u otros activos fuera del ledger.
        </p>

        <div class="ui-accounting-account-groups">
          <section
            v-for="type in operationalAccountTypeOptions"
            :key="type.value"
            class="ui-accounting-account-group"
          >
            <div class="ui-accounting-account-group-head">
              <strong>{{ type.label }}</strong>
              <span>{{ accountsByType.get(type.value)?.length ?? 0 }}</span>
            </div>

            <div
              v-if="(accountsByType.get(type.value)?.length ?? 0) === 0"
              class="ui-accounting-empty"
            >
              Sin cuentas de este tipo todavia.
            </div>

            <ul v-else class="ui-accounting-account-list">
              <li
                v-for="account in accountsByType.get(type.value)"
                :key="account.id"
                class="ui-accounting-account-row"
              >
                <div class="ui-accounting-account-meta">
                  <strong>{{ account.name }}</strong>
                  <p>{{ account.currency }} / {{ account.origin }}</p>
                </div>
                <div class="ui-accounting-account-actions">
                  <span>{{ formatCompact(account.current_balance, account.currency) }}</span>
                  <button
                    v-if="account.asset_id != null || account.liability_id != null"
                    class="btn ui-accounting-account-untrack-btn"
                    type="button"
                    :disabled="accountActivationLoading || accountCreationLoading"
                    @click="removeNetWorthTracking(account)"
                  >
                    Quitar tracking
                  </button>
                  <button
                    v-if="account.origin === 'user'"
                    class="btn ui-accounting-account-delete-btn"
                    type="button"
                    :disabled="accountCreationLoading"
                    @click="deleteAccount(account.id, account.name)"
                  >
                    Eliminar
                  </button>
                </div>
              </li>
            </ul>
          </section>

          <details v-if="hasTechnicalAccounts" class="ui-accounting-account-legacy">
            <summary>Contrapartidas tecnicas del sistema</summary>
            <p class="ui-accounting-legacy-copy">
              Estas cuentas siguen existiendo por compatibilidad interna, pero no forman parte del
              catalogo operativo que se gestiona manualmente.
            </p>
            <section
              v-for="type in technicalAccountTypeOptions"
              :key="type.value"
              class="ui-accounting-account-group"
            >
              <div class="ui-accounting-account-group-head">
                <strong>{{ type.label }}</strong>
                <span>{{ accountsByType.get(type.value)?.length ?? 0 }}</span>
              </div>

              <ul
                v-if="(accountsByType.get(type.value)?.length ?? 0) > 0"
                class="ui-accounting-account-list"
              >
                <li
                  v-for="account in accountsByType.get(type.value)"
                  :key="account.id"
                  class="ui-accounting-account-row"
                >
                  <div class="ui-accounting-account-meta">
                    <strong>{{ account.name }}</strong>
                    <p>{{ account.currency }} / {{ account.origin }}</p>
                  </div>
                  <div class="ui-accounting-account-actions">
                    <span>{{ formatCompact(account.current_balance, account.currency) }}</span>
                    <button
                      v-if="account.asset_id != null || account.liability_id != null"
                      class="btn ui-accounting-account-untrack-btn"
                      type="button"
                      :disabled="accountActivationLoading || accountCreationLoading"
                      @click="removeNetWorthTracking(account)"
                    >
                      Quitar tracking
                    </button>
                    <button
                      v-if="account.origin === 'user'"
                      class="btn ui-accounting-account-delete-btn"
                      type="button"
                      :disabled="accountCreationLoading"
                      @click="deleteAccount(account.id, account.name)"
                    >
                      Eliminar
                    </button>
                  </div>
                </li>
              </ul>
            </section>
          </details>
        </div>

        <p class="ui-accounting-inline-note">
          Usa el boton <strong>+</strong> para seleccionar posiciones manuales ya existentes y
          pasarlas a tracking contable sin salir del libro diario.
        </p>
      </article>

      <article class="card ui-pro-panel ui-accounting-panel">
        <div class="ui-accounting-panel-head">
          <div>
            <p class="ui-accounting-panel-kicker">Liquidez</p>
            <h2 class="h2">Saldos derivados del ledger</h2>
          </div>
          <div class="ui-accounting-panel-actions">
            <span class="ui-accounting-pill">{{ formatMoney(liquidityBalanceTotal) }}</span>
            <button
              class="icon-btn ui-accounting-panel-add"
              type="button"
              aria-label="Registrar movimiento diario"
              title="Registrar movimiento diario"
              :disabled="!liquidityAccounts.length"
              @click="showQuickEntryModal = true"
            >
              <span class="icon" aria-hidden="true">+</span>
            </button>
          </div>
        </div>

        <p class="ui-accounting-inline-note">
          El alta rapida clasifica primero por categoria y subcategoria. La alineacion con el plan
          anual queda como ayuda secundaria.
        </p>

        <div v-if="loading && !accountBalancesSummary" class="ui-accounting-empty">
          Cargando balances del periodo...
        </div>

        <div v-else-if="!liquidityBalanceRows.length" class="ui-accounting-empty">
          Sin cuentas de liquidez con actividad ledger en el periodo seleccionado.
        </div>

        <div v-else class="ui-accounting-balance-list">
          <article
            v-for="row in liquidityBalanceRows"
            :key="row.account_id"
            class="ui-accounting-balance-card"
          >
            <div class="ui-accounting-balance-card-head">
              <div>
                <strong>{{ row.name }}</strong>
                <p>
                  {{ row.currency }} / saldo actual
                  {{ formatCompact(row.current_balance, row.currency) }}
                </p>
              </div>
              <span
                class="ui-accounting-balance-delta"
                :class="`ui-accounting-balance-delta-${liquidityBalanceDeltaTone(row)}`"
              >
                {{ formatCompact(row.period_net_change, row.currency) }}
              </span>
            </div>

            <dl class="ui-accounting-balance-metrics">
              <div>
                <dt>Entradas</dt>
                <dd>{{ formatCompact(row.period_debit_total, row.currency) }}</dd>
              </div>
              <div>
                <dt>Salidas</dt>
                <dd>{{ formatCompact(row.period_credit_total, row.currency) }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </article>

      <article class="card ui-pro-panel ui-accounting-panel ui-accounting-activity-panel">
        <div class="ui-accounting-panel-head">
          <div>
            <p class="ui-accounting-panel-kicker">Actividad</p>
            <h2 class="h2">Asientos del periodo</h2>
          </div>
          <span class="ui-accounting-pill">{{ filteredTransactions.length }} movimientos</span>
        </div>

        <div class="ui-accounting-form-grid">
          <input
            v-model="activityFilters.query"
            class="input"
            placeholder="Filtrar por texto o cuenta"
          />
          <select v-model="activityFilters.accountId" class="select">
            <option value="all">Todas las cuentas</option>
            <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
              {{ account.name }}
            </option>
          </select>
          <select v-model="activityFilters.kind" class="select">
            <option value="all">Todos los movimientos</option>
            <option value="income">Solo ingresos</option>
            <option value="expense">Solo gastos</option>
            <option value="transfer">Solo transferencias</option>
            <option value="investment_purchase">Solo compras de inversion</option>
            <option value="debt_payment">Solo pagos de deuda</option>
          </select>
        </div>

        <div class="ui-accounting-summary-strip">
          <div v-for="row in summaryRows" :key="row.month" class="ui-accounting-summary-month">
            <span>{{ monthLabel(row.month) }}</span>
            <strong>{{ formatMoney(row.incomeValue - row.expenseValue) }}</strong>
            <small
              >I {{ formatMoney(row.incomeValue) }} / G {{ formatMoney(row.expenseValue) }}</small
            >
          </div>
        </div>

        <div v-if="loading && !transactions.length" class="ui-accounting-empty">
          Cargando movimientos del periodo...
        </div>

        <div v-else-if="!filteredTransactions.length && !loading" class="ui-accounting-empty">
          No hay movimientos para el periodo seleccionado.
        </div>

        <div v-else class="ui-accounting-transaction-list">
          <article
            v-for="transaction in filteredTransactions"
            :key="transaction.id"
            class="ui-accounting-transaction"
          >
            <div class="ui-accounting-transaction-head">
              <div>
                <strong>{{ transaction.description }}</strong>
                <p>
                  {{ transaction.booking_date }} / {{ activityKindLabel(transaction) }} /
                  {{ transaction.status }} / {{ transaction.origin }}
                </p>
              </div>
              <span>{{ transaction.entries.length }} apuntes</span>
            </div>

            <ul class="ui-accounting-entry-list">
              <li
                v-for="entry in transaction.entries"
                :key="entry.id"
                class="ui-accounting-entry-row"
              >
                <div>
                  <strong>{{ entry.account_name }}</strong>
                  <p>{{ entry.side === 'debit' ? 'Debe' : 'Haber' }}</p>
                </div>
                <span>{{ formatCompact(entry.amount, entry.currency) }}</span>
              </li>
            </ul>
          </article>
        </div>

        <details class="ui-accounting-advanced">
          <summary class="ui-accounting-advanced-summary">
            <span>Modo avanzado</span>
            <span>Debe {{ formatMoney(debitTotal) }} / Haber {{ formatMoney(creditTotal) }}</span>
          </summary>

          <form
            class="ui-accounting-form ui-accounting-transaction-form"
            @submit.prevent="submitTransaction"
          >
            <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
              <input
                v-model="transactionForm.description"
                class="input"
                placeholder="Nomina marzo, alquiler abril, transferencia interna..."
                required
              />
              <input v-model="transactionForm.booking_date" type="date" class="input" required />
              <input v-model="transactionForm.value_date" type="date" class="input" required />
            </div>

            <div class="ui-accounting-entry-editor">
              <div
                v-for="entry in transactionForm.entries"
                :key="entry.key"
                class="ui-accounting-entry-editor-row"
              >
                <select v-model="entry.account_id" class="select" required>
                  <option :value="null">Selecciona cuenta</option>
                  <option v-for="account in accounts" :key="account.id" :value="account.id">
                    {{ account.name }} / {{ account.currency }}
                  </option>
                </select>

                <select v-model="entry.side" class="select">
                  <option value="debit">Debe</option>
                  <option value="credit">Haber</option>
                </select>

                <input
                  v-model="entry.amount"
                  class="input"
                  inputmode="decimal"
                  placeholder="0.00"
                  required
                />
                <input
                  v-model="entry.currency"
                  class="input"
                  maxlength="3"
                  placeholder="EUR"
                  required
                />
                <input v-model="entry.notes" class="input" placeholder="Nota opcional" />

                <button
                  class="btn"
                  type="button"
                  :disabled="transactionForm.entries.length <= 2"
                  @click="removeEntry(entry.key)"
                >
                  Quitar
                </button>
              </div>
            </div>

            <div class="ui-accounting-inline-actions">
              <button class="btn" type="button" @click="addEntry('debit')">Anadir debe</button>
              <button class="btn" type="button" @click="addEntry('credit')">Anadir haber</button>
            </div>

            <textarea
              v-model="transactionForm.notes"
              class="textarea"
              rows="2"
              placeholder="Notas generales del movimiento"
            />

            <div class="ui-accounting-submit-row">
              <p class="subtle">
                El guardado exige al menos dos apuntes y balance exacto por moneda, igual que el
                backend.
              </p>
              <button
                class="btn btn-primary"
                type="submit"
                :disabled="transactionCreationLoading || !transactionBalanced"
              >
                {{
                  transactionCreationLoading ? 'Guardando...' : 'Registrar movimiento balanceado'
                }}
              </button>
            </div>

            <p
              v-if="!transactionBalanced && !transactionCreationLoading"
              class="ui-accounting-inline-note"
            >
              El modo avanzado bloquea el guardado hasta que debe y haber coincidan exactamente.
            </p>
          </form>
        </details>
      </article>
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
        <div class="ui-accounting-form-head">
          <h3>Activar tracking contable</h3>
          <span class="subtle">Selecciona una posicion manual ya existente del patrimonio</span>
        </div>

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

        <div v-if="availableManualPositionOptions.length" class="ui-accounting-inline-actions">
          <p class="ui-accounting-inline-note">{{ selectedActivationIds.length }} seleccionadas</p>
          <button class="btn" type="button" @click="toggleSelectAllFiltered">
            {{ allFilteredSelected ? 'Quitar seleccion visible' : 'Seleccionar visibles' }}
          </button>
        </div>

        <div v-if="filteredManualPositionOptions.length" class="ui-accounting-activation-list">
          <label
            v-for="position in filteredManualPositionOptions"
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
      :open="showQuickEntryModal"
      title="Registrar movimiento diario"
      panel-class="max-w-[920px]"
      @close="showQuickEntryModal = false"
    >
      <div class="ui-accounting-modal-copy">
        <p class="ui-accounting-panel-kicker">Alta rapida</p>
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

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
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

          <div
            v-else-if="quickEntryForm.movement_type === 'income'"
            class="ui-accounting-inline-note"
          >
            Selecciona categoria y subcategoria debajo.
          </div>

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

          <div v-else class="ui-accounting-inline-note">
            Selecciona categoria y subcategoria debajo.
          </div>
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
.ui-accounting-page {
  display: grid;
  gap: 18px;
}

.ui-accounting-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  flex-wrap: wrap;
}

.ui-accounting-title {
  margin-bottom: 8px;
}

.ui-accounting-subtitle {
  max-width: 68ch;
}

.ui-accounting-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ui-accounting-filter {
  display: grid;
  gap: 6px;
  min-width: 140px;
}

.ui-accounting-filter span {
  font-size: 0.76rem;
  color: rgba(255, 255, 255, 0.66);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ui-accounting-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.ui-accounting-activity-panel {
  grid-column: 1 / -1;
}

.ui-accounting-panel {
  display: grid;
  gap: 16px;
}

.ui-accounting-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  flex-wrap: wrap;
}

.ui-accounting-panel-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ui-accounting-panel-add {
  flex: 0 0 auto;
}

.ui-accounting-panel-kicker {
  margin: 0 0 4px;
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.62);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.ui-accounting-pill {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.86);
}

.ui-accounting-account-groups {
  display: grid;
  gap: 12px;
}

.ui-accounting-net-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
}

.ui-accounting-net-summary-copy {
  display: grid;
  gap: 2px;
}

.ui-accounting-net-summary-title {
  margin: 0;
  font-size: 1.05rem;
}

.ui-accounting-net-summary-subtitle {
  margin: 0;
  color: rgba(255, 255, 255, 0.64);
  font-size: 0.78rem;
}

.ui-accounting-net-summary-values {
  display: grid;
  justify-items: end;
  gap: 4px;
}

.ui-accounting-net-summary-values strong {
  font-size: 1.25rem;
}

.ui-accounting-net-summary-values small {
  color: rgba(255, 255, 255, 0.64);
  font-size: 0.76rem;
  text-align: right;
}

.ui-accounting-account-group {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.ui-accounting-account-legacy {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.01);
  padding: 10px;
}

.ui-accounting-account-legacy summary {
  cursor: pointer;
  color: rgba(255, 255, 255, 0.74);
  font-size: 0.82rem;
  margin-bottom: 10px;
}

.ui-accounting-legacy-copy {
  margin: 0 0 10px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.78rem;
}

.ui-accounting-account-group-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.ui-accounting-account-list,
.ui-accounting-entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.ui-accounting-account-row,
.ui-accounting-entry-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  padding: 10px 12px;
}

.ui-accounting-account-row + .ui-accounting-account-row,
.ui-accounting-entry-row + .ui-accounting-entry-row {
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.ui-accounting-account-row p,
.ui-accounting-entry-row p,
.ui-accounting-transaction-head p,
.ui-accounting-balance-card-head p {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.78rem;
}

.ui-accounting-account-meta {
  display: grid;
  gap: 2px;
}

.ui-accounting-account-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.ui-accounting-account-delete-btn {
  min-height: 30px;
  padding: 0 10px;
  font-size: 0.74rem;
}

.ui-accounting-account-untrack-btn {
  min-height: 30px;
  padding: 0 10px;
  font-size: 0.74rem;
}

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

.ui-accounting-summary-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}

.ui-accounting-summary-month {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 10px;
  display: grid;
  gap: 3px;
}

.ui-accounting-summary-month span,
.ui-accounting-summary-month small {
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.75rem;
}

.ui-accounting-balance-list,
.ui-accounting-transaction-list {
  display: grid;
  gap: 10px;
}

.ui-accounting-balance-card,
.ui-accounting-transaction {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.ui-accounting-balance-card {
  padding: 12px;
  gap: 10px;
}

.ui-accounting-balance-card-head,
.ui-accounting-transaction-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.ui-accounting-transaction-head {
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.ui-accounting-balance-delta {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  border-radius: 999px;
  padding: 0 10px;
  font-size: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.ui-accounting-balance-delta-positive {
  color: #8cf0d0;
  background: rgba(45, 212, 191, 0.12);
}

.ui-accounting-balance-delta-negative {
  color: #ffb3b3;
  background: rgba(248, 113, 113, 0.14);
}

.ui-accounting-balance-delta-neutral {
  color: rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.04);
}

.ui-accounting-balance-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.ui-accounting-balance-metrics div {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  padding: 10px;
}

.ui-accounting-balance-metrics dt {
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.74rem;
}

.ui-accounting-balance-metrics dd {
  margin: 6px 0 0;
  font-weight: 600;
}

.ui-accounting-entry-editor {
  display: grid;
  gap: 10px;
}

.ui-accounting-segmented {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ui-accounting-segmented-btn {
  min-width: 120px;
}

.ui-accounting-segmented-btn-active {
  border-color: rgba(45, 212, 191, 0.34);
  background: rgba(45, 212, 191, 0.12);
}

.ui-accounting-modal-copy {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.ui-accounting-modal-copy .subtle,
.ui-accounting-modal-copy .ui-accounting-panel-kicker {
  margin: 0;
}

.ui-accounting-modal-form {
  padding-top: 0;
  border-top: 0;
}

.ui-accounting-advanced {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 12px;
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

.ui-accounting-entry-editor-row {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) repeat(4, minmax(0, 1fr)) auto;
  gap: 10px;
}

.ui-accounting-inline-actions,
.ui-accounting-submit-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.ui-accounting-empty {
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.86rem;
}

@media (max-width: 1024px) {
  .ui-accounting-grid {
    grid-template-columns: 1fr;
  }

  .ui-accounting-summary-strip {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .ui-accounting-entry-editor-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ui-accounting-balance-metrics {
    grid-template-columns: 1fr;
  }

  .ui-accounting-net-summary-values {
    justify-items: start;
  }

  .ui-accounting-net-summary-values small {
    text-align: left;
  }
}

@media (max-width: 720px) {
  .ui-accounting-form-grid,
  .ui-accounting-form-grid-wide,
  .ui-accounting-summary-strip,
  .ui-accounting-entry-editor-row {
    grid-template-columns: 1fr;
  }

  .ui-accounting-advanced-summary {
    flex-direction: column;
    align-items: start;
  }
}
</style>
