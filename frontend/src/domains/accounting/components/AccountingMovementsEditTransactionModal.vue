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

const editAccountGroups = computed(() => groupAndSortAccounts(props.page.editAccountOptions));
const editCounterpartyGroups = computed(() =>
  groupAndSortAccounts(props.page.editCounterpartyOptions),
);
</script>

<template>
  <BaseModal
    :open="page.showEditTransactionModal"
    title="Editar movimiento"
    panel-class="max-w-[760px]"
    @close="page.showEditTransactionModal = false"
  >
    <div class="ui-accounting-modal-copy">
      <p class="ui-page-eyebrow">Edicion</p>
      <p class="subtle">
        Ajusta tipo, cuenta, fechas e importe manteniendo el asiento balanceado y coherente.
      </p>
    </div>
    <form
      class="ui-accounting-form ui-accounting-transaction-form ui-accounting-modal-form ui-accounting-edit-form"
      @submit.prevent="page.submitEditedTransactionFromModal"
    >
      <div class="ui-accounting-segmented">
        <button
          v-for="option in page.editMovementTypeOptions"
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
      </div>

      <input
        v-model="page.editTransactionForm.description"
        class="input"
        placeholder="Nomina marzo, compra semanal, mover a ahorro..."
        required
      />
      <div class="ui-accounting-form-grid ui-accounting-form-grid-dates">
        <label class="ui-accounting-field">
          <span>Fecha contabilizacion</span>
          <input
            v-model="page.editTransactionForm.booking_date"
            type="date"
            class="input"
            required
          />
        </label>
        <label class="ui-accounting-field">
          <span>Fecha valor</span>
          <input v-model="page.editTransactionForm.value_date" type="date" class="input" required />
        </label>
        <label class="ui-accounting-field">
          <span>Hora</span>
          <input v-model="page.editTransactionForm.booking_time" type="time" class="input" />
        </label>
      </div>

      <div
        class="ui-accounting-form-grid"
        :class="
          page.editKindNeedsCounterparty
            ? 'ui-accounting-form-grid-wide'
            : 'ui-accounting-form-grid-edit-simple'
        "
      >
        <select v-model="page.editTransactionForm.ownership_id" class="select">
          <option
            v-for="option in page.ownershipOptions"
            :key="option.value == null ? 'none' : option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>

        <select v-model="page.editTransactionForm.account_id" class="select" required>
          <option :value="null" disabled>Cuenta principal</option>
          <optgroup v-for="group in editAccountGroups" :key="group.key" :label="group.label">
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
              ? 'Saldo objetivo'
              : page.editTransactionForm.kind === 'revaluation'
                ? 'Importe revalorizacion'
                : '0.00'
          "
          required
        />

        <select
          v-if="page.editKindNeedsCounterparty"
          v-model="page.editTransactionForm.counterparty_account_id"
          class="select"
          required
        >
          <option :value="null">{{ page.editCounterpartyLabel }}</option>
          <optgroup v-for="group in editCounterpartyGroups" :key="group.key" :label="group.label">
            <option v-for="account in group.accounts" :key="account.id" :value="account.id">
              {{ accountLabel(account) }} / {{ account.currency }}
            </option>
          </optgroup>
        </select>
      </div>
      <p
        v-if="page.editKindNeedsCounterparty && !page.editCounterpartyOptions.length"
        class="ui-accounting-inline-note"
      >
        {{ page.editCounterpartyMissingHint }}
      </p>
      <p v-else-if="page.editKindNeedsClassification" class="ui-accounting-inline-note">
        Selecciona categoria y subcategoria debajo.
      </p>
      <div
        v-if="page.editTransactionForm.kind === 'investment'"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <select v-model="page.editTransactionForm.investment_direction" class="select">
          <option value="inflow">Aporte (liquidez a inversion)</option>
          <option value="outflow">Retirada inversion (inversion a liquidez)</option>
        </select>
      </div>
      <p
        v-else-if="
          page.editTransactionForm.kind !== 'balance_adjustment' &&
          page.editTransactionForm.kind !== 'revaluation'
        "
        class="ui-accounting-inline-note"
      >
        No requiere contracuenta manual para este tipo.
      </p>

      <div
        v-if="page.editKindNeedsClassification"
        class="ui-accounting-form-grid ui-accounting-form-grid-wide"
      >
        <select v-model="page.editTransactionForm.category_key" class="select" required>
          <option value="">Categoria</option>
          <option
            v-for="option in page.editCategoryOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <select v-model="page.editTransactionForm.subcategory_key" class="select" required>
          <option value="">Subcategoria</option>
          <option
            v-for="option in page.editSubcategoryOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </div>

      <p
        v-if="
          page.editTransactionForm.kind === 'balance_adjustment' ||
          page.editTransactionForm.kind === 'revaluation'
        "
        class="ui-accounting-inline-note"
      >
        Saldo actual de la cuenta:
        <strong>
          {{
            page.editSelectedAccountCurrentBalance != null
              ? page.formatCompact(
                  page.editSelectedAccountCurrentBalance,
                  page.editTransactionForm.currency,
                )
              : '-'
          }}
        </strong>
        .
        {{
          page.editTransactionForm.kind === 'revaluation'
            ? 'Introduce el importe de la revalorizacion (diferencia respecto al saldo actual).'
            : 'Se registrara un asiento de ajuste por la diferencia.'
        }}
      </p>

      <label class="ui-accounting-field">
        <span>Notas</span>
        <textarea
          v-model="page.editTransactionForm.notes"
          class="textarea"
          rows="2"
          placeholder="Nota opcional para el movimiento"
        />
      </label>

      <div class="ui-accounting-submit-row">
        <p class="subtle">
          {{
            page.editTransactionForm.kind === 'balance_adjustment'
              ? 'Ajuste: fija el saldo actual de la cuenta al valor objetivo sin tocar otros movimientos.'
              : page.editTransactionForm.kind === 'revaluation'
                ? 'Revalorizacion: ajusta el importe registrado sin modificar los apuntes de contrapartida.'
                : 'Se mantiene el asiento balanceado y se actualizan tipo, cuenta, clasificacion e importe.'
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
      <p
        v-if="!page.editEntryReady && !page.transactionCreationLoading"
        class="ui-accounting-inline-note"
      >
        Completa descripcion, fechas, importe y cuenta principal. Segun el tipo tambien puede
        requerir contracuenta y clasificacion.
      </p>
    </form>
  </BaseModal>
</template>
