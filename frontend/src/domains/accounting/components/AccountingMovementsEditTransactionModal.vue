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

const editLiquidityGroups = computed(() => groupAndSortAccounts(props.page.liquidityAccounts));
const editOperationalGroups = computed(() => groupAndSortAccounts(props.page.editAccountOptions));
const editRevaluationGroups = computed(() =>
  groupAndSortAccounts(props.page.revaluationAccountOptions),
);
const editAdjustmentGroups = computed(() =>
  groupAndSortAccounts(props.page.quickAdjustmentAccountOptions),
);
const editCounterpartyGroups = computed(() =>
  groupAndSortAccounts(props.page.editCounterpartyOptions),
);

type MovementTypeOption = { value: string; label: string };
const commonTypeOptions = computed<MovementTypeOption[]>(() =>
  (props.page.editMovementTypeOptions as MovementTypeOption[]).slice(0, 2),
);
const advancedTypeOptions = computed<MovementTypeOption[]>(() =>
  (props.page.editMovementTypeOptions as MovementTypeOption[]).slice(2),
);

const showValueDate = ref(false);
const debtInterestManualOverride = ref(false);

function decimalsForCurrency(currency?: string): number {
  const code = String(currency ?? '')
    .trim()
    .toUpperCase();
  return code === 'BTC' || code === 'ETH' ? 8 : 2;
}

function parseDecimal(raw: string): number | null {
  const normalized = String(raw ?? '')
    .replace(',', '.')
    .trim();
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function maybeAutofillDebtInterest() {
  if (props.page.editTransactionForm.kind !== 'debt_payment') return;
  if (debtInterestManualOverride.value) return;
  const total = parseDecimal(props.page.editTransactionForm.amount);
  const principal = parseDecimal(props.page.editTransactionForm.principal_amount);
  if (total == null || principal == null) return;
  const interest = total - principal;
  if (!Number.isFinite(interest) || interest < 0) return;
  const decimals = decimalsForCurrency(props.page.editTransactionForm.currency);
  props.page.editTransactionForm.interest_amount = interest.toFixed(decimals);
}

function handleDebtInterestInput() {
  debtInterestManualOverride.value = true;
}

watch(
  () => props.page.showEditTransactionModal,
  (isOpen: boolean) => {
    if (!isOpen) return;
    debtInterestManualOverride.value = false;
    showValueDate.value =
      props.page.editTransactionForm.value_date !== props.page.editTransactionForm.booking_date;
  },
);
watch(
  () =>
    [
      props.page.editTransactionForm.kind,
      props.page.editTransactionForm.amount,
      props.page.editTransactionForm.principal_amount,
      props.page.editTransactionForm.currency,
    ] as const,
  () => {
    maybeAutofillDebtInterest();
  },
  { flush: 'sync' },
);

watch(
  () => props.page.editTransactionForm.booking_date,
  (date: string) => {
    if (!showValueDate.value) {
      props.page.editTransactionForm.value_date = date;
    }
  },
);

watch(showValueDate, (show: boolean) => {
  if (!show) {
    props.page.editTransactionForm.value_date = props.page.editTransactionForm.booking_date;
  }
});

const isInvestmentOutflow = computed(
  () =>
    props.page.editTransactionForm.kind === 'investment' &&
    props.page.editTransactionForm.investment_direction === 'outflow',
);
const isInvestmentReinvestment = computed(
  () =>
    props.page.editTransactionForm.kind === 'investment' &&
    props.page.editTransactionForm.investment_direction === 'reinvestment',
);

const editAdjustmentCurrentBalance = computed((): number | null => {
  if (props.page.editTransactionForm.kind !== 'balance_adjustment') return null;
  const raw = props.page.editSelectedAccountCurrentBalance;
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
});

const editAdjustmentDelta = computed((): number | null => {
  if (props.page.editTransactionForm.kind !== 'balance_adjustment') return null;
  const rawTarget = String(props.page.editTransactionForm.amount ?? '').trim();
  if (!rawTarget) return null;
  const currentBalance = editAdjustmentCurrentBalance.value;
  if (currentBalance == null) return null;
  const target = Number(rawTarget.replace(',', '.'));
  return Number.isFinite(target) ? Math.round((target - currentBalance) * 100) / 100 : null;
});

const editRevaluationCurrentBalance = computed((): number | null => {
  if (props.page.editTransactionForm.kind !== 'revaluation') return null;
  const raw = props.page.editSelectedAccountCurrentBalance;
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
});

const editMainAccountGroups = computed(() => {
  const kind = props.page.editTransactionForm.kind;
  if (kind === 'income' || kind === 'expense') {
    return editOperationalGroups.value;
  }
  return editLiquidityGroups.value;
});
</script>

<template>
  <BaseModal
    :open="page.showEditTransactionModal"
    title="Editar movimiento"
    panel-class="max-w-[920px]"
    @close="page.showEditTransactionModal = false"
  >
    <form
      class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form"
      @submit.prevent="page.submitEditedTransactionFromModal"
    >
      <div class="ui-accounting-segmented">
        <button
          v-for="option in commonTypeOptions"
          :key="option.value"
          type="button"
          class="btn ui-accounting-segmented-btn"
          :class="{
            'ui-accounting-segmented-btn-active': page.editTransactionForm.kind === option.value,
          }"
          @click="page.editTransactionForm.kind = option.value"
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
            'ui-accounting-segmented-btn-active': page.editTransactionForm.kind === option.value,
          }"
          @click="page.editTransactionForm.kind = option.value"
        >
          {{ option.label }}
        </button>
      </div>

      <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
        <label class="ui-accounting-field">
          <span>Descripcion</span>
          <input
            v-model="page.editTransactionForm.description"
            class="input"
            placeholder="Nomina marzo, compra semanal, mover a ahorro..."
            required
          />
        </label>

        <label class="ui-accounting-field">
          <span>Titularidad</span>
          <select v-model="page.editTransactionForm.ownership_id" class="select">
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
          <span>Fecha contabilizacion</span>
          <input
            v-model="page.editTransactionForm.booking_date"
            type="date"
            class="input"
            required
          />
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
              v-model="page.editTransactionForm.value_date"
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

      <template v-if="page.editTransactionForm.kind === 'revaluation'">
        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <select v-model="page.editTransactionForm.account_id" class="select" required>
            <option :value="null">Cuenta de inversion</option>
            <optgroup v-for="group in editRevaluationGroups" :key="group.key" :label="group.label">
              <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                {{ accountLabel(account) }} / {{ account.currency }}
              </option>
            </optgroup>
          </select>

          <input
            v-model="page.editTransactionForm.amount"
            class="input"
            inputmode="decimal"
            placeholder="Importe de la revalorizacion"
            required
          />
        </div>

        <p class="ui-accounting-balance-feedback">
          <template v-if="editRevaluationCurrentBalance != null">
            Saldo actual:
            <strong>{{ editRevaluationCurrentBalance.toFixed(2) }}</strong
            >.
            <template v-if="page.editTransactionForm.amount.trim()">
              Revalorizacion:
              <strong
                :class="
                  Number(page.editTransactionForm.amount) > 0
                    ? 'ui-accounting-tone-positive'
                    : Number(page.editTransactionForm.amount) < 0
                      ? 'ui-accounting-tone-negative'
                      : ''
                "
              >
                {{ Number(page.editTransactionForm.amount) >= 0 ? '+' : ''
                }}{{ page.editTransactionForm.amount }}
              </strong>
            </template>
          </template>
          <template v-else>Selecciona la cuenta de inversion para ver el saldo actual.</template>
        </p>
      </template>

      <template v-else-if="page.editTransactionForm.kind === 'investment'">
        <div class="ui-accounting-segmented">
          <button
            type="button"
            class="ui-accounting-segmented-btn"
            :class="{
              'ui-accounting-segmented-btn-active':
                page.editTransactionForm.investment_direction === 'inflow',
            }"
            @click="page.editTransactionForm.investment_direction = 'inflow'"
          >
            Aporte
          </button>
          <button
            type="button"
            class="ui-accounting-segmented-btn"
            :class="{
              'ui-accounting-segmented-btn-active':
                page.editTransactionForm.investment_direction === 'reinvestment',
            }"
            @click="page.editTransactionForm.investment_direction = 'reinvestment'"
          >
            Reinversion
          </button>
          <button
            type="button"
            class="ui-accounting-segmented-btn"
            :class="{
              'ui-accounting-segmented-btn-active':
                page.editTransactionForm.investment_direction === 'outflow',
            }"
            @click="page.editTransactionForm.investment_direction = 'outflow'"
          >
            Retirada
          </button>
        </div>

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <label class="ui-accounting-field">
            <span>
              {{
                isInvestmentReinvestment
                  ? 'Cuenta de inversion (origen)'
                  : `Cuenta de liquidez ${isInvestmentOutflow ? '(destino)' : '(origen)'}`
              }}
            </span>
            <select v-model="page.editTransactionForm.account_id" class="select" required>
              <option :value="null">Seleccionar</option>
              <optgroup
                v-for="group in isInvestmentReinvestment
                  ? groupAndSortAccounts(page.editInvestmentOriginOptions)
                  : editLiquidityGroups"
                :key="group.key"
                :label="group.label"
              >
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
          <label class="ui-accounting-field">
            <span>Cuenta de inversion {{ isInvestmentOutflow ? '(origen)' : '(destino)' }}</span>
            <select
              v-model="page.editTransactionForm.counterparty_account_id"
              class="select"
              required
            >
              <option :value="null">Seleccionar</option>
              <optgroup
                v-for="group in editCounterpartyGroups"
                :key="group.key"
                :label="group.label"
              >
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
        </div>

        <div class="ui-accounting-form-grid ui-accounting-form-grid-wide">
          <input
            v-model="page.editTransactionForm.amount"
            class="input"
            inputmode="decimal"
            :placeholder="`Importe${page.editInvestmentOriginCurrency ? ` (${page.editInvestmentOriginCurrency})` : ''}`"
            required
          />
          <input
            v-if="page.editInvestmentIsCrossCurrency"
            v-model="page.editTransactionForm.destination_amount"
            class="input"
            inputmode="decimal"
            :placeholder="`Importe destino (${page.editInvestmentDestinationCurrency || 'moneda destino'})`"
            required
          />
        </div>
      </template>

      <template v-else-if="page.editTransactionForm.kind === 'debt_payment'">
        <div class="ui-accounting-form-grid ui-accounting-form-grid-2col">
          <label class="ui-accounting-field">
            <span>Cuenta de liquidez</span>
            <select v-model="page.editTransactionForm.account_id" class="select" required>
              <option :value="null" disabled>Seleccionar</option>
              <optgroup v-for="group in editLiquidityGroups" :key="group.key" :label="group.label">
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
          <label class="ui-accounting-field">
            <span>Cuenta de pasivo</span>
            <select
              v-model="page.editTransactionForm.counterparty_account_id"
              class="select"
              required
            >
              <option :value="null" disabled>Seleccionar</option>
              <optgroup
                v-for="group in editCounterpartyGroups"
                :key="group.key"
                :label="group.label"
              >
                <option v-for="account in group.accounts" :key="account.id" :value="account.id">
                  {{ accountLabel(account) }} / {{ account.currency }}
                </option>
              </optgroup>
            </select>
          </label>
        </div>

        <div class="ui-accounting-debt-block">
          <p class="ui-accounting-debt-hint">
            Informa dos de los tres campos — el tercero se calcula automáticamente.
            <template v-if="page.editDebtComputedInterest != null">
              <span class="ui-accounting-tone-positive">
                Interés = {{ page.editDebtComputedInterest.toFixed(2) }}
                {{ page.editTransactionForm.currency }}
              </span>
            </template>
          </p>
          <div class="ui-accounting-form-grid">
            <label class="ui-accounting-field">
              <span>Total pagado</span>
              <input
                v-model="page.editTransactionForm.amount"
                class="input"
                inputmode="decimal"
                placeholder="Total cargado en cuenta"
                :required="
                  !(
                    page.editTransactionForm.principal_amount?.trim() &&
                    page.editTransactionForm.interest_amount?.trim()
                  )
                "
              />
            </label>
            <label class="ui-accounting-field">
              <span>Principal amortizado</span>
              <input
                v-model="page.editTransactionForm.principal_amount"
                class="input"
                inputmode="decimal"
                placeholder="Parte que reduce deuda"
              />
            </label>
            <label class="ui-accounting-field">
              <span>Interés</span>
              <input
                v-model="page.editTransactionForm.interest_amount"
                class="input"
                inputmode="decimal"
                :placeholder="
                  page.editDebtComputedInterest != null
                    ? `= ${page.editDebtComputedInterest.toFixed(2)}`
                    : 'Coste financiero'
                "
                @input="handleDebtInterestInput"
              />
            </label>
          </div>
          <p class="ui-accounting-inline-note">
            La cuenta de gasto de intereses se asigna automáticamente al guardar.
          </p>
        </div>
      </template>

      <div
        v-else
        class="ui-accounting-form-grid"
        :class="
          page.editTransactionForm.kind === 'transfer'
            ? 'ui-accounting-form-grid-wide'
            : 'ui-accounting-form-grid-edit-simple'
        "
      >
        <select v-model="page.editTransactionForm.account_id" class="select" required>
          <option :value="null" disabled>
            {{
              page.editTransactionForm.kind === 'balance_adjustment'
                ? 'Cuenta a conciliar'
                : 'Cuenta de liquidez'
            }}
          </option>
          <optgroup
            v-for="group in page.editTransactionForm.kind === 'balance_adjustment'
              ? editAdjustmentGroups
              : editMainAccountGroups"
            :key="group.key"
            :label="group.label"
          >
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>

        <input
          v-model="page.editTransactionForm.amount"
          class="input"
          inputmode="decimal"
          :placeholder="
            page.editTransactionForm.kind === 'balance_adjustment'
              ? 'Saldo final objetivo'
              : page.editTransactionForm.kind === 'transfer' && page.editInvestmentIsCrossCurrency
                ? page.editInvestmentOriginCurrency
                  ? `Importe origen (${page.editInvestmentOriginCurrency})`
                  : 'Importe origen'
                : '0.00'
          "
          required
        />

        <select
          v-if="page.editTransactionForm.kind === 'transfer'"
          v-model="page.editTransactionForm.counterparty_account_id"
          class="select"
          required
        >
          <option :value="null">Cuenta destino</option>
          <optgroup v-for="group in editCounterpartyGroups" :key="group.key" :label="group.label">
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>
      </div>

      <input
        v-if="page.editTransactionForm.kind === 'transfer' && page.editInvestmentIsCrossCurrency"
        v-model="page.editTransactionForm.destination_amount"
        class="input"
        inputmode="decimal"
        :placeholder="`Importe destino (${page.editInvestmentDestinationCurrency || 'moneda destino'})`"
        required
      />

      <p
        v-if="page.editTransactionForm.kind === 'balance_adjustment'"
        class="ui-accounting-balance-feedback"
      >
        <template v-if="editAdjustmentCurrentBalance != null">
          Saldo actual:
          <strong>{{ editAdjustmentCurrentBalance.toFixed(2) }}</strong
          >.
          <template v-if="editAdjustmentDelta != null">
            Ajuste calculado:
            <strong
              :class="
                editAdjustmentDelta > 0
                  ? 'ui-accounting-tone-positive'
                  : editAdjustmentDelta < 0
                    ? 'ui-accounting-tone-negative'
                    : ''
              "
            >
              {{ editAdjustmentDelta >= 0 ? '+' : '' }}{{ editAdjustmentDelta.toFixed(2) }}
            </strong>
          </template>
        </template>
        <template v-else>
          Selecciona la cuenta y el saldo final objetivo para calcular el ajuste automaticamente.
        </template>
      </p>

      <p
        v-if="page.editKindNeedsCounterparty && !page.editCounterpartyOptions.length"
        class="ui-accounting-inline-note"
      >
        {{ page.editCounterpartyMissingHint }}
      </p>

      <div
        v-if="page.editKindNeedsClassification"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <label class="ui-accounting-field">
          <span>Categoria</span>
          <select
            v-model="page.editTransactionForm.category_key"
            class="select"
            :disabled="page.editCategoryLocked"
            required
          >
            <option value="">Seleccionar</option>
            <option
              v-for="option in page.editCategoryOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="ui-accounting-field">
          <span>Subcategoria</span>
          <select
            v-model="page.editTransactionForm.subcategory_key"
            class="select"
            :disabled="page.editSubcategoryLocked"
            required
          >
            <option value="">Seleccionar</option>
            <option
              v-for="option in page.editSubcategoryOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <textarea
        v-model="page.editTransactionForm.notes"
        class="textarea"
        rows="2"
        placeholder="Nota opcional para el movimiento"
      />

      <p
        v-if="!page.editEntryReady && !page.transactionCreationLoading"
        class="ui-accounting-inline-note"
      >
        Completa descripcion, fechas, importe y cuenta. Algunos tipos requieren campos adicionales.
      </p>

      <div class="ui-accounting-submit-row">
        <p class="subtle">
          {{
            page.editTransactionForm.kind === 'transfer'
              ? 'Crea un asiento balanceado entre dos cuentas de liquidez.'
              : page.editTransactionForm.kind === 'investment'
                ? page.editInvestmentIsCrossCurrency
                  ? 'Inversion multimoneda: informa importe origen e importe destino segun ejecucion real.'
                  : page.editTransactionForm.investment_direction === 'reinvestment'
                    ? 'La reinversion mueve capital entre dos cuentas de inversion sin usar cuenta puente.'
                    : page.editTransactionForm.investment_direction === 'outflow'
                      ? 'La desinversion devuelve liquidez al activo de caja.'
                      : 'El aporte registra el alta en la cuenta de inversion.'
                : 'Las partidas contables se generan automaticamente.'
          }}
        </p>
        <button
          class="btn btn-primary"
          type="submit"
          :disabled="page.transactionCreationLoading || !page.editEntryReady"
        >
          {{ page.transactionCreationLoading ? 'Guardando...' : 'Guardar cambios' }}
        </button>
      </div>
    </form>
  </BaseModal>
</template>
