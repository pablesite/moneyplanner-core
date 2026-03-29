<script setup lang="ts">
/* eslint-disable vue/no-mutating-props */
import { computed, ref, watch, type PropType } from 'vue';
import BaseModal from '@/domains/ui/components/BaseModal.vue';

const props = defineProps({
  page: {
    type: Object as PropType<any>,
    required: true,
  },
});

type AccountOption = {
  id: number;
  name: string;
  currency: string;
  account_type?: string;
  asset_id?: number | null;
  liability_id?: number | null;
  display_name?: string;
};

type AccountGroup = {
  key: string;
  label: string;
  accounts: AccountOption[];
};

function accountTypeLabel(accountType?: string): string {
  if (accountType === 'asset') return 'Activos';
  if (accountType === 'liability') return 'Pasivos';
  if (accountType === 'equity') return 'Patrimonio neto';
  if (accountType === 'income') return 'Ingresos';
  if (accountType === 'expense') return 'Gastos';
  return 'Otras cuentas';
}

function accountLabel(account: AccountOption): string {
  if (typeof props.page.accountDisplayName === 'function') {
    return props.page.accountDisplayName(account);
  }
  return account.display_name || account.name;
}

function groupAndSortAccounts(accounts: AccountOption[]): AccountGroup[] {
  const order = ['asset', 'liability', 'equity', 'income', 'expense', 'other'];
  const groups = new Map<string, AccountOption[]>();

  for (const account of accounts) {
    const key = account.account_type ?? 'other';
    const existing = groups.get(key) ?? [];
    existing.push(account);
    groups.set(key, existing);
  }

  return Array.from(groups.entries())
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([key, grouped]) => ({
      key,
      label: accountTypeLabel(key),
      accounts: grouped
        .slice()
        .sort((left, right) =>
          accountLabel(left).localeCompare(accountLabel(right), 'es', { sensitivity: 'base' }),
        ),
    }));
}

const liquidityGroups = computed(() => groupAndSortAccounts(props.page.liquidityAccounts));
const revaluationGroups = computed(() =>
  groupAndSortAccounts(props.page.revaluationAccountOptions),
);
const transferGroups = computed(() => groupAndSortAccounts(props.page.transferCounterpartyOptions));
const adjustmentGroups = computed(() =>
  groupAndSortAccounts(props.page.quickAdjustmentAccountOptions),
);
const investmentGroups = computed(() =>
  groupAndSortAccounts(props.page.investmentCounterpartyOptions),
);
const liabilityGroups = computed(() =>
  groupAndSortAccounts(props.page.liabilityCounterpartyOptions),
);
const interestGroups = computed(() => groupAndSortAccounts(props.page.debtInterestOptions));

type MovementTypeOption = { value: string; label: string };
const commonTypeOptions = computed<MovementTypeOption[]>(() =>
  (props.page.quickMovementTypeOptions as MovementTypeOption[]).slice(0, 2),
);
const advancedTypeOptions = computed<MovementTypeOption[]>(() =>
  (props.page.quickMovementTypeOptions as MovementTypeOption[]).slice(2),
);

const showValueDate = ref(false);

watch(
  () => props.page.quickEntryForm.booking_date,
  (date: string) => {
    if (!showValueDate.value) {
      props.page.quickEntryForm.value_date = date;
    }
  },
);

watch(showValueDate, (show: boolean) => {
  if (!show) {
    props.page.quickEntryForm.value_date = props.page.quickEntryForm.booking_date;
  }
});
</script>

<template>
  <BaseModal
    :open="page.showQuickEntryModal"
    title="Registrar movimiento diario"
    panel-class="max-w-[920px]"
    @close="page.showQuickEntryModal = false"
  >
    <div v-if="!page.liquidityAccounts.length" class="ui-accounting-inline-note">
      Necesitas al menos una cuenta de liquidez para registrar movimientos.
    </div>

    <form
      class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form"
      @submit.prevent="page.submitQuickEntryFromModal"
    >
      <div class="ui-accounting-segmented">
        <button
          v-for="option in commonTypeOptions"
          :key="option.value"
          type="button"
          class="btn ui-accounting-segmented-btn"
          :class="{
            'ui-accounting-segmented-btn-active':
              page.quickEntryForm.movement_type === option.value,
          }"
          @click="page.quickEntryForm.movement_type = option.value"
        >
          {{ option.label }}
        </button>
        <div class="ui-accounting-segmented-divider" aria-hidden="true" />
        <button
          v-for="option in advancedTypeOptions"
          :key="option.value"
          type="button"
          class="btn ui-accounting-segmented-btn ui-accounting-segmented-btn-advanced"
          :class="{
            'ui-accounting-segmented-btn-active':
              page.quickEntryForm.movement_type === option.value,
          }"
          @click="page.quickEntryForm.movement_type = option.value"
        >
          {{ option.label }}
        </button>
      </div>

      <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
        <label class="ui-accounting-field">
          <span>Descripción</span>
          <input
            v-model="page.quickEntryForm.description"
            class="input"
            placeholder="Nomina marzo, compra semanal, mover a ahorro..."
            required
          />
        </label>

        <label class="ui-accounting-field">
          <span>Titularidad</span>
          <select v-model="page.quickEntryForm.ownership_id" class="select">
            <option
              v-for="option in page.ownershipOptions"
              :key="option.value == null ? 'none' : option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="ui-accounting-field">
          <span>Fecha contabilización</span>
          <input v-model="page.quickEntryForm.booking_date" type="date" class="input" required />
        </label>
      </div>

      <div class="ui-accounting-value-date-row">
        <button
          v-if="!showValueDate"
          type="button"
          class="ui-accounting-value-date-toggle"
          @click="showValueDate = true"
        >
          Fecha valor diferente
        </button>
        <label v-else class="ui-accounting-field">
          <span>Fecha valor</span>
          <div class="ui-accounting-value-date-input-row">
            <input
              v-model="page.quickEntryForm.value_date"
              type="date"
              class="input"
              required
            />
            <button
              type="button"
              class="ui-accounting-value-date-close"
              @click="showValueDate = false"
            >
              Misma fecha
            </button>
          </div>
        </label>
      </div>

      <template v-if="page.quickEntryForm.movement_type === 'revaluation'">
        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <select v-model="page.quickEntryForm.account_id" class="select" required>
            <option :value="null">Cuenta de inversion</option>
            <optgroup v-for="group in revaluationGroups" :key="group.key" :label="group.label">
              <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                {{ page.accountDisplayName(account) }} / {{ account.currency }}
              </option>
            </optgroup>
          </select>

          <input
            v-model="page.quickEntryForm.revaluation_new_value"
            class="input"
            inputmode="decimal"
            placeholder="Nuevo valor total del activo"
            required
          />
        </div>

        <p class="ui-accounting-balance-feedback">
          <template v-if="page.revaluationCurrentBalance != null">
            Saldo actual:
            <strong>{{ page.revaluationCurrentBalance.toFixed(2) }}</strong>.
            <template v-if="page.revaluationDelta != null">
              Revalorización:
              <strong
                :class="
                  page.revaluationDelta > 0
                    ? 'ui-accounting-tone-positive'
                    : page.revaluationDelta < 0
                      ? 'ui-accounting-tone-negative'
                      : ''
                "
              >
                {{ page.revaluationDelta >= 0 ? '+' : '' }}{{ page.revaluationDelta.toFixed(2) }}
              </strong>
            </template>
          </template>
          <template v-else>Selecciona la cuenta de inversión para ver el saldo actual.</template>
        </p>
      </template>

      <template v-else-if="page.quickEntryForm.movement_type === 'investment'">
        <div class="ui-accounting-segmented">
          <button
            type="button"
            class="ui-accounting-segmented-btn"
            :class="{ 'ui-accounting-segmented-btn-active': page.quickEntryForm.investment_direction === 'inflow' }"
            @click="page.quickEntryForm.investment_direction = 'inflow'"
          >
            Aporte
          </button>
          <button
            type="button"
            class="ui-accounting-segmented-btn"
            :class="{ 'ui-accounting-segmented-btn-active': page.quickEntryForm.investment_direction === 'outflow' }"
            @click="page.quickEntryForm.investment_direction = 'outflow'"
          >
            Retirada
          </button>
        </div>

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <label class="ui-accounting-field">
            <span>Cuenta de liquidez {{ page.quickEntryForm.investment_direction === 'inflow' ? '(origen)' : '(destino)' }}</span>
            <select v-model="page.quickEntryForm.account_id" class="select" required>
              <option :value="null">Seleccionar</option>
              <optgroup v-for="group in liquidityGroups" :key="group.key" :label="group.label">
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
          <label class="ui-accounting-field">
            <span>Cuenta de inversión {{ page.quickEntryForm.investment_direction === 'inflow' ? '(destino)' : '(origen)' }}</span>
            <select v-model="page.quickEntryForm.counterparty_account_id" class="select" required>
              <option :value="null">Seleccionar</option>
              <optgroup v-for="group in investmentGroups" :key="group.key" :label="group.label">
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
        </div>

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <input
            v-model="page.quickEntryForm.amount"
            class="input"
            inputmode="decimal"
            :placeholder="`Importe${page.quickInvestmentOriginCurrency ? ` (${page.quickInvestmentOriginCurrency})` : ''}`"
            required
          />
          <input
            v-if="page.quickInvestmentIsCrossCurrency"
            v-model="page.quickEntryForm.destination_amount"
            class="input"
            inputmode="decimal"
            :placeholder="`Importe destino (${page.quickInvestmentDestinationCurrency || 'moneda destino'})`"
            required
          />
          <template v-if="page.quickEntryForm.investment_direction === 'outflow'">
            <input
              v-model="page.quickEntryForm.realized_cost_basis"
              class="input"
              inputmode="decimal"
              placeholder="Coste de adquisición (opcional)"
            />
            <input
              v-model="page.quickEntryForm.realized_gain_loss"
              class="input"
              inputmode="decimal"
              placeholder="Ganancia/pérdida realizada (opcional)"
            />
          </template>
        </div>
      </template>

      <div
        v-else
        class="ui-accounting-form-grid"
        :class="
          page.quickEntryForm.movement_type === 'transfer' ||
          page.quickEntryForm.movement_type === 'debt_payment'
            ? 'ui-accounting-form-grid-wide'
            : 'ui-accounting-form-grid-edit-simple'
        "
      >
        <select v-model="page.quickEntryForm.account_id" class="select" required>
          <option :value="null">
            {{
              page.quickEntryForm.movement_type === 'adjustment'
                ? 'Cuenta a conciliar'
                : 'Cuenta de liquidez'
            }}
          </option>
          <optgroup
            v-for="group in
            page.quickEntryForm.movement_type === 'adjustment' ? adjustmentGroups : liquidityGroups"
            :key="group.key"
            :label="group.label"
          >
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>

        <input
          v-model="page.quickEntryForm.amount"
          class="input"
          inputmode="decimal"
          :placeholder="
            page.quickEntryForm.movement_type === 'adjustment'
              ? 'Saldo final objetivo'
              : '0.00'
          "
          required
        />

        <select
          v-if="page.quickEntryForm.movement_type === 'transfer'"
          v-model="page.quickEntryForm.counterparty_account_id"
          class="select"
          required
        >
          <option :value="null">Cuenta destino</option>
          <optgroup v-for="group in transferGroups" :key="group.key" :label="group.label">
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>

        <select
          v-else-if="page.quickEntryForm.movement_type === 'debt_payment'"
          v-model="page.quickEntryForm.liability_account_id"
          class="select"
          required
        >
          <option :value="null">Cuenta de pasivo</option>
          <optgroup v-for="group in liabilityGroups" :key="group.key" :label="group.label">
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>
      </div>
      <p v-if="page.quickEntryForm.movement_type === 'adjustment'" class="ui-accounting-balance-feedback">
        <template v-if="page.quickAdjustmentCurrentBalance != null">
          Saldo actual:
          <strong>{{ page.quickAdjustmentCurrentBalance.toFixed(page.quickAdjustmentDisplayDecimals) }}</strong
          >.
          <template v-if="page.quickAdjustmentDelta != null">
            Ajuste calculado:
            <strong
              :class="
                page.quickAdjustmentDelta > 0
                  ? 'ui-accounting-tone-positive'
                  : page.quickAdjustmentDelta < 0
                    ? 'ui-accounting-tone-negative'
                    : ''
              "
            >
              {{ page.quickAdjustmentDelta >= 0 ? '+' : '' }}{{ page.quickAdjustmentDelta.toFixed(page.quickAdjustmentDisplayDecimals) }}
            </strong>
          </template>
        </template>
        <template v-else>
          Selecciona la cuenta y el saldo final objetivo para calcular el ajuste automáticamente.
        </template>
      </p>

      <div
        v-if="page.quickEntryNeedsClassification"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <label class="ui-accounting-field">
          <span>Categoría</span>
          <select
            v-model="page.quickEntryForm.category_key"
            class="select"
            :disabled="page.quickCategoryLocked"
            required
          >
            <option value="">Seleccionar</option>
            <option
              v-for="category in page.quickCategoryOptions"
              :key="category.value"
              :value="category.value"
            >
              {{ category.label }}
            </option>
          </select>
        </label>

        <label class="ui-accounting-field">
          <span>Subcategoría</span>
          <select
            v-model="page.quickEntryForm.subcategory_key"
            class="select"
            :disabled="page.quickSubcategoryLocked"
            required
          >
            <option value="">Seleccionar</option>
            <option
              v-for="subcategory in page.quickSubcategoryOptions"
              :key="subcategory.value"
              :value="subcategory.value"
            >
              {{ subcategory.label }}
            </option>
          </select>
        </label>
      </div>

      <details
        v-if="page.quickEntryNeedsClassification && page.hasCompatibleAnnualPlanOptions"
        class="ui-accounting-annual-link"
        :open="
          page.quickEntryForm.annual_income_entry_id != null ||
          page.quickEntryForm.annual_expense_entry_id != null
        "
      >
        <summary>Alinear con una línea del plan (opcional)</summary>
        <p class="ui-accounting-inline-note">
          Usa este enlace solo si quieres relacionar el movimiento con una fila concreta del
          presupuesto anual. La clasificación principal ya queda guardada en el ledger.
        </p>

        <select
          v-if="page.quickEntryForm.movement_type === 'income'"
          v-model="page.quickEntryForm.annual_income_entry_id"
          class="select"
        >
          <option :value="null">Sin vincular al plan anual</option>
          <option
            v-for="entry in page.annualIncomeOptionsCompatible"
            :key="entry.id"
            :value="entry.id"
          >
            {{ entry.name }}
          </option>
        </select>

        <select
          v-else
          v-model="page.quickEntryForm.annual_expense_entry_id"
          class="select"
        >
          <option :value="null">Sin vincular al plan anual</option>
          <option
            v-for="entry in page.annualExpenseOptionsCompatible"
            :key="entry.id"
            :value="entry.id"
          >
            {{ entry.name }}
          </option>
        </select>
      </details>

      <div
        v-if="page.quickEntryForm.movement_type === 'debt_payment'"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <input
          v-model="page.quickEntryForm.principal_amount"
          class="input"
          inputmode="decimal"
          placeholder="Principal (ej: 300.00)"
          required
        />
        <input
          v-model="page.quickEntryForm.interest_amount"
          class="input"
          inputmode="decimal"
          placeholder="Interés (ej: 30.00, 0 si no aplica)"
          required
        />
        <select v-model="page.quickEntryForm.interest_account_id" class="select">
          <option :value="null">Cuenta de gasto por intereses (si aplica)</option>
          <optgroup v-for="group in interestGroups" :key="group.key" :label="group.label">
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>
      </div>

      <textarea
        v-model="page.quickEntryForm.notes"
        class="textarea"
        rows="2"
        placeholder="Nota opcional para el movimiento"
      />

      <p
        v-if="!page.quickEntryReady && !page.transactionCreationLoading"
        class="ui-accounting-inline-note"
      >
        Completa descripción, fechas, importe y cuenta. Algunos tipos requieren campos adicionales.
      </p>

      <div class="ui-accounting-submit-row">
        <p class="subtle">
          {{
            page.quickEntryForm.movement_type === 'transfer'
              ? 'Crea un asiento balanceado entre dos cuentas de liquidez.'
              : page.quickEntryForm.movement_type === 'investment'
                ? page.quickInvestmentIsCrossCurrency
                  ? 'Inversión multimoneda: informa importe origen e importe destino según ejecución real.'
                  : page.quickEntryForm.investment_direction === 'outflow'
                  ? 'La desinversión devuelve liquidez al activo de caja.'
                  : 'El aporte registra el alta en la cuenta de inversión.'
                : page.quickEntryForm.movement_type === 'debt_payment'
                  ? 'El pago separa principal e intereses. Total = principal + intereses.'
                  : 'Las partidas contables se generan automáticamente.'
          }}
        </p>
        <button
          class="btn btn-primary"
          type="submit"
          :disabled="page.transactionCreationLoading || !page.quickEntryReady"
        >
          {{ page.transactionCreationLoading ? 'Guardando...' : 'Registrar movimiento' }}
        </button>
      </div>
    </form>
  </BaseModal>
</template>
