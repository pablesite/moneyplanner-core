<script setup lang="ts">
/* eslint-disable vue/no-mutating-props */
import { computed, type PropType } from 'vue';
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
</script>

<template>
  <BaseModal
    :open="page.showQuickEntryModal"
    title="Registrar movimiento diario"
    panel-class="max-w-[920px]"
    @close="page.showQuickEntryModal = false"
  >
    <div class="ui-accounting-modal-copy">
      <p class="ui-page-eyebrow">Alta rapida</p>
      <p class="subtle">
        La fecha de contabilizacion manda en el libro y la fecha valor indica cuando impacta
        realmente en saldo.
      </p>
    </div>

    <div v-if="!page.liquidityAccounts.length" class="ui-accounting-inline-note">
      Necesitas al menos una cuenta de liquidez para registrar movimientos de alta rapida.
    </div>

    <form
      class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form"
      @submit.prevent="page.submitQuickEntryFromModal"
    >
      <div class="ui-accounting-segmented">
        <button
          v-for="option in page.quickMovementTypeOptions"
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
      </div>

      <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
        <input
          v-model="page.quickEntryForm.description"
          class="input"
          placeholder="Nomina marzo, compra semanal, mover a ahorro..."
          required
        />

        <select v-model="page.quickEntryForm.ownership_id" class="select">
          <option
            v-for="option in page.ownershipOptions"
            :key="option.value == null ? 'none' : option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>

        <label class="ui-accounting-field">
          <span>Fecha contabilizacion</span>
          <input v-model="page.quickEntryForm.booking_date" type="date" class="input" required />
        </label>

        <label class="ui-accounting-field">
          <span>Fecha valor</span>
          <input v-model="page.quickEntryForm.value_date" type="date" class="input" required />
        </label>
      </div>

      <p class="ui-accounting-inline-note">
        Normalmente coinciden. Si el banco liquida despues, usa una fecha valor posterior.
      </p>

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

        <p class="ui-accounting-inline-note">
          <template v-if="page.revaluationCurrentBalance != null">
            Saldo actual:
            <strong>{{ page.revaluationCurrentBalance.toFixed(2) }}</strong
            >.
            <template v-if="page.revaluationDelta != null">
              Revalorizacion:
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
          <template v-else> Selecciona la cuenta de inversion para ver el saldo actual. </template>
        </p>
      </template>

      <div
        v-else
        class="ui-accounting-form-grid"
        :class="
          page.quickEntryForm.movement_type === 'transfer' ||
          page.quickEntryForm.movement_type === 'investment' ||
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
              : page.quickEntryForm.movement_type === 'investment'
              ? `Importe origen${page.quickInvestmentOriginCurrency ? ` (${page.quickInvestmentOriginCurrency})` : ''}`
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
          v-else-if="page.quickEntryForm.movement_type === 'investment'"
          v-model="page.quickEntryForm.counterparty_account_id"
          class="select"
          required
        >
          <option :value="null">Cuenta de inversion</option>
          <optgroup v-for="group in investmentGroups" :key="group.key" :label="group.label">
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
      <p v-if="page.quickEntryForm.movement_type === 'adjustment'" class="ui-accounting-inline-note">
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
          Selecciona la cuenta y el saldo final objetivo para calcular el ajuste automaticamente.
        </template>
      </p>
      <div
        v-if="page.quickEntryForm.movement_type === 'investment'"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <select v-model="page.quickEntryForm.investment_direction" class="select">
          <option value="inflow">Aporte (liquidez a inversion)</option>
          <option value="outflow">Retirada inversion (inversion a liquidez)</option>
        </select>
        <input
          v-if="page.quickInvestmentIsCrossCurrency"
          v-model="page.quickEntryForm.destination_amount"
          class="input"
          inputmode="decimal"
          :placeholder="`Importe destino (${page.quickInvestmentDestinationCurrency || 'moneda destino'})`"
          required
        />
        <input
          v-model="page.quickEntryForm.realized_cost_basis"
          class="input"
          inputmode="decimal"
          placeholder="Coste realizado (opcional)"
        />
        <input
          v-model="page.quickEntryForm.realized_gain_loss"
          class="input"
          inputmode="decimal"
          placeholder="Ganancia/perdida realizada (opcional)"
        />
      </div>

      <div
        v-if="page.quickEntryNeedsClassification"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <select
          v-model="page.quickEntryForm.category_key"
          class="select"
          :disabled="page.quickCategoryLocked"
          required
        >
          <option value="">Categoria</option>
          <option
            v-for="category in page.quickCategoryOptions"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
          </option>
        </select>

        <select
          v-model="page.quickEntryForm.subcategory_key"
          class="select"
          :disabled="page.quickSubcategoryLocked"
          required
        >
          <option value="">Subcategoria</option>
          <option
            v-for="subcategory in page.quickSubcategoryOptions"
            :key="subcategory.value"
            :value="subcategory.value"
          >
            {{ subcategory.label }}
          </option>
        </select>
      </div>

      <details
        v-if="page.quickEntryNeedsClassification"
        class="ui-accounting-annual-link"
        :open="
          page.quickEntryForm.annual_income_entry_id != null ||
          page.quickEntryForm.annual_expense_entry_id != null
        "
      >
        <summary>
          {{
            page.hasCompatibleAnnualPlanOptions
              ? 'Alinear con una linea del plan (opcional)'
              : 'Sin lineas anuales compatibles para esta clasificacion'
          }}
        </summary>
        <p class="ui-accounting-inline-note">
          Usa este enlace solo si quieres relacionar el movimiento con una fila concreta del
          presupuesto anual. La clasificacion principal ya queda guardada en el ledger.
        </p>

        <select
          v-if="page.quickEntryForm.movement_type === 'income'"
          v-model="page.quickEntryForm.annual_income_entry_id"
          class="select"
          :disabled="!page.annualIncomeOptionsCompatible.length"
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
          :disabled="!page.annualExpenseOptionsCompatible.length"
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
          placeholder="Interes (ej: 30.00, 0 si no aplica)"
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

      <div class="ui-accounting-submit-row">
        <p class="subtle">
          {{
            page.quickEntryForm.movement_type === 'transfer'
              ? 'La transferencia crea un asiento balanceado entre dos cuentas de liquidez.'
              : page.quickEntryForm.movement_type === 'investment'
                ? page.quickInvestmentIsCrossCurrency
                  ? 'Movimiento de inversion multimoneda: informa importe origen e importe destino segun ejecucion real del broker.'
                  : page.quickEntryForm.investment_direction === 'outflow'
                  ? 'La desinversion acredita inversion y devuelve liquidez al activo de caja.'
                  : 'El aporte acredita liquidez y registra el alta en la cuenta de inversion.'
                : page.quickEntryForm.movement_type === 'debt_payment'
                  ? 'El pago separa principal e intereses; total = principal + interes.'
                  : 'El backend genera la contrapartida contable y registra categoria/subcategoria como clasificacion primaria.'
          }}
        </p>
        <button
          class="btn btn-primary"
          type="submit"
          :disabled="page.transactionCreationLoading || !page.quickEntryReady"
        >
          {{ page.transactionCreationLoading ? 'Guardando...' : 'Registrar movimiento rapido' }}
        </button>
      </div>

      <p
        v-if="!page.quickEntryReady && !page.transactionCreationLoading"
        class="ui-accounting-inline-note"
      >
        Completa descripcion, fechas, importe y cuenta de liquidez. Cada tipo puede requerir
        cuentas, clasificacion funcional y desglose adicionales.
      </p>
    </form>
  </BaseModal>
</template>
