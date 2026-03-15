<script setup lang="ts">
import { computed } from 'vue';
import { useAccountingPage } from '@/domains/accounting';

const {
  loading,
  accountCreationLoading,
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
  accountForm,
  transactionForm,
  debitTotal,
  creditTotal,
  transactionBalanced,
  summaryRows,
  addEntry,
  removeEntry,
  reloadPeriod,
  submitAccount,
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
</script>

<template>
  <div class="container ui-pro-page ui-accounting-page">
    <section class="card ui-pro-panel ui-accounting-hero">
      <div class="ui-accounting-hero-copy">
        <p class="ui-pro-kicker">Accounting movements</p>
        <h1 class="h1 ui-accounting-title">Libro diario operativo</h1>
        <p class="subtle ui-accounting-subtitle">
          Primera entrega del dominio contable: cuentas, asientos balanceados y lectura mensual para
          preparar la integracion futura con presupuesto y patrimonio.
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
          <span class="ui-accounting-pill">{{ accounts.length }} activas</span>
        </div>

        <div class="ui-accounting-account-groups">
          <section
            v-for="type in accountTypeOptions"
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
                <div>
                  <strong>{{ account.name }}</strong>
                  <p>{{ account.currency }} · {{ account.origin }}</p>
                </div>
                <span>{{ formatCompact(account.current_balance, account.currency) }}</span>
              </li>
            </ul>
          </section>
        </div>

        <form class="ui-accounting-form" @submit.prevent="submitAccount">
          <div class="ui-accounting-form-head">
            <h3>Nueva cuenta</h3>
            <span class="subtle">Base operativa para tracking contable</span>
          </div>

          <div class="ui-accounting-form-grid">
            <input
              v-model="accountForm.name"
              class="input"
              placeholder="Cuenta corriente, gastos hogar, ingresos salariales..."
              required
            />
            <select v-model="accountForm.account_type" class="select">
              <option v-for="type in accountTypeOptions" :key="type.value" :value="type.value">
                {{ type.label }}
              </option>
            </select>
            <input v-model="accountForm.currency" class="input" maxlength="3" placeholder="EUR" />
          </div>

          <textarea
            v-model="accountForm.notes"
            class="textarea"
            rows="2"
            placeholder="Notas operativas opcionales"
          />

          <button class="btn btn-primary" type="submit" :disabled="accountCreationLoading">
            {{ accountCreationLoading ? 'Creando...' : 'Crear cuenta' }}
          </button>
        </form>
      </article>

      <article class="card ui-pro-panel ui-accounting-panel">
        <div class="ui-accounting-panel-head">
          <div>
            <p class="ui-accounting-panel-kicker">Actividad</p>
            <h2 class="h2">Asientos del periodo</h2>
          </div>
          <span class="ui-accounting-pill">{{ transactions.length }} movimientos</span>
        </div>

        <div class="ui-accounting-summary-strip">
          <div v-for="row in summaryRows" :key="row.month" class="ui-accounting-summary-month">
            <span>{{ monthLabel(row.month) }}</span>
            <strong>{{ formatMoney(row.incomeValue - row.expenseValue) }}</strong>
            <small>
              I {{ formatMoney(row.incomeValue) }} · G {{ formatMoney(row.expenseValue) }}
            </small>
          </div>
        </div>

        <div v-if="!transactions.length && !loading" class="ui-accounting-empty">
          No hay movimientos para el periodo seleccionado.
        </div>

        <div v-else class="ui-accounting-transaction-list">
          <article
            v-for="transaction in transactions"
            :key="transaction.id"
            class="ui-accounting-transaction"
          >
            <div class="ui-accounting-transaction-head">
              <div>
                <strong>{{ transaction.description }}</strong>
                <p>
                  {{ transaction.booking_date }} · {{ transaction.status }} ·
                  {{ transaction.origin }}
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
      </article>
    </section>

    <section class="card ui-pro-panel ui-accounting-panel">
      <div class="ui-accounting-panel-head">
        <div>
          <p class="ui-accounting-panel-kicker">Alta rapida</p>
          <h2 class="h2">Registrar movimiento balanceado</h2>
        </div>
        <span
          class="ui-accounting-balance-pill"
          :class="{ 'ui-accounting-balance-pill-ok': transactionBalanced }"
        >
          Debe {{ formatMoney(debitTotal) }} · Haber {{ formatMoney(creditTotal) }}
        </span>
      </div>

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
                {{ account.name }} · {{ account.currency }}
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
            {{ transactionCreationLoading ? 'Guardando...' : 'Registrar movimiento' }}
          </button>
        </div>
      </form>
    </section>
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

.ui-accounting-panel-kicker {
  margin: 0 0 4px;
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.62);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.ui-accounting-pill,
.ui-accounting-balance-pill {
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

.ui-accounting-balance-pill-ok {
  border-color: rgba(45, 212, 191, 0.34);
  background: rgba(45, 212, 191, 0.1);
}

.ui-accounting-account-groups {
  display: grid;
  gap: 12px;
}

.ui-accounting-account-group {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
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
.ui-accounting-transaction-head p {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.78rem;
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

.ui-accounting-transaction-list {
  display: grid;
  gap: 10px;
}

.ui-accounting-transaction {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.ui-accounting-transaction-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.ui-accounting-entry-editor {
  display: grid;
  gap: 10px;
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
}

@media (max-width: 720px) {
  .ui-accounting-form-grid,
  .ui-accounting-form-grid-wide,
  .ui-accounting-summary-strip,
  .ui-accounting-entry-editor-row {
    grid-template-columns: 1fr;
  }
}
</style>
